"""
Async equivalents of Model.save/save_base/_save_table.

Mix `AsyncModelMixin` into your model class to enable `asave()`. The
mixin reuses Django's sync helpers (`_prepare_related_fields_for_save`,
`_validate_force_insert`, `_is_pk_set`, `_assign_returned_values`) and
swaps out only the parts that touch the database.

Multi-table inheritance is not yet supported.
"""
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.db import router
from django.db.models import (
    Field,
    Model,
)
from django.db.models.signals import (
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)

from django_async_backend.db import async_connections
from django_async_backend.db.transaction import (
    async_atomic,
    async_mark_for_rollback_on_error,
)

if TYPE_CHECKING:
    from django_async_backend.db.models.manager import AsyncManager
    from django_async_backend.db.models.query import QuerySet


_UpdateValue = tuple[Field, type[Model] | None, object]


def _async_base_manager(cls: type[Model]) -> "AsyncManager":
    """
    Return the async manager to use for save/insert/update queries.

    Django's `_base_manager` is the standard choice but is created as a sync
    `Manager` when none is explicitly declared. Pick the first declared
    AsyncManager instead so the async ORM primitives are used.
    """
    from django_async_backend.db.models.manager import AsyncManager

    for manager in cls._meta.managers:
        if isinstance(manager, AsyncManager):
            return manager
    raise TypeError(
        f"{cls.__name__} must declare an AsyncManager to use asave()."
    )


class AsyncModelMixin:
    """
    Provide async save() for single-table models.
    """

    async def asave(
        self,
        *,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """
        Async equivalent of Model.save(). Override this in a subclass if you
        want to control the saving process.

        Backward-compat: if the model has a custom save() override, we fall
        back to running it via sync_to_async so the user's logic still runs.
        Models that rely on Model.save's default behavior get the native
        async path through asave_base().
        """
        from asgiref.sync import sync_to_async

        if type(self).save is not Model.save:
            await sync_to_async(self.save)(
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            )
            return

        self._prepare_related_fields_for_save(operation_name="save")

        using = using or router.db_for_write(
            self.__class__, instance=self
        )
        if force_insert and (force_update or update_fields):
            raise ValueError(
                "Cannot force both insert and updating in model saving."
            )

        deferred_non_generated_fields = {
            f.attname
            for f in self._meta.concrete_fields
            if f.attname not in self.__dict__ and f.generated is False
        }
        if update_fields is not None:
            # If update_fields is empty, skip the save. We do also check for
            # no-op saves later on for inheritance cases. This bailout is
            # still needed for skipping signal sending.
            if not update_fields:
                return

            update_fields = frozenset(update_fields)
            field_names = self._meta._non_pk_concrete_field_names
            not_updatable_fields = update_fields.difference(field_names)

            if not_updatable_fields:
                raise ValueError(
                    "The following fields do not exist in this model, "
                    "are m2m fields, primary keys, or are non-concrete "
                    "fields: %s" % ", ".join(not_updatable_fields)
                )

        # If saving to the same database, and this model is deferred, then
        # automatically do an "update_fields" save on the loaded fields.
        elif (
            not force_insert
            and deferred_non_generated_fields
            and using == self._state.db
            and self._is_pk_set()
        ):
            field_names = set()
            pk_fields = self._meta.pk_fields
            for field in self._meta.concrete_fields:
                if field not in pk_fields and not hasattr(field, "through"):
                    field_names.add(field.attname)
            loaded_fields = field_names.difference(
                deferred_non_generated_fields
            )
            if loaded_fields:
                update_fields = frozenset(loaded_fields)

        await self.asave_base(
            using=using,
            force_insert=force_insert,
            force_update=force_update,
            update_fields=update_fields,
        )

    asave.alters_data = True

    async def asave_base(
        self,
        raw: bool = False,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: frozenset[str] | None = None,
    ) -> None:
        """
        Async equivalent of Model.save_base(). Handle the parts of saving
        which should be done only once per save, yet need to be done in raw
        saves, too. This includes some sanity checks and signal sending.
        """
        using = using or router.db_for_write(
            self.__class__, instance=self
        )
        assert not (force_insert and (force_update or update_fields))
        assert update_fields is None or update_fields
        cls = origin = self.__class__
        # Skip proxies, but keep the origin as the proxy model.
        if cls._meta.proxy:
            cls = cls._meta.concrete_model
        meta = cls._meta
        if meta.parents:
            raise NotImplementedError(
                "Async save does not yet support multi-table inheritance."
            )
        if not meta.auto_created:
            await pre_save.asend(
                sender=origin,
                instance=self,
                raw=raw,
                using=using,
                update_fields=update_fields,
            )
        # A transaction isn't needed if one query is issued.
        async with async_mark_for_rollback_on_error(using=using):
            if not raw:
                # Validate force insert only when parents are inserted.
                force_insert = self._validate_force_insert(force_insert)
            updated = await self._asave_table(
                raw,
                cls,
                force_insert,
                force_update,
                using,
                update_fields,
            )
        # Store the database on which the object was saved
        self._state.db = using
        # Once saved, this is no longer a to-be-added instance.
        self._state.adding = False

        # Signal that the save is complete
        if not meta.auto_created:
            await post_save.asend(
                sender=origin,
                instance=self,
                created=(not updated),
                update_fields=update_fields,
                raw=raw,
                using=using,
            )

    asave_base.alters_data = True

    async def _asave_table(
        self,
        raw: bool = False,
        cls: type[Model] | None = None,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: frozenset[str] | None = None,
    ) -> bool:
        """
        Do the heavy-lifting involved in saving. Update or insert the data
        for a single table.
        """
        meta = cls._meta
        pk_fields = meta.pk_fields
        non_pks_non_generated = [
            f
            for f in meta.local_concrete_fields
            if f not in pk_fields and not f.generated
        ]

        if update_fields:
            non_pks_non_generated = [
                f
                for f in non_pks_non_generated
                if f.name in update_fields or f.attname in update_fields
            ]

        if not self._is_pk_set(meta):
            pk_val = meta.pk.get_pk_value_on_save(self)
            setattr(self, meta.pk.attname, pk_val)
        pk_set = self._is_pk_set(meta)
        if not pk_set and (force_update or update_fields):
            raise ValueError(
                "Cannot force an update in save() with no primary key."
            )
        updated = False
        # Skip an UPDATE when adding an instance and primary key has a default.
        if (
            not raw
            and not force_insert
            and not force_update
            and self._state.adding
            and all(
                f.has_default() or f.has_db_default()
                for f in meta.pk_fields
            )
        ):
            force_insert = True
        # If possible, try an UPDATE. If that doesn't update anything, do an
        # INSERT.
        if pk_set and not force_insert:
            base_qs = _async_base_manager(cls).using(using)
            values = [
                (
                    f,
                    None,
                    (
                        getattr(self, f.attname)
                        if raw
                        else f.pre_save(self, False)
                    ),
                )
                for f in non_pks_non_generated
            ]
            forced_update = update_fields or force_update
            pk_val = self._get_pk_val(meta)
            returning_fields = [
                f
                for f in meta.local_concrete_fields
                if (
                    f.generated
                    and f.referenced_fields.intersection(
                        non_pks_non_generated
                    )
                )
            ]
            for field, _model, value in values:
                if (
                    update_fields is None or field.name in update_fields
                ) and hasattr(value, "resolve_expression"):
                    returning_fields.append(field)
            results = await self._ado_update(
                base_qs,
                using,
                pk_val,
                values,
                update_fields,
                forced_update,
                returning_fields,
            )
            if updated := bool(results):
                self._assign_returned_values(results[0], returning_fields)
            elif force_update:
                raise self.NotUpdated(
                    "Forced update did not affect any rows."
                )
            elif update_fields:
                raise self.NotUpdated(
                    "Save with update_fields did not affect any rows."
                )
        if not updated:
            insert_fields = [
                f
                for f in meta.local_concrete_fields
                if not f.generated and (pk_set or f is not meta.auto_field)
            ]
            returning_fields = list(meta.db_returning_fields)
            can_return_columns_from_insert = async_connections[
                using
            ].features.can_return_columns_from_insert
            for field in insert_fields:
                value = (
                    getattr(self, field.attname)
                    if raw
                    else field.pre_save(self, add=True)
                )
                if hasattr(value, "resolve_expression"):
                    if field not in returning_fields:
                        returning_fields.append(field)
                elif (
                    field.db_returning
                    and not can_return_columns_from_insert
                    and not (pk_set and field is meta.auto_field)
                ):
                    returning_fields.remove(field)
            results = await self._ado_insert(
                _async_base_manager(cls),
                using,
                insert_fields,
                returning_fields,
                raw,
            )
            if results:
                self._assign_returned_values(results[0], returning_fields)
        return updated

    async def adelete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        """
        Async delete for a single instance.

        Fires `pre_delete` and `post_delete` signals via `Signal.asend`.
        Cascade deletes are not yet supported: deleting an instance whose
        model is the target of any reverse relation raises
        `NotImplementedError`. Use the async Collector once it lands.
        """
        if not self._is_pk_set():
            raise ValueError(
                "%s object can't be deleted because its %s attribute is "
                "set to None."
                % (self._meta.object_name, self._meta.pk.attname)
            )
        if keep_parents:
            raise NotImplementedError(
                "Async delete does not yet support keep_parents."
            )
        if self._meta.related_objects:
            raise NotImplementedError(
                "Async delete does not yet support cascading relations."
            )
        using = using or router.db_for_write(
            self.__class__, instance=self
        )
        cls = origin = self.__class__
        if cls._meta.proxy:
            cls = cls._meta.concrete_model
        meta = cls._meta

        if not meta.auto_created:
            await pre_delete.asend(
                sender=origin, instance=self, using=using, origin=self
            )

        async with async_atomic(using=using, savepoint=False):
            count = await _async_base_manager(cls).using(using).filter(
                pk=self.pk
            )._raw_delete(using=using)

        if not meta.auto_created:
            await post_delete.asend(
                sender=origin, instance=self, using=using, origin=self
            )

        setattr(self, meta.pk.attname, None)
        return count, {meta.label: count}

    adelete.alters_data = True

    async def _ado_insert(
        self,
        manager: "AsyncManager",
        using: str,
        fields: list[Field],
        returning_fields: list[Field],
        raw: bool,
    ) -> list[tuple[object, ...]]:
        """
        Do an INSERT. If returning_fields is defined then this method should
        return the newly created data for the model.
        """
        return await manager._insert(
            [self],
            fields=fields,
            returning_fields=returning_fields,
            using=using,
            raw=raw,
        )

    async def _ado_update(
        self,
        base_qs: "QuerySet",
        using: str,
        pk_val: object,
        values: list[_UpdateValue],
        update_fields: frozenset[str] | None,
        forced_update: bool,
        returning_fields: list[Field],
    ) -> list[tuple[object, ...]]:
        """
        Try to update the model. Return True if the model was updated (if an
        update query was done and a matching row was found in the DB).
        """
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            # We can end up here when saving a model in inheritance chain
            # where update_fields doesn't target any field in current model.
            # In that case we just say the update succeeded. Another case
            # ending up here is a model with just PK - in that case check
            # that the PK still exists.
            if update_fields is not None or await filtered.aexists():
                return [()]
            return []
        if self._meta.select_on_save and not forced_update:
            if not await filtered.aexists():
                return []
            if results := await filtered._update(values, returning_fields):
                return results
            return [()] if await filtered.aexists() else []
        return await filtered._update(values, returning_fields)

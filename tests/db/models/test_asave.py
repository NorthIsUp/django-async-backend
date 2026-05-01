from django.db.models.signals import (
    post_save,
    pre_save,
)
from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestAsave(AsyncioTestCase):
    async def test_asave_inserts_when_no_pk(self):
        obj = TestModel(name="A", value=1)
        await obj.asave()
        self.assertIsNotNone(obj.pk)
        self.assertFalse(obj._state.adding)
        fetched = await TestModel.async_object.aget(pk=obj.pk)
        self.assertEqual(fetched.value, 1)

    async def test_asave_updates_when_pk_set(self):
        obj = TestModel(name="A", value=1)
        await obj.asave()
        obj.value = 99
        await obj.asave()
        fetched = await TestModel.async_object.aget(pk=obj.pk)
        self.assertEqual(fetched.value, 99)

    async def test_asave_with_update_fields(self):
        obj = TestModel(name="A", value=1)
        await obj.asave()
        obj.name = "B"
        obj.value = 99
        await obj.asave(update_fields=["value"])
        fetched = await TestModel.async_object.aget(pk=obj.pk)
        self.assertEqual(fetched.name, "A")
        self.assertEqual(fetched.value, 99)

    async def test_asave_force_insert_with_force_update_raises(self):
        obj = TestModel(name="A")
        with self.assertRaises(ValueError):
            await obj.asave(force_insert=True, force_update=True)

    async def test_pre_save_post_save_signals_fire(self):
        seen = []

        def pre(sender, instance, **kwargs):
            seen.append(("pre", instance.name, kwargs.get("update_fields")))

        def post(sender, instance, created, **kwargs):
            seen.append(("post", instance.name, created))

        pre_save.connect(pre, sender=TestModel)
        post_save.connect(post, sender=TestModel)
        try:
            obj = TestModel(name="X")
            await obj.asave()
            obj.value = 1
            await obj.asave()
        finally:
            pre_save.disconnect(pre, sender=TestModel)
            post_save.disconnect(post, sender=TestModel)

        self.assertEqual(
            seen,
            [
                ("pre", "X", None),
                ("post", "X", True),
                ("pre", "X", None),
                ("post", "X", False),
            ],
        )


class TestAsaveBackwardCompat(AsyncioTestCase):
    """
    Models with a custom save() override should still have their save()
    called when asave() is invoked, instead of bypassing it.
    """

    async def test_overridden_save_runs(self):
        original_save = TestModel.save
        calls = []

        def custom_save(self, *args, **kwargs):
            calls.append("sync")
            return original_save(self, *args, **kwargs)

        TestModel.save = custom_save
        try:
            obj = TestModel(name="custom-save")
            await obj.asave()
            self.assertEqual(calls, ["sync"])
            self.assertIsNotNone(obj.pk)
        finally:
            TestModel.save = original_save


class TestACreate(AsyncioTestCase):
    async def test_returns_persisted_object(self):
        obj = await TestModel.async_object.acreate(name="A", value=5)
        self.assertIsNotNone(obj.pk)
        self.assertFalse(obj._state.adding)
        self.assertEqual(obj.value, 5)
        self.assertEqual(await TestModel.async_object.acount(), 1)

    async def test_acreate_dispatches_post_save_with_created_true(self):
        seen = []

        def receiver(sender, instance, created, **kwargs):
            seen.append(created)

        post_save.connect(receiver, sender=TestModel)
        try:
            await TestModel.async_object.acreate(name="A")
        finally:
            post_save.disconnect(receiver, sender=TestModel)
        self.assertEqual(seen, [True])

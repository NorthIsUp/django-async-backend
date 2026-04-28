from django.db.models.signals import (
    post_delete,
    pre_delete,
)
from test_app.models import GetLatestByModel, TestModel

from django_async_backend.test import AsyncioTestCase


class TestModelADelete(AsyncioTestCase):
    async def test_deletes_instance(self):
        obj = await GetLatestByModel.async_object.acreate(name="A")
        pk = obj.pk
        count, by_model = await obj.adelete()
        self.assertEqual(count, 1)
        self.assertEqual(by_model, {GetLatestByModel._meta.label: 1})
        self.assertIsNone(obj.pk)
        self.assertEqual(
            await GetLatestByModel.async_object.filter(pk=pk).acount(),
            0,
        )

    async def test_dispatches_signals(self):
        obj = await GetLatestByModel.async_object.acreate(name="B")
        seen = []

        def pre(sender, instance, **kwargs):
            seen.append(("pre", instance.name))

        def post(sender, instance, **kwargs):
            seen.append(("post", instance.name))

        pre_delete.connect(pre, sender=GetLatestByModel)
        post_delete.connect(post, sender=GetLatestByModel)
        try:
            await obj.adelete()
        finally:
            pre_delete.disconnect(pre, sender=GetLatestByModel)
            post_delete.disconnect(post, sender=GetLatestByModel)

        self.assertEqual(seen, [("pre", "B"), ("post", "B")])

    async def test_unsaved_raises(self):
        obj = GetLatestByModel(name="C")
        with self.assertRaises(ValueError):
            await obj.adelete()

    async def test_cascading_relation_raises(self):
        obj = await TestModel.async_object.acreate(name="A")
        with self.assertRaises(NotImplementedError):
            await obj.adelete()


class TestQuerySetADelete(AsyncioTestCase):
    async def test_deletes_filtered_rows(self):
        await GetLatestByModel.async_object.abulk_create(
            [
                GetLatestByModel(name="A"),
                GetLatestByModel(name="B"),
                GetLatestByModel(name="C"),
            ]
        )
        count, by_model = await GetLatestByModel.async_object.filter(
            name__in=["A", "B"]
        ).adelete()
        self.assertEqual(count, 2)
        self.assertEqual(by_model, {GetLatestByModel._meta.label: 2})
        remaining = sorted(
            [
                obj.name
                async for obj in GetLatestByModel.async_object.all()
            ]
        )
        self.assertEqual(remaining, ["C"])

    async def test_deletes_all(self):
        await GetLatestByModel.async_object.abulk_create(
            [GetLatestByModel(name=f"{i}") for i in range(3)]
        )
        count, _ = await GetLatestByModel.async_object.all().adelete()
        self.assertEqual(count, 3)
        self.assertEqual(await GetLatestByModel.async_object.acount(), 0)

    async def test_sliced_raises(self):
        with self.assertRaises(TypeError):
            await GetLatestByModel.async_object.all()[:1].adelete()

    async def test_after_values_raises(self):
        with self.assertRaises(TypeError):
            await GetLatestByModel.async_object.values("name").adelete()

    async def test_cascading_relation_raises(self):
        with self.assertRaises(NotImplementedError):
            await TestModel.async_object.all().adelete()

from django.db.models import Count
from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestDefer(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.acreate(name="A", value=1)
        await TestModel.async_object.acreate(name="B", value=2)

    async def test_defers_field(self):
        qs = TestModel.async_object.defer("value")
        obj = await qs.aget(name="A")
        # `value` should not be in the loaded fields. (Accessing a deferred
        # field would trigger a sync reload, which is not supported.)
        self.assertNotIn("value", obj.__dict__)

    async def test_defer_none_clears(self):
        qs = TestModel.async_object.defer("value").defer(None)
        obj = await qs.aget(name="A")
        self.assertIn("value", obj.__dict__)

    async def test_defer_after_values_raises(self):
        with self.assertRaises(TypeError):
            TestModel.async_object.values("name").defer("value")


class TestOnly(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.acreate(name="A", value=1)

    async def test_only_loads_subset(self):
        obj = await TestModel.async_object.only("name").aget(name="A")
        self.assertNotIn("value", obj.__dict__)
        self.assertEqual(obj.name, "A")

    async def test_only_none_raises(self):
        with self.assertRaises(TypeError):
            TestModel.async_object.only(None)

    async def test_only_after_values_raises(self):
        with self.assertRaises(TypeError):
            TestModel.async_object.values("name").only("name")


class TestAlias(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.acreate(name="A", value=1)
        await TestModel.async_object.acreate(name="B", value=2)

    async def test_alias_filterable_without_select(self):
        qs = TestModel.async_object.alias(
            relatives_count=Count("relatives")
        ).filter(relatives_count=0)
        names = sorted([obj.name async for obj in qs])
        self.assertEqual(names, ["A", "B"])

    async def test_alias_not_in_values(self):
        qs = TestModel.async_object.alias(
            relatives_count=Count("relatives")
        )
        obj = await qs.aget(name="A")
        # alias() doesn't add to SELECT, so the attribute isn't set.
        self.assertFalse(hasattr(obj, "relatives_count"))

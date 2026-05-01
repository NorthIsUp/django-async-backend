from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestAGetOrCreate(AsyncioTestCase):
    async def test_creates_when_missing(self):
        obj, created = await TestModel.async_object.aget_or_create(
            name="A", defaults={"value": 5}
        )
        self.assertTrue(created)
        self.assertEqual(obj.name, "A")
        self.assertEqual(obj.value, 5)
        self.assertEqual(await TestModel.async_object.acount(), 1)

    async def test_returns_existing(self):
        existing = await TestModel.async_object.acreate(
            name="A", value=1
        )
        obj, created = await TestModel.async_object.aget_or_create(
            name="A", defaults={"value": 99}
        )
        self.assertFalse(created)
        self.assertEqual(obj.pk, existing.pk)
        self.assertEqual(obj.value, 1)

    async def test_callable_default(self):
        obj, created = await TestModel.async_object.aget_or_create(
            name="A", defaults={"value": lambda: 42}
        )
        self.assertTrue(created)
        self.assertEqual(obj.value, 42)

    async def test_lookup_only_kwargs_not_set_on_create(self):
        # __ lookups don't end up as field params on create.
        obj, created = await TestModel.async_object.aget_or_create(
            name__exact="A", defaults={"name": "A", "value": 1}
        )
        self.assertTrue(created)
        self.assertEqual(obj.name, "A")

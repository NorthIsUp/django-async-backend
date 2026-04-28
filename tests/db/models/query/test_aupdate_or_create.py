from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestAUpdateOrCreate(AsyncioTestCase):
    async def test_creates_when_missing(self):
        obj, created = await TestModel.async_object.aupdate_or_create(
            name="A", defaults={"value": 5}
        )
        self.assertTrue(created)
        self.assertEqual(obj.value, 5)

    async def test_updates_existing(self):
        existing = await TestModel.async_object.acreate(
            name="A", value=1
        )
        obj, created = await TestModel.async_object.aupdate_or_create(
            name="A", defaults={"value": 99}
        )
        self.assertFalse(created)
        self.assertEqual(obj.pk, existing.pk)
        self.assertEqual(obj.value, 99)
        fetched = await TestModel.async_object.aget(pk=existing.pk)
        self.assertEqual(fetched.value, 99)

    async def test_create_defaults_distinct_from_defaults(self):
        obj, created = await TestModel.async_object.aupdate_or_create(
            name="A",
            defaults={"value": 1},
            create_defaults={"value": 100},
        )
        self.assertTrue(created)
        self.assertEqual(obj.value, 100)

        obj, created = await TestModel.async_object.aupdate_or_create(
            name="A",
            defaults={"value": 1},
            create_defaults={"value": 100},
        )
        self.assertFalse(created)
        self.assertEqual(obj.value, 1)

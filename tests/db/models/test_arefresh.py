from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestArefreshFromDb(AsyncioTestCase):
    async def test_refreshes_changed_value(self):
        obj = await TestModel.async_object.acreate(name="A", value=1)
        await TestModel.async_object.filter(pk=obj.pk).aupdate(value=99)
        # In-memory copy is stale.
        self.assertEqual(obj.value, 1)
        await obj.arefresh_from_db()
        self.assertEqual(obj.value, 99)

    async def test_refresh_specific_fields(self):
        obj = await TestModel.async_object.acreate(name="A", value=1)
        await TestModel.async_object.filter(pk=obj.pk).aupdate(value=99)
        await obj.arefresh_from_db(fields=["value"])
        self.assertEqual(obj.value, 99)

    async def test_refresh_relation_in_fields_raises(self):
        obj = await TestModel.async_object.acreate(name="A")
        with self.assertRaises(ValueError):
            await obj.arefresh_from_db(fields=["relative__name"])

from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestABulkUpdate(AsyncioTestCase):
    async def asyncSetUp(self):
        self.objs = await TestModel.async_object.abulk_create(
            [
                TestModel(name="A", value=1),
                TestModel(name="B", value=2),
                TestModel(name="C", value=3),
            ]
        )

    async def test_updates_all_objects(self):
        for i, obj in enumerate(self.objs):
            obj.value = (i + 1) * 10
        rows = await TestModel.async_object.abulk_update(
            self.objs, ["value"]
        )
        self.assertEqual(rows, 3)
        values = sorted(
            [
                obj.value
                async for obj in TestModel.async_object.all()
            ]
        )
        self.assertEqual(values, [10, 20, 30])

    async def test_empty_objects_returns_zero(self):
        rows = await TestModel.async_object.abulk_update([], ["value"])
        self.assertEqual(rows, 0)

    async def test_no_fields_raises(self):
        with self.assertRaises(ValueError):
            await TestModel.async_object.abulk_update(self.objs, [])

    async def test_invalid_batch_size_raises(self):
        with self.assertRaises(ValueError):
            await TestModel.async_object.abulk_update(
                self.objs, ["value"], batch_size=0
            )

    async def test_unsaved_object_raises(self):
        self.objs[0].pk = None
        with self.assertRaises(ValueError):
            await TestModel.async_object.abulk_update(
                self.objs, ["value"]
            )

    async def test_pk_field_raises(self):
        with self.assertRaises(ValueError):
            await TestModel.async_object.abulk_update(self.objs, ["id"])

    async def test_batch_size(self):
        for obj in self.objs:
            obj.value = 99
        rows = await TestModel.async_object.abulk_update(
            self.objs, ["value"], batch_size=1
        )
        self.assertEqual(rows, 3)
        values = sorted(
            [
                obj.value
                async for obj in TestModel.async_object.all()
            ]
        )
        self.assertEqual(values, [99, 99, 99])

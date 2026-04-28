from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestABulkCreate(AsyncioTestCase):
    async def test_returns_objects(self):
        result = await TestModel.async_object.abulk_create(
            [
                TestModel(name="Item1", value=1),
                TestModel(name="Item2", value=2),
            ]
        )
        self.assertEqual(len(result), 2)
        for obj in result:
            self.assertIsNotNone(obj.pk)
            self.assertFalse(obj._state.adding)

    async def test_persists_rows(self):
        await TestModel.async_object.abulk_create(
            [
                TestModel(name="Item1"),
                TestModel(name="Item2"),
                TestModel(name="Item3"),
            ]
        )
        self.assertEqual(await TestModel.async_object.acount(), 3)

    async def test_empty_list(self):
        result = await TestModel.async_object.abulk_create([])
        self.assertEqual(result, [])
        self.assertEqual(await TestModel.async_object.acount(), 0)

    async def test_batch_size(self):
        objs = [TestModel(name=f"Item{i}") for i in range(7)]
        result = await TestModel.async_object.abulk_create(
            objs, batch_size=2
        )
        self.assertEqual(len(result), 7)
        self.assertEqual(await TestModel.async_object.acount(), 7)

    async def test_invalid_batch_size_raises(self):
        with self.assertRaises(ValueError):
            await TestModel.async_object.abulk_create(
                [TestModel(name="X")], batch_size=0
            )

    async def test_ignore_conflicts(self):
        await TestModel.async_object.abulk_create(
            [TestModel(name="dup")]
        )
        # name has unique=True
        result = await TestModel.async_object.abulk_create(
            [
                TestModel(name="dup"),
                TestModel(name="new"),
            ],
            ignore_conflicts=True,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(await TestModel.async_object.acount(), 2)

    async def test_update_conflicts(self):
        await TestModel.async_object.abulk_create(
            [TestModel(name="dup", value=1)]
        )
        await TestModel.async_object.abulk_create(
            [TestModel(name="dup", value=99)],
            update_conflicts=True,
            update_fields=["value"],
            unique_fields=["name"],
        )
        obj = await TestModel.async_object.aget(name="dup")
        self.assertEqual(obj.value, 99)

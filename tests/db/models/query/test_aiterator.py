from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestAIterator(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.abulk_create(
            [TestModel(name=f"Item{i}") for i in range(5)]
        )

    async def test_iterates_all_rows(self):
        names = sorted(
            [
                obj.name
                async for obj in TestModel.async_object.all().aiterator()
            ]
        )
        self.assertEqual(names, [f"Item{i}" for i in range(5)])

    async def test_chunk_size(self):
        names = sorted(
            [
                obj.name
                async for obj in TestModel.async_object.all().aiterator(
                    chunk_size=2
                )
            ]
        )
        self.assertEqual(names, [f"Item{i}" for i in range(5)])

    async def test_invalid_chunk_size(self):
        with self.assertRaises(ValueError):
            async for _ in TestModel.async_object.all().aiterator(
                chunk_size=0
            ):
                pass

from test_app.models import GetLatestByModel, TestModel

from django_async_backend.test import AsyncioTestCase


class TestAContains(AsyncioTestCase):
    async def asyncSetUp(self):
        self.item1 = await TestModel.async_object.acreate(name="Item1")
        self.item2 = await TestModel.async_object.acreate(name="Item2")

    async def test_returns_true_for_present_object(self):
        self.assertTrue(
            await TestModel.async_object.all().acontains(self.item1)
        )

    async def test_filtered_queryset(self):
        qs = TestModel.async_object.filter(name="Item1")
        self.assertTrue(await qs.acontains(self.item1))
        self.assertFalse(await qs.acontains(self.item2))

    async def test_different_concrete_model_returns_false(self):
        other = await GetLatestByModel.async_object.acreate(name="Other")
        self.assertFalse(
            await TestModel.async_object.all().acontains(other)
        )

    async def test_unsaved_object_raises(self):
        unsaved = TestModel(name="X")
        with self.assertRaises(ValueError):
            await TestModel.async_object.all().acontains(unsaved)

    async def test_non_model_raises(self):
        with self.assertRaises(TypeError):
            await TestModel.async_object.all().acontains("not a model")

    async def test_after_values_raises(self):
        qs = TestModel.async_object.values("name")
        with self.assertRaises(TypeError):
            await qs.acontains(self.item1)

    async def test_uses_result_cache_when_evaluated(self):
        qs = TestModel.async_object.all()
        # Force evaluation
        [obj async for obj in qs]
        self.assertTrue(await qs.acontains(self.item1))

from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestCombineOps(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.abulk_create(
            [
                TestModel(name="A", value=1),
                TestModel(name="B", value=2),
                TestModel(name="C", value=3),
            ]
        )

    async def test_or(self):
        qs1 = TestModel.async_object.filter(name="A")
        qs2 = TestModel.async_object.filter(name="B")
        combined = qs1 | qs2
        names = sorted([obj.name async for obj in combined])
        self.assertEqual(names, ["A", "B"])

    async def test_and(self):
        qs1 = TestModel.async_object.filter(value__gte=2)
        qs2 = TestModel.async_object.filter(value__lte=2)
        combined = qs1 & qs2
        names = [obj.name async for obj in combined]
        self.assertEqual(names, ["B"])

    async def test_xor(self):
        qs1 = TestModel.async_object.filter(value__lte=2)  # A, B
        qs2 = TestModel.async_object.filter(value__gte=2)  # B, C
        combined = qs1 ^ qs2
        names = sorted([obj.name async for obj in combined])
        self.assertEqual(names, ["A", "C"])

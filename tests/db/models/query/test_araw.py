from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestARaw(AsyncioTestCase):
    async def asyncSetUp(self):
        await TestModel.async_object.abulk_create(
            [
                TestModel(name="A", value=1),
                TestModel(name="B", value=2),
                TestModel(name="C", value=3),
            ]
        )

    async def test_iterates_results(self):
        qs = TestModel.async_object.araw(
            "SELECT * FROM test_model ORDER BY name"
        )
        names = [obj.name async for obj in qs]
        self.assertEqual(names, ["A", "B", "C"])

    async def test_with_params(self):
        qs = TestModel.async_object.araw(
            "SELECT * FROM test_model WHERE value >= %s", [2]
        )
        names = sorted([obj.name async for obj in qs])
        self.assertEqual(names, ["B", "C"])

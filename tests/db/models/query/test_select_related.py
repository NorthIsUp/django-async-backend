from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestSelectRelated(AsyncioTestCase):
    async def asyncSetUp(self):
        self.parent = await TestModel.async_object.acreate(name="P")
        await TestModel.async_object.acreate(
            name="C", relative_id=self.parent.pk
        )

    async def test_select_related_loads_fk(self):
        qs = TestModel.async_object.select_related("relative")
        child = await qs.aget(name="C")
        # Accessing the related object should not trigger a separate query
        # because select_related joined it.
        self.assertEqual(child.relative.name, "P")

    async def test_select_related_after_values_raises(self):
        with self.assertRaises(TypeError):
            TestModel.async_object.values("name").select_related(
                "relative"
            )

    async def test_select_related_none_clears(self):
        qs = TestModel.async_object.select_related("relative").select_related(
            None
        )
        # No exception; still iterable.
        names = sorted([obj.name async for obj in qs])
        self.assertEqual(names, ["C", "P"])

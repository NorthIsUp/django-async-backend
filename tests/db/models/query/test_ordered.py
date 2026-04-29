from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestOrdered(AsyncioTestCase):
    async def test_unordered_queryset(self):
        self.assertFalse(TestModel.async_object.all().ordered)

    async def test_ordered_queryset(self):
        qs = TestModel.async_object.order_by("name")
        self.assertTrue(qs.ordered)

    async def test_none_is_ordered(self):
        # EmptyQuerySet is reported as ordered (matches Django).
        self.assertTrue(TestModel.async_object.none().ordered)

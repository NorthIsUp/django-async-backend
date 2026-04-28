from test_app.models import TestModel

from django_async_backend.test import AsyncioTestCase


class TestDates(AsyncioTestCase):
    async def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            TestModel.async_object.dates("created_at", "century")

    async def test_invalid_order(self):
        with self.assertRaises(ValueError):
            TestModel.async_object.dates("created_at", "year", "SIDEWAYS")


class TestDatetimes(AsyncioTestCase):
    async def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            TestModel.async_object.datetimes("created_at", "century")

    async def test_invalid_order(self):
        with self.assertRaises(ValueError):
            TestModel.async_object.datetimes(
                "created_at", "year", "SIDEWAYS"
            )

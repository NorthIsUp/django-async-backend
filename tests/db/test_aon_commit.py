from django.db import DEFAULT_DB_ALIAS

from django_async_backend.db import async_connections
from django_async_backend.db.transaction import (
    aon_commit,
    async_atomic,
)
from django_async_backend.test import AsyncioTransactionTestCase


class ForcedError(Exception):
    pass


class TestAonCommit(AsyncioTransactionTestCase):
    """Tests for the module-level transaction.aon_commit helper."""

    def setUp(self):
        self.fired = []

    async def test_runs_immediately_outside_transaction(self):
        await aon_commit(lambda: self.fired.append("a"))
        self.assertEqual(self.fired, ["a"])

    async def test_defers_until_commit(self):
        async with async_atomic():
            await aon_commit(lambda: self.fired.append("a"))
            self.assertEqual(self.fired, [])
        self.assertEqual(self.fired, ["a"])

    async def test_skipped_on_rollback(self):
        try:
            async with async_atomic():
                await aon_commit(lambda: self.fired.append("a"))
                raise ForcedError()
        except ForcedError:
            pass
        self.assertEqual(self.fired, [])

    async def test_routes_to_named_alias(self):
        await aon_commit(
            lambda: self.fired.append("a"), using=DEFAULT_DB_ALIAS
        )
        self.assertEqual(self.fired, ["a"])

    async def test_async_callable_runs(self):
        async def cb():
            self.fired.append("a")

        async with async_atomic():
            await aon_commit(cb)
        self.assertEqual(self.fired, ["a"])

    async def test_robust_swallows_errors(self):
        def boom():
            raise ForcedError("boom")

        with self.assertLogs(
            "django_async_backend.db.backends", "ERROR"
        ):
            async with async_atomic():
                await aon_commit(boom, robust=True)
                await aon_commit(lambda: self.fired.append("a"))

        self.assertEqual(self.fired, ["a"])

    async def asyncTearDown(self):
        await async_connections[DEFAULT_DB_ALIAS].close()

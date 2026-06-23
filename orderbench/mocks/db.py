"""Mock transactional database API (DB-API 2.0 flavoured), fully instrumented.

Usage pattern the candidate is expected to follow::

    conn = pool.connect()
    try:
        conn.begin()
        conn.execute(sql)
        conn.commit()
    finally:
        conn.close()

Invariants enforced:

* ``begin``    on a closed conn -> order; while a txn is active -> order.
* ``execute``  on a closed conn -> order; outside a txn -> guard.
* ``commit``/``rollback`` on a closed conn -> order; with no active txn -> guard.
* ``close``    on an already-closed conn -> double. (close implicitly rolls back.)
* teardown: a connection left open -> ``unclosed`` (the leak signal).

Fault injection is armed on the pool and propagated to each connection it creates,
so a test can make e.g. ``execute`` raise mid-transaction to probe cleanup-on-exception.
"""

from __future__ import annotations

from ..invariants import Injectable, RunContext


class MockConnection(Injectable):
    _name = "connection"

    def __init__(self, ctx: RunContext) -> None:
        self._init_injection()
        self._ctx = ctx
        self._closed = False
        self._in_txn = False
        self._committed = False
        ctx.register(self)

    def begin(self) -> None:
        if self._closed:
            self._ctx.violation("order", "begin", "begin() on a closed connection", self)
            return
        if self._in_txn:
            self._ctx.violation("order", "begin", "begin() while a transaction is already active", self)
            return
        self._maybe_inject("begin")
        self._in_txn = True
        self._committed = False

    def execute(self, sql: str):
        if self._closed:
            self._ctx.violation("order", "execute", "execute() on a closed connection", self)
            return None
        if not self._in_txn:
            self._ctx.violation("guard", "execute", "execute() outside of a transaction", self)
        self._maybe_inject("execute")  # raises here -> txn stays active, conn stays open
        return f"ok:{sql}"

    def commit(self) -> None:
        if self._closed:
            self._ctx.violation("order", "commit", "commit() on a closed connection", self)
            return
        if not self._in_txn:
            self._ctx.violation("guard", "commit", "commit() with no active transaction", self)
            return
        self._maybe_inject("commit")
        self._in_txn = False
        self._committed = True

    def rollback(self) -> None:
        if self._closed:
            self._ctx.violation("order", "rollback", "rollback() on a closed connection", self)
            return
        if not self._in_txn:
            self._ctx.violation("guard", "rollback", "rollback() with no active transaction", self)
            return
        self._in_txn = False

    def close(self) -> None:
        if self._closed:
            self._ctx.violation("double", "close", "close() on an already-closed connection", self)
            return
        # Closing implicitly discards any open transaction (rollback semantics).
        self._in_txn = False
        self._closed = True

    @property
    def committed(self) -> bool:
        return self._committed

    def _teardown_check(self, ctx: RunContext) -> None:
        if not self._closed:
            ctx.violation("unclosed", "close", "connection left open at scope exit (leak)", self)


class MockConnectionPool(Injectable):
    """Factory the candidate receives. Hands out instrumented connections."""

    _name = "pool"

    def __init__(self, ctx: RunContext) -> None:
        self._init_injection()
        self._ctx = ctx

    def connect(self) -> MockConnection:
        conn = MockConnection(self._ctx)
        if self._inj_op is not None:
            conn.arm_injection(self._inj_op, self._inj_index, self._inj_exc)
        return conn


def build(ctx: RunContext) -> MockConnectionPool:
    """Entry point used by the harness to construct this family's manager."""
    return MockConnectionPool(ctx)

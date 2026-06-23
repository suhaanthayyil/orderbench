"""Mock reentrant lock + guarded shared resource, fully instrumented.

The candidate receives an ``env`` exposing ``env.lock`` (a reentrant lock) and
``env.resource`` (a shared counter whose mutators must run under the lock).

Usage pattern the candidate is expected to follow::

    env.lock.acquire()
    try:
        env.resource.modify(delta)
    finally:
        env.lock.release()

Invariants enforced:

* ``release`` with no lock held -> guard (over-release).
* ``modify`` while the lock is *not* held -> guard (unguarded mutation).
* teardown: lock left held (acquire/release imbalance) -> ``unclosed`` (the leak signal).

Fault injection is armed on the env and propagated to the shared resource, so a test
can make ``modify`` raise while the lock is held to probe release-on-exception.
"""

from __future__ import annotations

from ..invariants import Injectable, RunContext


class MockReentrantLock:
    _name = "lock"

    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx
        self._depth = 0
        ctx.register(self)

    def acquire(self) -> None:
        self._depth += 1

    def release(self) -> None:
        if self._depth == 0:
            self._ctx.violation("guard", "release", "release() with no lock held (over-release)", self)
            return
        self._depth -= 1

    @property
    def held(self) -> bool:
        return self._depth > 0

    def _teardown_check(self, ctx: RunContext) -> None:
        if self._depth > 0:
            ctx.violation("unclosed", "release", "lock still held at scope exit (acquire/release imbalance)", self)


class MockSharedResource(Injectable):
    _name = "resource"

    def __init__(self, ctx: RunContext, lock: MockReentrantLock, value: int = 0) -> None:
        self._init_injection()
        self._ctx = ctx
        self._lock = lock
        self._value = value

    def modify(self, delta: int) -> int:
        if not self._lock.held:
            self._ctx.violation("guard", "modify", "modify() called without holding the lock", self)
        self._maybe_inject("modify")  # raises here -> lock is still held
        self._value += delta
        return self._value

    @property
    def value(self) -> int:
        return self._value


class MockLockEnv:
    """Factory the candidate receives, bundling the lock and the guarded resource."""

    _name = "env"

    def __init__(self, ctx: RunContext, value: int = 0) -> None:
        self._ctx = ctx
        self.lock = MockReentrantLock(ctx)
        self.resource = MockSharedResource(ctx, self.lock, value)

    def arm_injection(self, op: str, call_index: int = 1, exc: Exception | None = None) -> None:
        # Faults are injected on the guarded resource (the operation that can fail).
        self.resource.arm_injection(op, call_index, exc)


def build(ctx: RunContext, value: int = 0) -> MockLockEnv:
    """Entry point used by the harness to construct this family's manager."""
    return MockLockEnv(ctx, value)

"""Mock file/resource-handle API (context-manager flavoured), fully instrumented.

Usage pattern the candidate is expected to follow::

    handle = fs.open(path)
    try:
        data = handle.read()
        handle.write(transform(data))
    finally:
        handle.close()

Invariants enforced:

* ``read``/``write`` on a closed handle -> order.
* ``close`` on an already-closed handle -> double.
* teardown: a handle left open -> ``unclosed`` (the leak signal).

Fault injection is armed on the filesystem and propagated to each handle it opens,
so a test can make e.g. ``read`` raise to probe cleanup-on-exception.
"""

from __future__ import annotations

from ..invariants import Injectable, RunContext


class MockHandle(Injectable):
    _name = "handle"

    def __init__(self, ctx: RunContext, path: str, contents: str) -> None:
        self._init_injection()
        self._ctx = ctx
        self._path = path
        self._contents = contents
        self._closed = False
        self._written = None
        ctx.register(self)

    def read(self) -> str:
        if self._closed:
            self._ctx.violation("order", "read", "read() on a closed handle", self)
            return ""
        self._maybe_inject("read")
        return self._contents

    def write(self, data: str) -> None:
        if self._closed:
            self._ctx.violation("order", "write", "write() on a closed handle", self)
            return
        self._maybe_inject("write")
        self._written = data

    def close(self) -> None:
        if self._closed:
            self._ctx.violation("double", "close", "close() on an already-closed handle", self)
            return
        self._closed = True

    @property
    def written(self):
        return self._written

    def _teardown_check(self, ctx: RunContext) -> None:
        if not self._closed:
            ctx.violation("unclosed", "close", "handle left open at scope exit (leak)", self)


class MockFileSystem(Injectable):
    """Factory the candidate receives. Hands out instrumented handles."""

    _name = "fs"

    def __init__(self, ctx: RunContext, files: dict | None = None) -> None:
        self._init_injection()
        self._ctx = ctx
        self._files = dict(files or {})

    def open(self, path: str) -> MockHandle:
        contents = self._files.get(path, f"contents-of:{path}")
        handle = MockHandle(self._ctx, path, contents)
        if self._inj_op is not None:
            handle.arm_injection(self._inj_op, self._inj_index, self._inj_exc)
        return handle


def build(ctx: RunContext, files: dict | None = None) -> MockFileSystem:
    """Entry point used by the harness to construct this family's manager."""
    return MockFileSystem(ctx, files)

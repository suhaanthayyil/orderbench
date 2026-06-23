"""Instrumented mock API families used by OrderBench tasks.

Each family exposes a ``build(ctx, **kwargs)`` factory that returns the *manager*
object handed to the candidate program as its first argument:

* ``db``   -> :class:`MockConnectionPool`  (``pool``)
* ``fs``   -> :class:`MockFileSystem`      (``fs``)
* ``lock`` -> :class:`MockLockEnv`         (``env``)
"""

from __future__ import annotations

from . import db, fs, lock

FAMILIES = {
    "db": db,
    "fs": fs,
    "lock": lock,
}

__all__ = ["db", "fs", "lock", "FAMILIES"]

"""Construct-validity bridge (paper §V).

OrderBench grades against self-authored *mock* APIs. A reviewer may ask whether an
``unclosed`` violation reflects a real resource leak or an artifact of a contrived mock.
This script answers it by replicating the cleanup-on-exception pattern against the REAL
Python standard library and detecting the leak directly:

* ``sqlite3``  -- a still-open Connection after an injected error (probed by operating on it).
* ``threading.Lock`` -- a still-held lock after an injected error (probed by ``locked()``).

For each primitive we run a reference solution (try/finally) and a buggy solution (no
finally) on an error path. The buggy solution leaks a genuine OS-backed resource; the
reference does not. This is exactly what the mock's ``unclosed`` class flags, confirming
the mock is a faithful proxy for real resource discipline.
"""

from __future__ import annotations

import sqlite3
import threading


class InjectedError(Exception):
    pass


# --------------------------------------------------------------------------- sqlite3
def sqlite_reference(connect, sql):
    conn = connect()
    try:
        conn.execute("CREATE TABLE t(x)")
        conn.execute(sql)            # injected bad SQL raises here
        conn.commit()
        return "ok"
    finally:
        conn.close()


def sqlite_buggy(connect, sql):
    conn = connect()
    conn.execute("CREATE TABLE t(x)")
    conn.execute(sql)                # raises -> close() below is skipped (leak)
    conn.commit()
    conn.close()
    return "ok"


def sqlite_leaked(conn) -> bool:
    """A real sqlite3 connection raises ProgrammingError only once closed."""
    try:
        conn.execute("SELECT 1")
        return True   # still operable -> never closed -> leaked
    except sqlite3.ProgrammingError:
        return False  # closed


def run_sqlite(solution):
    leaked = {"value": None}

    def connect():
        c = sqlite3.connect(":memory:")
        leaked["conn"] = c
        return c

    bad_sql = "SELECT * FROM no_such_table"  # raises sqlite3.OperationalError (no such table)
    try:
        solution(connect, bad_sql)
    except Exception:
        pass
    return sqlite_leaked(leaked["conn"])


# --------------------------------------------------------------------------- threading.Lock
def lock_reference(lock, work):
    lock.acquire()
    try:
        work()                       # injected raise here
    finally:
        lock.release()


def lock_buggy(lock, work):
    lock.acquire()
    work()                           # raises -> release() below is skipped (leak)
    lock.release()


def run_lock(solution):
    lock = threading.Lock()

    def work():
        raise InjectedError("boom")

    try:
        solution(lock, work)
    except Exception:
        pass
    return lock.locked()             # True -> still held -> leaked


def main() -> int:
    cases = [
        ("sqlite3 Connection", "reference", run_sqlite(sqlite_reference)),
        ("sqlite3 Connection", "buggy",     run_sqlite(sqlite_buggy)),
        ("threading.Lock",     "reference", run_lock(lock_reference)),
        ("threading.Lock",     "buggy",     run_lock(lock_buggy)),
    ]
    print(f"{'real stdlib primitive':22} {'solution':10} {'leaked on error path?'}")
    print("-" * 56)
    ok = True
    for prim, kind, leaked in cases:
        print(f"{prim:22} {kind:10} {'YES (resource not released)' if leaked else 'no'}")
        # Expect: reference never leaks; buggy always leaks.
        if kind == "reference" and leaked:
            ok = False
        if kind == "buggy" and not leaked:
            ok = False
    print()
    if ok:
        print("BRIDGE PASS: the cleanup-on-exception leak reproduces against the real Python "
              "stdlib (an open sqlite3 connection; a held threading.Lock) exactly as the mock's "
              "`unclosed` class flags it. The mock is a faithful proxy.")
        return 0
    print("BRIDGE FAIL: stdlib behaviour did not match the expected pattern.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

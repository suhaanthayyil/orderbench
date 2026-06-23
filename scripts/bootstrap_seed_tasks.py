"""Materialize the hand-authored seed tasks as static files under tasks/.

These six tasks (two per family) are the canonical, reviewed examples. Agent-authored
tasks are added directly as static files following tasks/_schema.md; this bootstrap
exists only so the seed reference/buggy solutions are readable in one place and the
repo can be regenerated deterministically. Re-running it overwrites the seed tasks only.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"


def write_task(family, tid, meta, prompt, scenarios, reference, buggy):
    d = TASKS / family / tid
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (d / "prompt.md").write_text(prompt.strip() + "\n")
    (d / "scenarios.json").write_text(json.dumps(scenarios, indent=2) + "\n")
    (d / "reference.py").write_text(reference.lstrip("\n"))
    (d / "buggy.py").write_text(buggy.lstrip("\n"))
    print("wrote", d.relative_to(ROOT))


# --------------------------------------------------------------------------- db
write_task(
    "db", "db_001_run_query",
    {"id": "db_001_run_query", "family": "db",
     "title": "Run a query inside a transaction and always close the connection",
     "entrypoint": "run_query", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Open a connection from `pool`, run `sql` inside a transaction (begin, execute, commit),
and return the result of `execute`. The connection must always be closed, even if
`execute` raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": ["SELECT 1"], "expected": "ok:SELECT 1"},
        {"name": "fail_in_execute", "type": "error", "args": ["SELECT 1"],
         "inject": {"op": "execute", "call_index": 1}, "expect": "propagate"},
    ]},
    """
def run_query(pool, sql):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(sql)
        conn.commit()
        return result
    finally:
        conn.close()
""",
    """
def run_query(pool, sql):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(sql)
    conn.commit()
    conn.close()
    return result
""",
)

write_task(
    "db", "db_002_process_batch",
    {"id": "db_002_process_batch", "family": "db",
     "title": "Execute a batch of statements in one transaction; always close",
     "entrypoint": "process_batch", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Open a connection from `pool`, begin a transaction, execute every statement in
`statements` in order, commit, and return the list of results. The connection must
always be closed, even if one of the statements raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": [["A", "B"]], "expected": ["ok:A", "ok:B"]},
        {"name": "fail_second_stmt", "type": "error", "args": [["A", "B"]],
         "inject": {"op": "execute", "call_index": 2}, "expect": "propagate"},
    ]},
    """
def process_batch(pool, statements):
    conn = pool.connect()
    try:
        conn.begin()
        results = [conn.execute(s) for s in statements]
        conn.commit()
        return results
    finally:
        conn.close()
""",
    """
def process_batch(pool, statements):
    conn = pool.connect()
    conn.begin()
    results = [conn.execute(s) for s in statements]
    conn.commit()
    conn.close()
    return results
""",
)

# --------------------------------------------------------------------------- fs
write_task(
    "fs", "fs_001_uppercase_file",
    {"id": "fs_001_uppercase_file", "family": "fs",
     "title": "Read a file, write back its upper-cased contents, return the original",
     "entrypoint": "uppercase_file", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Open `path` from `fs`, read its contents, write the upper-cased contents back, and
return the ORIGINAL contents. The handle must always be closed, even if `read` raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": ["a.txt"], "expected": "hello",
         "build_kwargs": {"files": {"a.txt": "hello"}}},
        {"name": "fail_in_read", "type": "error", "args": ["a.txt"],
         "inject": {"op": "read", "call_index": 1}, "expect": "propagate",
         "build_kwargs": {"files": {"a.txt": "hello"}}},
    ]},
    """
def uppercase_file(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        handle.write(data.upper())
        return data
    finally:
        handle.close()
""",
    """
def uppercase_file(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.write(data.upper())
    handle.close()
    return data
""",
)

write_task(
    "fs", "fs_002_write_log",
    {"id": "fs_002_write_log", "family": "fs",
     "title": "Write a message to a file and always close the handle",
     "entrypoint": "write_log", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Open `path` from `fs`, write `message` to it, and return the string "written". The
handle must always be closed, even if `write` raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": ["log.txt", "hi"], "expected": "written"},
        {"name": "fail_in_write", "type": "error", "args": ["log.txt", "hi"],
         "inject": {"op": "write", "call_index": 1}, "expect": "propagate"},
    ]},
    """
def write_log(fs, path, message):
    handle = fs.open(path)
    try:
        handle.write(message)
        return "written"
    finally:
        handle.close()
""",
    """
def write_log(fs, path, message):
    handle = fs.open(path)
    handle.write(message)
    handle.close()
    return "written"
""",
)

# ------------------------------------------------------------------------- lock
write_task(
    "lock", "lock_001_apply_deltas",
    {"id": "lock_001_apply_deltas", "family": "lock",
     "title": "Apply deltas to a shared resource under the lock; always release",
     "entrypoint": "apply_deltas", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Acquire `env.lock`, apply each delta in `deltas` to `env.resource` via
`env.resource.modify(delta)`, and return the final value. The lock must always be
released, even if `modify` raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": [[1, 2, 3]], "expected": 6},
        {"name": "fail_second_modify", "type": "error", "args": [[1, 2, 3]],
         "inject": {"op": "modify", "call_index": 2}, "expect": "propagate"},
    ]},
    """
def apply_deltas(env, deltas):
    env.lock.acquire()
    try:
        result = 0
        for d in deltas:
            result = env.resource.modify(d)
        return result
    finally:
        env.lock.release()
""",
    """
def apply_deltas(env, deltas):
    env.lock.acquire()
    result = 0
    for d in deltas:
        result = env.resource.modify(d)
    env.lock.release()
    return result
""",
)

write_task(
    "lock", "lock_002_increment_counter",
    {"id": "lock_002_increment_counter", "family": "lock",
     "title": "Increment the shared counter under the lock; always release",
     "entrypoint": "increment_counter", "misuse_classes": ["unclosed"], "difficulty": "easy"},
    """
Acquire `env.lock`, increment `env.resource` by `n` via `env.resource.modify(n)`,
and return the new value. The lock must always be released, even if `modify` raises.
""",
    {"scenarios": [
        {"name": "happy", "type": "happy", "args": [5], "expected": 5},
        {"name": "fail_in_modify", "type": "error", "args": [5],
         "inject": {"op": "modify", "call_index": 1}, "expect": "propagate"},
    ]},
    """
def increment_counter(env, n):
    env.lock.acquire()
    try:
        return env.resource.modify(n)
    finally:
        env.lock.release()
""",
    """
def increment_counter(env, n):
    env.lock.acquire()
    value = env.resource.modify(n)
    env.lock.release()
    return value
""",
)

print("\nseed tasks written.")

"""Validate a SINGLE task directory. Exit 0 if valid, 1 otherwise.

Safe to run concurrently (reads only the given dir + the read-only library), so
parallel task-authoring agents can self-check each task they write:

    python3 scripts/validate_one.py tasks/db/db_010_transfer
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.harness import load_task, validate_task  # noqa: E402


def main(task_dir: str) -> int:
    task = load_task(task_dir)
    v = validate_task(task)
    if v.ok:
        print(f"OK   {task.id}  (reference clean, buggy trips >=1 violation)")
        return 0
    print(f"FAIL {task.id}")
    print("  reference_clean:", v.reference_clean, " buggy_violates:", v.buggy_violates)
    for m in v.messages:
        print("  -", m)
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 scripts/validate_one.py <task_dir>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

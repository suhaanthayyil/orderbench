"""Construct-validity gate: every task's reference must be clean and buggy must violate.

Exit code is non-zero if any task fails, so this doubles as a CI check.
Usage: python scripts/validate_all.py [tasks_root]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.harness import load_suite, validate_task  # noqa: E402


def main(tasks_root: str) -> int:
    tasks = load_suite(tasks_root)
    if not tasks:
        print(f"no tasks found under {tasks_root}")
        return 1

    n_ok = 0
    failures = []
    by_family: dict = {}
    for task in tasks:
        v = validate_task(task)
        by_family[task.family] = by_family.get(task.family, 0) + 1
        if v.ok:
            n_ok += 1
            print(f"  OK   {task.id}")
        else:
            failures.append(v)
            print(f"  FAIL {task.id}: {'; '.join(v.messages)}")

    print(f"\n{n_ok}/{len(tasks)} tasks valid", "by family:", by_family)
    if failures:
        print(f"{len(failures)} task(s) failed validation")
        return 1
    print("all tasks valid")
    return 0


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "tasks")
    raise SystemExit(main(root))

"""Re-grade every cached solution and assert it still matches the committed rows.

The published results are re-gradable offline: the harness caches one solution file per
(tag, model, task, rep), so grading can be replayed with no network and no model calls.
That also makes it a regression test. Any change to the mocks, the invariant engine, or the
harness must leave the committed rows byte-identical -- otherwise a published number silently
moved. Run after touching anything under orderbench/.

Exits non-zero on the first tag that disagrees.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.harness import load_suite, run_task_safe  # noqa: E402
from orderbench.invariants import cm_support, set_cm_support  # noqa: E402


def sanitize(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def main() -> int:
    assert not cm_support(), "context-manager support must default to off"
    tasks = {t.id: t for t in load_suite(ROOT / "tasks")}

    tags = sorted(p.parent.name for p in (ROOT / "results").glob("*/rows.json"))
    total = mismatch = skipped = 0
    for tag in tags:
        # A run's grading depends on the mock configuration it was collected under, which the
        # bundle records. The context-manager arm must be replayed with the protocol on, or
        # every one of its `with` solutions "mismatches" for the wrong reason.
        bundle = ROOT / "results" / tag / "results.json"
        cfg = {}
        if bundle.exists():
            cfg = json.loads(bundle.read_text()).get("config", {})
        set_cm_support(bool(cfg.get("mock_cm", False)))

        committed = json.loads((ROOT / "results" / tag / "rows.json").read_text())
        by_key: dict[tuple, list] = {}
        for r in committed:
            by_key.setdefault((r["model"], r["task_id"], r.get("rep", 0)), []).append(r)

        bad = n = 0
        for (model, task_id, rep), rows in by_key.items():
            sol = (ROOT / "results" / tag / "solutions" / sanitize(model)
                   / f"{task_id}__rep{rep}.py")
            if not sol.exists() or task_id not in tasks:
                skipped += 1
                continue
            fresh = {(r.scenario, r.output_ok, tuple(sorted(r.violations)), r.full_correct)
                     for r in run_task_safe(tasks[task_id], sol)}
            want = {(r["scenario"], r["output_ok"], tuple(sorted(r["violations"])),
                     r["full_correct"]) for r in rows}
            n += len(rows)
            if fresh != want:
                bad += 1
                if bad <= 3:
                    print(f"  MISMATCH {tag} {model} {task_id} rep{rep}\n"
                          f"    regraded={sorted(fresh)}\n    committed={sorted(want)}")
        total += n
        mismatch += bad
        flag = "OK  " if bad == 0 else "FAIL"
        cm = " [mock_cm=on]" if cm_support() else ""
        print(f"  {flag} {tag:26s} {n:5d} rows re-graded, {bad} mismatched{cm}")
    set_cm_support(False)

    print(f"\n{total} rows re-graded across {len(tags)} tags; "
          f"{mismatch} mismatched; {skipped} groups had no cached solution")
    if mismatch:
        print("REGRADE FAIL: a committed number moved.")
        return 1
    print("REGRADE PASS: every cached solution grades exactly as published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

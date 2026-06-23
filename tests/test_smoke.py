"""Smoke tests: the engine fires correctly and the suite is well-formed.

Run with: pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.harness import load_suite, run_task, validate_task  # noqa: E402
from orderbench.metrics import compute_metrics  # noqa: E402
from orderbench.runner import run_model  # noqa: E402

TASKS = ROOT / "tasks"


def _suite():
    suite = load_suite(TASKS)
    assert suite, "no tasks discovered"
    return suite


def test_every_task_valid():
    for task in _suite():
        v = validate_task(task)
        assert v.ok, f"{task.id} invalid: {v.messages}"


def test_reference_is_clean_everywhere():
    for task in _suite():
        for r in run_task(task, task.path / "reference.py"):
            assert r.full_correct, f"{task.id}/{r.scenario}: {r.detail}"


def test_buggy_leaks_only_on_error_path():
    for task in _suite():
        results = run_task(task, task.path / "buggy.py")
        happy = [r for r in results if r.type == "happy"]
        error = [r for r in results if r.type == "error"]
        # buggy is designed to pass happy paths ...
        assert all(r.full_correct for r in happy), f"{task.id}: buggy failed a happy path"
        # ... and trip at least one invariant somewhere on the error paths.
        assert any(r.violations for r in error), f"{task.id}: buggy never leaked"


def test_metrics_separate_reference_from_buggy():
    suite = _suite()
    sols = ROOT / "results" / "_pytest" / "solutions"
    ref_rows = run_model("reference", suite, sols)
    buggy_rows = run_model("buggy", suite, sols)
    ref = compute_metrics("reference", ref_rows)
    buggy = compute_metrics("buggy", buggy_rows)
    assert abs(ref.cleanup_gap) < 1e-9
    assert buggy.cleanup_gap > 0.5
    assert buggy.per_class["unclosed"] > 0


def test_injected_error_class_present_in_vocab():
    from orderbench.invariants import VIOLATION_CLASSES
    assert set(VIOLATION_CLASSES) == {"order", "guard", "double", "unclosed"}


def test_validity_bridge_passes():
    """The §V stdlib bridge: real sqlite3/threading.Lock leak on the error path
    exactly as the mock's `unclosed` class flags (reference clean, buggy leaks)."""
    import importlib.util
    vb = ROOT / "scripts" / "validity_bridge.py"
    spec = importlib.util.spec_from_file_location("validity_bridge", vb)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.run_sqlite(mod.sqlite_buggy) is True       # real connection leaks
    assert mod.run_sqlite(mod.sqlite_reference) is False  # try/finally closes it
    assert mod.run_lock(mod.lock_buggy) is True           # real lock stays held
    assert mod.run_lock(mod.lock_reference) is False      # finally releases it


if __name__ == "__main__":
    # Fallback runner so the suite works even without pytest installed.
    fns = {name: fn for name, fn in sorted(globals().items())
           if name.startswith("test_") and callable(fn)}
    failed = 0
    for name, fn in fns.items():
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {name}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} tests passed")
    raise SystemExit(1 if failed else 0)

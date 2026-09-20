"""Smoke tests: the engine fires correctly and the suite is well-formed.

Run with: pytest -q
"""

from __future__ import annotations

import sys
import tempfile
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
    sys.modules["validity_bridge"] = mod  # dataclass introspection needs the module registered
    spec.loader.exec_module(mod)
    # Every real stdlib primitive: the buggy (no-finally) path leaks a genuine resource on
    # error, while still producing the reference's happy output (output-only cannot tell).
    assert len(mod.PRIMS) >= 6
    for p in mod.PRIMS:
        assert mod._run_error(p) is True, f"{p.name} buggy should leak on error"
        assert mod._run_happy(p) is not None, f"{p.name} happy should produce output"
    assert mod.main() == 0  # BRIDGE PASS across all primitives


def test_context_manager_mode_is_off_by_default_and_sound_when_on():
    """The context-manager ablation must not disturb the published, method-only results.

    Off (the default): `with resource:` raises TypeError exactly as it does on an object with
    no `__exit__`, which is what every committed result was graded against. On: `with` is a
    real cleanup path -- it releases on the exception path and records no violation -- and the
    construct-validity gate still holds, so the ablation arm is graded by the same instrument.
    """
    from orderbench.invariants import RunContext, InjectedError, cm_support, set_cm_support
    from orderbench.mocks import db, fs, lock
    from orderbench.harness import validate_task

    assert cm_support() is False, "context-manager support must default to off"

    def run(build, body, op):
        ctx = RunContext()
        mgr = build(ctx)
        mgr.arm_injection(op, 1, InjectedError("boom"))
        raised = None
        try:
            body(mgr)
        except Exception as exc:  # noqa: BLE001
            raised = type(exc).__name__
        ctx.teardown()
        return raised, ctx.classes()

    cases = [
        (lambda c: db.build(c),
         lambda p: exec("with p.connect() as c:\n c.begin(); c.execute('x'); c.commit()", {"p": p}),
         "execute"),
        (lambda c: fs.build(c, {"a": "hi"}),
         lambda f: exec("with f.open('a') as h:\n h.write(h.read().upper())", {"f": f}), "read"),
        (lambda c: lock.build(c, 0),
         lambda e: exec("with e.lock:\n e.resource.modify(1)", {"e": e}), "modify"),
    ]
    try:
        for build, body, op in cases:
            raised, classes = run(build, body, op)
            assert raised == "TypeError", f"cm off: expected TypeError, got {raised}"

        set_cm_support(True)
        for build, body, op in cases:
            raised, classes = run(build, body, op)
            assert raised == "InjectedError", f"cm on: fault must propagate, got {raised}"
            assert classes == [], f"cm on: `with` must release cleanly, got {classes}"
        for task in _suite():
            assert validate_task(task).ok, f"{task.id}: gate fails under mock_cm=on"
    finally:
        set_cm_support(False)


def test_non_terminating_candidate_is_bounded_and_not_counted_as_a_leak():
    """A candidate that never returns must not hang the run, nor be scored as leaking.

    Models write this shape: read in a loop until the call returns empty. It is a reasonable
    real idiom, but the mock's `read()` always returns the same contents, so the loop never
    exits. Before the execution bound, one such generation stalled an entire evaluation at
    100% CPU. It is graded output-wrong (the function does not return) with no violation --
    charging it a cleanup violation would conflate non-termination with a cleanup bug.
    """
    import time
    from orderbench.harness import EXEC_TIMEOUT_SECONDS, run_task_safe

    spinner = (
        "def read_file(fs, path):\n"
        "    handle = fs.open(path)\n"
        "    try:\n"
        "        out = []\n"
        "        while True:\n"
        "            chunk = handle.read()\n"
        "            if chunk == '':\n"
        "                break\n"
        "            out.append(chunk)\n"
        "        return ''.join(out)\n"
        "    finally:\n"
        "        handle.close()\n"
    )
    task = next(t for t in _suite() if t.id == "fs_010_read_file")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sol.py"
        p.write_text(spinner)
        start = time.time()
        rows = run_task_safe(task, p)
        elapsed = time.time() - start

    assert elapsed < EXEC_TIMEOUT_SECONDS * len(rows) + 5, f"grading took {elapsed:.1f}s"
    happy = [r for r in rows if r.type == "happy"]
    assert happy and all(r.raised == "timeout" for r in happy), [r.raised for r in happy]
    assert all(not r.output_ok for r in happy)
    assert all(r.violations == [] for r in happy), "a timeout must not be scored as a leak"


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

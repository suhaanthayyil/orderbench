"""OrderBench harness: load a task, run a candidate solution through every scenario,
and grade it on BOTH output correctness AND the mock's invariant log.

A *task* lives in a directory containing:

* ``meta.json``      -- id, family, title, entrypoint, targeted misuse classes, difficulty.
* ``prompt.md``      -- the natural-language requirement shown to the model.
* ``scenarios.json`` -- the list of happy-path and error-injection scenarios.
* ``reference.py``   -- a correct solution (must be fully clean on every scenario).
* ``buggy.py``       -- a plausible-but-wrong solution (must trip >=1 violation).

A candidate solution is any Python module defining a function named ``meta["entrypoint"]``
whose first parameter is the family manager (``pool`` / ``fs`` / ``env``), followed by
the scenario ``args``.

Grading per scenario yields a :class:`ScenarioResult`:

* ``output_ok``    -- happy: return == expected; error: the injected fault propagated
                      (or the task-defined ``expect`` value was returned).
* ``violations``   -- list of invariant-violation classes the mock recorded.
* ``full_correct`` -- ``output_ok and not violations``.

The headline instrument is computed across scenarios in :mod:`orderbench.metrics`:
the *cleanup-on-exception gap* = (happy full-correct rate) - (error full-correct rate).
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List

from .invariants import InjectedError, RunContext
from .mocks import FAMILIES


# --------------------------------------------------------------------------- #
# Task / scenario model
# --------------------------------------------------------------------------- #
@dataclass
class Scenario:
    name: str
    type: str               # "happy" | "error"
    args: list = field(default_factory=list)
    expected: Any = None    # expected return value (happy)
    inject: dict | None = None   # {"op": str, "call_index": int}  (error)
    expect: str = "propagate"    # error scenarios: "propagate" | "return"
    expect_value: Any = None     # used when expect == "return"
    build_kwargs: dict = field(default_factory=dict)


@dataclass
class Task:
    id: str
    family: str
    title: str
    entrypoint: str
    misuse_classes: List[str]
    difficulty: str
    prompt: str
    scenarios: List[Scenario]
    path: Path

    @property
    def manager_name(self) -> str:
        return {"db": "pool", "fs": "fs", "lock": "env"}[self.family]


def load_task(task_dir: str | Path) -> Task:
    task_dir = Path(task_dir)
    meta = json.loads((task_dir / "meta.json").read_text())
    prompt = (task_dir / "prompt.md").read_text()
    raw = json.loads((task_dir / "scenarios.json").read_text())
    scenarios = [
        Scenario(
            name=s["name"],
            type=s["type"],
            args=s.get("args", []),
            expected=s.get("expected"),
            inject=s.get("inject"),
            expect=s.get("expect", "propagate"),
            expect_value=s.get("expect_value"),
            build_kwargs=s.get("build_kwargs", {}),
        )
        for s in raw["scenarios"]
    ]
    return Task(
        id=meta["id"],
        family=meta["family"],
        title=meta["title"],
        entrypoint=meta["entrypoint"],
        misuse_classes=meta.get("misuse_classes", []),
        difficulty=meta.get("difficulty", "medium"),
        prompt=prompt,
        scenarios=scenarios,
        path=task_dir,
    )


def load_suite(tasks_root: str | Path) -> List[Task]:
    tasks_root = Path(tasks_root)
    dirs = sorted(p.parent for p in tasks_root.rglob("meta.json"))
    return [load_task(d) for d in dirs]


def load_entrypoint(module_path: str | Path, entrypoint: str) -> Callable:
    """Import a Python file by path and return the named entrypoint function."""
    module_path = Path(module_path)
    spec = importlib.util.spec_from_file_location(f"_ob_{module_path.stem}_{id(module_path)}", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, entrypoint, None)
    if fn is None:
        raise AttributeError(f"{module_path} does not define entrypoint {entrypoint!r}")
    return fn


# --------------------------------------------------------------------------- #
# Grading
# --------------------------------------------------------------------------- #
@dataclass
class ScenarioResult:
    task_id: str
    scenario: str
    type: str
    output_ok: bool
    violations: List[str]
    raised: str | None
    detail: str

    @property
    def full_correct(self) -> bool:
        return self.output_ok and not self.violations


def run_scenario(task: Task, entrypoint: Callable, scenario: Scenario) -> ScenarioResult:
    """Execute one scenario against a candidate entrypoint and grade it."""
    ctx = RunContext()
    family = FAMILIES[task.family]
    manager = family.build(ctx, **scenario.build_kwargs)

    if scenario.inject:
        manager.arm_injection(
            scenario.inject["op"],
            int(scenario.inject.get("call_index", 1)),
            InjectedError(f"injected fault at {scenario.inject['op']}"),
        )

    raised: str | None = None
    returned: Any = None
    try:
        returned = entrypoint(manager, *scenario.args)
    except InjectedError as exc:
        raised = "InjectedError"
        _ = exc
    except Exception as exc:  # candidate crashed for some other reason
        raised = type(exc).__name__

    # End-of-scope leak/cleanup checks.
    ctx.teardown()
    violations = ctx.classes()

    # Output correctness.
    if scenario.type == "happy":
        output_ok = (raised is None) and (returned == scenario.expected)
        detail = f"returned={returned!r} expected={scenario.expected!r} raised={raised}"
    else:  # error scenario
        if scenario.expect == "propagate":
            output_ok = raised == "InjectedError"
        else:  # "return": candidate is allowed to swallow and return a sentinel
            output_ok = (raised is None) and (returned == scenario.expect_value)
        detail = f"expect={scenario.expect} returned={returned!r} raised={raised}"

    return ScenarioResult(
        task_id=task.id,
        scenario=scenario.name,
        type=scenario.type,
        output_ok=output_ok,
        violations=violations,
        raised=raised,
        detail=f"{detail} violations={ctx.summary()}",
    )


def run_task(task: Task, module_path: str | Path) -> List[ScenarioResult]:
    """Run every scenario of a task against the solution module at ``module_path``."""
    entrypoint = load_entrypoint(module_path, task.entrypoint)
    return [run_scenario(task, entrypoint, s) for s in task.scenarios]


def run_task_safe(task: Task, module_path: str | Path) -> List[ScenarioResult]:
    """Like :func:`run_task`, but tolerant of malformed candidate solutions.

    Real models sometimes emit code that fails to import or never defines the
    entrypoint. Such a solution must score as *wrong on every scenario* (output
    incorrect, no violations) rather than crashing the whole eval run.
    """
    try:
        entrypoint = load_entrypoint(module_path, task.entrypoint)
    except Exception as exc:  # syntax error, import error, missing entrypoint
        reason = f"load_error:{type(exc).__name__}"
        return [
            ScenarioResult(task.id, s.name, s.type, output_ok=False,
                           violations=[], raised=reason, detail=str(exc)[:200])
            for s in task.scenarios
        ]
    return [run_scenario(task, entrypoint, s) for s in task.scenarios]


# --------------------------------------------------------------------------- #
# Built-in solution validation (reference must pass, buggy must fail)
# --------------------------------------------------------------------------- #
@dataclass
class TaskValidation:
    task_id: str
    ok: bool
    reference_clean: bool
    buggy_violates: bool
    messages: List[str]


def validate_task(task: Task) -> TaskValidation:
    """A well-formed task: reference is fully clean on all scenarios; buggy trips >=1
    violation on at least one scenario. This is the construct-validity gate every task
    (hand- or agent-authored) must pass before it enters the suite."""
    msgs: List[str] = []

    ref_results = run_task(task, task.path / "reference.py")
    reference_clean = all(r.full_correct for r in ref_results)
    if not reference_clean:
        for r in ref_results:
            if not r.full_correct:
                msgs.append(f"reference FAILED on {r.scenario}: {r.detail}")

    buggy_path = task.path / "buggy.py"
    buggy_violates = False
    if buggy_path.exists():
        buggy_results = run_task(task, buggy_path)
        buggy_violates = any(r.violations for r in buggy_results)
        if not buggy_violates:
            msgs.append("buggy solution did not trip any invariant on any scenario")
    else:
        msgs.append("no buggy.py present")

    ok = reference_clean and buggy_violates
    return TaskValidation(task.id, ok, reference_clean, buggy_violates, msgs)

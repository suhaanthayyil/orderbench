"""Metric computation for OrderBench.

Given a flat list of per-scenario results (each a dict with at least
``type``, ``output_ok``, ``violations``, ``full_correct``), compute:

* ``happy_correct``      -- mean full-correct over happy-path scenarios.
* ``error_correct``      -- mean full-correct over error-injection scenarios.
* ``cleanup_gap``        -- happy_correct - error_correct  (THE headline number).
* ``silent_misuse_rate`` -- fraction of scenarios where output is correct yet >=1
                            invariant was violated ("looks right but leaks").
* ``per_class``          -- count of each violation class across all scenarios.
* bootstrap confidence intervals for the rates, resampled over tasks (not scenarios),
  so the unit of uncertainty is the task -- the honest unit for a benchmark.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import numpy as np

from .invariants import VIOLATION_CLASSES


@dataclass
class Metrics:
    model: str
    n_tasks: int
    n_scenarios: int
    happy_correct: float
    error_correct: float
    cleanup_gap: float
    silent_misuse_rate: float
    per_class: Dict[str, int]
    ci: Dict[str, list] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "n_tasks": self.n_tasks,
            "n_scenarios": self.n_scenarios,
            "happy_correct": self.happy_correct,
            "error_correct": self.error_correct,
            "cleanup_gap": self.cleanup_gap,
            "silent_misuse_rate": self.silent_misuse_rate,
            "per_class": self.per_class,
            "ci": self.ci,
        }


def _rate(flags: Sequence[bool]) -> float:
    return float(np.mean(flags)) if len(flags) else 0.0


def _bootstrap_ci(task_means: Sequence[float], n_boot: int = 2000, seed: int = 0,
                  alpha: float = 0.05) -> list:
    """Percentile bootstrap CI resampling over per-task means."""
    arr = np.asarray(task_means, dtype=float)
    if len(arr) == 0:
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        boots[i] = sample.mean()
    lo = float(np.percentile(boots, 100 * alpha / 2))
    hi = float(np.percentile(boots, 100 * (1 - alpha / 2)))
    return [round(lo, 4), round(hi, 4)]


def compute_metrics(model: str, results: List[dict], seed: int = 0) -> Metrics:
    """``results`` is a flat list across all tasks/scenarios/repeats for one model."""
    happy = [r["full_correct"] for r in results if r["type"] == "happy"]
    error = [r["full_correct"] for r in results if r["type"] == "error"]
    silent = [bool(r["output_ok"] and r["violations"]) for r in results]

    per_class: Counter = Counter()
    for r in results:
        for c in r["violations"]:
            per_class[c] += 1

    # Per-task means for bootstrapping.
    by_task_happy: Dict[str, list] = defaultdict(list)
    by_task_error: Dict[str, list] = defaultdict(list)
    by_task_gap: Dict[str, list] = defaultdict(list)
    for r in results:
        if r["type"] == "happy":
            by_task_happy[r["task_id"]].append(r["full_correct"])
        else:
            by_task_error[r["task_id"]].append(r["full_correct"])
    task_ids = set(by_task_happy) | set(by_task_error)
    happy_task_means, error_task_means, gap_task_means = [], [], []
    for t in task_ids:
        h = _rate(by_task_happy.get(t, []))
        e = _rate(by_task_error.get(t, []))
        if by_task_happy.get(t):
            happy_task_means.append(h)
        if by_task_error.get(t):
            error_task_means.append(e)
        if by_task_happy.get(t) and by_task_error.get(t):
            gap_task_means.append(h - e)

    happy_correct = _rate(happy)
    error_correct = _rate(error)
    metrics = Metrics(
        model=model,
        n_tasks=len(task_ids),
        n_scenarios=len(results),
        happy_correct=round(happy_correct, 4),
        error_correct=round(error_correct, 4),
        cleanup_gap=round(happy_correct - error_correct, 4),
        silent_misuse_rate=round(_rate(silent), 4),
        per_class={c: int(per_class.get(c, 0)) for c in VIOLATION_CLASSES},
        ci={
            "happy_correct": _bootstrap_ci(happy_task_means, seed=seed),
            "error_correct": _bootstrap_ci(error_task_means, seed=seed + 1),
            "cleanup_gap": _bootstrap_ci(gap_task_means, seed=seed + 2),
        },
    )
    return metrics

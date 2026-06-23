"""Runtime invariant engine for OrderBench.

The central idea of OrderBench: the API a candidate program uses is a *self-authored
mock* whose every method is instrumented. When candidate code misuses the API
(wrong call order, missing guard, double-free, or a resource left open), the mock
records a deterministic :class:`Violation`. These are *silent* failures: the program
can return a perfectly correct value yet still leak a connection or skip a rollback.
Output-only benchmarks (HumanEval, SWE-bench, ...) structurally cannot see them.

Violation taxonomy (four classes):

* ``order``    -- an operation issued in an invalid state / wrong sequence
                 (e.g. ``commit()`` before ``begin()``, ``read()`` after ``close()``).
* ``guard``    -- an operation missing a required precondition
                 (e.g. ``commit()`` with no active transaction, ``release()`` with no lock held).
* ``double``   -- a terminal operation applied twice
                 (e.g. ``close()`` on an already-closed handle).
* ``unclosed`` -- a resource left in a non-final state at scenario teardown
                 (the *leak* class; the headline signal when it happens on an error path).

:class:`InjectedError` is raised by a mock when the harness has armed fault injection
at a given operation. It models an *external* failure (I/O error, dropped socket) --
NOT a misuse. The candidate's response to it (cleanup-on-exception) is what is graded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

#: The closed vocabulary of invariant-violation classes.
VIOLATION_CLASSES = ("order", "guard", "double", "unclosed")


class InjectedError(Exception):
    """An externally-injected fault (e.g. I/O error) raised by a mock operation.

    Represents an environmental failure the candidate program must clean up after,
    not a misuse of the API. Correct code lets it propagate (or handles it) *after*
    releasing every resource it acquired.
    """


@dataclass
class Violation:
    """A single recorded invariant violation."""

    cls: str       # one of VIOLATION_CLASSES
    op: str        # the operation involved (e.g. "commit", "close")
    message: str   # human-readable explanation
    resource: str  # name of the offending resource

    def __post_init__(self) -> None:
        if self.cls not in VIOLATION_CLASSES:
            raise ValueError(f"unknown violation class: {self.cls!r}")


class RunContext:
    """Per-scenario state: collects violations and tracks live resources for teardown.

    A fresh ``RunContext`` is created for every scenario execution, so runs are fully
    isolated and deterministic. Mocks register themselves on construction and report
    violations through :meth:`violation`. After the candidate returns (or raises),
    the harness calls :meth:`teardown`, which asks every registered resource whether
    it was left open -> ``unclosed`` violations.
    """

    def __init__(self) -> None:
        self.violations: List[Violation] = []
        self._resources: list = []
        self._tornDown = False

    # -- registration -------------------------------------------------------
    def register(self, resource) -> None:
        self._resources.append(resource)

    # -- reporting ----------------------------------------------------------
    def violation(self, cls: str, op: str, message: str, resource) -> None:
        self.violations.append(Violation(cls, op, message, _name(resource)))

    # -- end-of-scenario checks --------------------------------------------
    def teardown(self) -> None:
        """Run leak/cleanup checks on every registered resource (idempotent)."""
        if self._tornDown:
            return
        self._tornDown = True
        for r in self._resources:
            check = getattr(r, "_teardown_check", None)
            if check is not None:
                check(self)

    # -- queries ------------------------------------------------------------
    @property
    def clean(self) -> bool:
        return len(self.violations) == 0

    def classes(self) -> List[str]:
        return [v.cls for v in self.violations]

    def summary(self) -> str:
        if self.clean:
            return "clean"
        return "; ".join(f"[{v.cls}] {v.message}" for v in self.violations)


def _name(resource) -> str:
    return getattr(resource, "_name", resource.__class__.__name__)


class Injectable:
    """Mixin giving a mock resource an arm-able, count-indexed fault injector.

    The harness calls :meth:`arm_injection` (usually via the manager) before running
    the candidate. On the ``call_index``-th invocation of operation ``op``, the next
    :meth:`_maybe_inject` raises the configured :class:`InjectedError`.
    """

    def _init_injection(self) -> None:
        self._inj_op = None
        self._inj_index = 1
        self._inj_exc = None
        self._op_counts: dict = {}

    def arm_injection(self, op: str, call_index: int = 1, exc: Exception | None = None) -> None:
        self._inj_op = op
        self._inj_index = int(call_index)
        self._inj_exc = exc

    def _maybe_inject(self, op: str) -> None:
        n = self._op_counts.get(op, 0) + 1
        self._op_counts[op] = n
        if op == self._inj_op and n == self._inj_index:
            raise self._inj_exc or InjectedError(f"injected fault at {op}#{n}")

"""OrderBench: measuring cleanup-on-exception in LLM-generated code.

A contamination-free, copyright-clean benchmark built entirely on self-authored,
instrumented mock APIs. Candidate programs can return correct output yet silently
leak resources, skip rollbacks, or unbalance locks on injected error paths -- failures
that output-only benchmarks structurally cannot observe.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .harness import Task, load_suite, load_task, run_task, validate_task  # noqa: F401
from .metrics import compute_metrics  # noqa: F401

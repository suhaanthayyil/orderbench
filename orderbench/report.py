"""Turn graded result rows into a results bundle and LaTeX tables for the paper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .metrics import Metrics, compute_metrics


def summarize(rows_by_model: Dict[str, List[dict]]) -> Dict[str, Metrics]:
    return {model: compute_metrics(model, rows) for model, rows in rows_by_model.items()}


def results_bundle(rows_by_model: Dict[str, List[dict]]) -> dict:
    metrics = summarize(rows_by_model)
    return {"models": {m: met.as_dict() for m, met in metrics.items()}}


def write_bundle(bundle: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(bundle, indent=2))


def _fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _fmt_ci(ci: list) -> str:
    return f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}]"


def main_results_table(bundle: dict) -> str:
    """LaTeX table: per-model happy / error / gap / silent-misuse, with CIs on the gap."""
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Model & Happy-path & Error-path & Cleanup gap & Silent-misuse \\",
        r" & correct (\%) & correct (\%) & (pp) [95\% CI] & rate (\%) \\",
        r"\midrule",
    ]
    for m, d in bundle["models"].items():
        gap_ci = _fmt_ci(d["ci"]["cleanup_gap"])
        lines.append(
            f"{_escape(m)} & {_fmt_pct(d['happy_correct'])} & {_fmt_pct(d['error_correct'])} & "
            f"{100 * d['cleanup_gap']:.1f} {gap_ci} & {_fmt_pct(d['silent_misuse_rate'])} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def per_class_table(bundle: dict) -> str:
    """LaTeX table: violation counts per class per model."""
    classes = ["order", "guard", "double", "unclosed"]
    header = " & ".join(["Model"] + [c for c in classes])
    lines = [
        r"\begin{tabular}{l" + "r" * len(classes) + "}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]
    for m, d in bundle["models"].items():
        cells = " & ".join(str(d["per_class"].get(c, 0)) for c in classes)
        lines.append(f"{_escape(m)} & {cells} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def _escape(s: str) -> str:
    return s.replace("_", r"\_")


def write_tables(bundle: dict, tables_dir: str | Path) -> None:
    tables_dir = Path(tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "main_results.tex").write_text(main_results_table(bundle))
    (tables_dir / "per_class.tex").write_text(per_class_table(bundle))

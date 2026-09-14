"""One full-width per-model table for the neutral condition.

The paper previously carried two 13-row breakdowns of the same runs -- one decomposing the gap
(happy/error full-correctness, silent misuse on both denominators) and one showing which
cleanup idiom each candidate wrote and the per-family gaps. They answer different questions
about the same rows, so they are emitted here as a single spanning table: at an 8-page limit a
second 13-row float costs more than the separation is worth.

Columns, all neutral prompt at k=1:
  happy / error  full-correct rate per path (the gap is their difference)
  gap            cleanup-on-exception gap, and the same gap with every task on which the model
                 attempted `with` removed -- the check that the method-only mocks are not
                 manufacturing the effect
  silent         output-correct-yet-violating, over all 98 scenarios and over only the
                 output-correct error-path scenarios that could actually leak
  db / fs / lock per-family gap
  idiom          how many of the 48 candidates used `with`, `try/finally`, or neither

Writes out/tables/panel.tex.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from idiom_stats import (BASE, CONDITIONS, FAMILIES, LABEL, ORDER,  # noqa: E402
                         family_gaps, load_condition, solution_src, idiom, gap_and_leaks)


def main() -> int:
    tags = CONDITIONS["neutral"]
    rows, tag_of = load_condition(tags)
    fam = family_gaps(tags)

    by_model = defaultdict(list)
    for r in rows:
        if r["model"] not in BASE:
            by_model[r["model"]].append(r)

    lines = [r"\begin{tabular}{lrrrrrrrrrrrr}", r"\toprule",
             r"& \multicolumn{2}{c}{Full-correct (\%)} & \multicolumn{2}{c}{Gap (pp)} "
             r"& \multicolumn{2}{c}{Silent (\%)} & \multicolumn{3}{c}{Gap by family (pp)} "
             r"& \multicolumn{3}{c}{Idiom (n/48)} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-10}"
             r"\cmidrule(lr){11-13}",
             r"Model & happy & error & all & ex.\ \texttt{w.} & all & cond. "
             r"& db & fs & lock & \texttt{with} & \texttt{fin.} & none \\",
             r"\midrule"]
    tot = defaultdict(int)
    for m in ORDER:
        mrows = by_model.get(m)
        if not mrows:
            continue
        happy = [r for r in mrows if r["type"] == "happy"]
        err = [r for r in mrows if r["type"] == "error"]
        h = sum(r["full_correct"] for r in happy) / len(happy)
        e = sum(r["full_correct"] for r in err) / len(err)
        s_all = sum(1 for r in mrows if r["output_ok"] and r["violations"]) / len(mrows)
        err_ok = [r for r in err if r["output_ok"]]
        s_cond = (sum(1 for r in err_ok if r["violations"]) / len(err_ok)) if err_ok else 0.0

        counts, with_tasks, seen = defaultdict(int), set(), set()
        for r in mrows:
            key = (r["task_id"], r.get("rep", 0))
            if key in seen:
                continue
            seen.add(key)
            tag = tag_of.get((m, r["task_id"], r.get("rep", 0)))
            src = solution_src(tag, m, r["task_id"], r.get("rep", 0)) if tag else None
            if src is None:
                continue
            k = idiom(src)
            counts[k] += 1
            if k == "with":
                with_tasks.add(r["task_id"])
        for k in ("with", "finally", "plain"):
            tot[k] += counts.get(k, 0)

        gap, _ = gap_and_leaks(mrows)
        gap_x, _ = gap_and_leaks(mrows, exclude=with_tasks)
        g = fam.get(m, {})
        lines.append(
            f"{LABEL.get(m, m)} & {100*h:.0f} & {100*e:.0f} & {gap:.0f} & {gap_x:.0f} & "
            f"{100*s_all:.0f} & {100*s_cond:.0f} & {g.get('db',0):.0f} & "
            f"\\textbf{{{g.get('fs',0):.0f}}} & {g.get('lock',0):.0f} & "
            f"{counts.get('with',0)} & {counts.get('finally',0)} & {counts.get('plain',0)} \\\\")
    lines += [r"\midrule",
              rf"\textbf{{Total}} & -- & -- & -- & -- & -- & -- & -- & -- & -- & "
              rf"\textbf{{{tot['with']}}} & \textbf{{{tot['finally']}}} & "
              rf"\textbf{{{tot['plain']}}} \\",
              r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/panel.tex").write_text("\n".join(lines))
    print("wrote out/tables/panel.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

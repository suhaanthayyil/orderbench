"""Headline ablation table at k=3: per-model instructed and neutral cleanup gap reported as the
mean over three generations, with the generation SD on the neutral gap and a percentile
bootstrap CI over tasks. Overwrites paper-table ablation.tex (run after make_ablation, which
also produces perfamily.tex and the figure).

Reads the k3_*_{neutral,instructed} tags. silent-misuse and leak counts are taken at rep0
(interpretable as counts over the 48 error scenarios). Writes out/tables/ablation.tex.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orderbench.metrics import _bootstrap_ci  # noqa: E402

NEUT = ["k3_claude_neutral", "k3_gemma_neutral", "k3_gpt_neutral", "k3_gpt2_neutral",
        "k3_qwen25coder_neutral", "k3_deepseekcoder_neutral"]
INSTR = ["k3_claude_instructed", "k3_gemma_instructed", "k3_gpt_instructed", "k3_gpt2_instructed",
         "k3_qwen25coder_instructed", "k3_deepseekcoder_instructed"]
BASE = {"reference", "buggy", "null"}
ORDER = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
         "openai:gpt-5.5", "openai:gpt-5.4-mini", "openai:gpt-5.4-nano",
         "openai:gpt-5", "openai:gpt-5-mini",
         "openai:gpt-4.1", "openai:gpt-4.1-mini", "openai:gpt-4.1-nano", "openai:gpt-4o-mini"]
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "ollama:qwen2.5-coder:7b": "Qwen2.5-Coder 7B", "ollama:deepseek-coder:6.7b": "DeepSeek-Coder 6.7B",
         "openai:gpt-5.5": "GPT-5.5", "openai:gpt-5.4-mini": "GPT-5.4-mini",
         "openai:gpt-5.4-nano": "GPT-5.4-nano", "openai:gpt-5": "GPT-5", "openai:gpt-5-mini": "GPT-5-mini",
         "openai:gpt-4.1": "GPT-4.1", "openai:gpt-4.1-mini": "GPT-4.1-mini",
         "openai:gpt-4.1-nano": "GPT-4.1-nano", "openai:gpt-4o-mini": "GPT-4o-mini"}


def load(tags):
    rows, seen = [], set()
    for t in tags:
        p = ROOT / "results" / t / "rows.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        fresh = {r["model"] for r in data if r["model"] not in BASE} - seen
        rows += [r for r in data if r["model"] in fresh]
        seen |= fresh
    return rows


def gaps_by_rep(rows, model):
    by = defaultdict(lambda: {"h": [], "e": []})
    for r in rows:
        if r["model"] != model:
            continue
        by[r.get("rep", 0)]["h" if r["type"] == "happy" else "e"].append(r["full_correct"])
    out = []
    for rep in sorted(by):
        d = by[rep]
        h = sum(d["h"]) / len(d["h"]) if d["h"] else 0.0
        e = sum(d["e"]) / len(d["e"]) if d["e"] else 0.0
        out.append(100 * (h - e))
    return out


def task_gap_means(rows, model):
    by = defaultdict(lambda: {"h": [], "e": []})
    for r in rows:
        if r["model"] != model:
            continue
        by[r["task_id"]]["h" if r["type"] == "happy" else "e"].append(r["full_correct"])
    means = []
    for t, d in by.items():
        if d["h"] and d["e"]:
            means.append(sum(d["h"]) / len(d["h"]) - sum(d["e"]) / len(d["e"]))
    return means


def main() -> int:
    neut, instr = load(NEUT), load(INSTR)
    models = [m for m in ORDER if any(r["model"] == m for r in neut)]

    lines = [r"\begin{tabular}{lrcrr}", r"\toprule",
             r"& Instr. & \multicolumn{3}{c}{Neutral (not told)} \\",
             r"\cmidrule(lr){2-2}\cmidrule(lr){3-5}",
             r"Model & gap & gap [95\% CI] & silent & leaks \\",
             r" & (pp) & (pp) & (\%) & (n) \\", r"\midrule"]
    for m in models:
        ig = gaps_by_rep(instr, m)
        ng = gaps_by_rep(neut, m)
        imean = st.mean(ig) if ig else 0.0
        nmean = st.mean(ng) if ng else 0.0
        nsd = st.pstdev(ng) if len(ng) > 1 else 0.0
        ci = _bootstrap_ci(task_gap_means(neut, m))
        # rep0 counts for silent + leaks
        r0 = [r for r in neut if r["model"] == m and r.get("rep", 0) == 0]
        n0 = len(r0)
        silent = sum(1 for r in r0 if r["output_ok"] and r["violations"])
        leaks = sum(len(r["violations"]) for r in r0)
        lines.append(
            f"{LABEL[m]} & {imean:.0f} & "
            f"\\textbf{{{nmean:.0f}}}$\\pm${nsd:.0f} [{100*ci[0]:.0f},\\,{100*ci[1]:.0f}] & "
            f"{round(100*silent/n0)} & {leaks} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/ablation.tex").write_text("\n".join(lines))
    print(f"wrote out/tables/ablation.tex (k=3 mean +/- SD, {len(models)} models)")
    for m in models:
        ng = gaps_by_rep(neut, m)
        print(f"  {LABEL[m]:18} neutral k3 mean={st.mean(ng):.1f} sd={st.pstdev(ng) if len(ng)>1 else 0:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

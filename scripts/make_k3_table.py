"""k=1 vs k=3 robustness table: per-model neutral cleanup gap, mean +/- SD over generations.

Reads the k3 neutral tags (which carry rep0,rep1,rep2). For each model computes the cleanup
gap (happy_fc - error_fc) per rep, then reports the k=1 value (rep0), the k=3 mean, and the
SD across the three generations -- the direct answer to "could k=1 be a sampling fluke?".
Writes out/tables/k3.tex.
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAGS = ["k3_claude_neutral", "k3_gemma_neutral", "k3_gpt_neutral", "k3_gpt2_neutral"]
BASE = {"reference", "buggy", "null"}
ORDER = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
         "openai:gpt-5.5", "openai:gpt-5.4-mini", "openai:gpt-5.4-nano",
         "openai:gpt-5", "openai:gpt-5-mini",
         "openai:gpt-4.1", "openai:gpt-4.1-mini", "openai:gpt-4.1-nano", "openai:gpt-4o-mini"]
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "openai:gpt-5.5": "GPT-5.5", "openai:gpt-5.4-mini": "GPT-5.4-mini",
         "openai:gpt-5.4-nano": "GPT-5.4-nano", "openai:gpt-5": "GPT-5", "openai:gpt-5-mini": "GPT-5-mini",
         "openai:gpt-4.1": "GPT-4.1", "openai:gpt-4.1-mini": "GPT-4.1-mini",
         "openai:gpt-4.1-nano": "GPT-4.1-nano", "openai:gpt-4o-mini": "GPT-4o-mini"}


def gap_per_rep(rows):
    """model -> {rep -> gap_pp}."""
    agg = defaultdict(lambda: defaultdict(lambda: {"h": [], "e": []}))
    for r in rows:
        if r["model"] in BASE:
            continue
        d = agg[r["model"]][r.get("rep", 0)]
        (d["h"] if r["type"] == "happy" else d["e"]).append(r["full_correct"])
    out = {}
    for m, reps in agg.items():
        gaps = {}
        for rep, d in reps.items():
            h = sum(d["h"]) / len(d["h"]) if d["h"] else 0.0
            e = sum(d["e"]) / len(d["e"]) if d["e"] else 0.0
            gaps[rep] = 100 * (h - e)
        out[m] = gaps
    return out


def main() -> int:
    rows = []
    for t in TAGS:
        p = ROOT / "results" / t / "rows.json"
        if p.exists():
            rows += json.loads(p.read_text())
    gaps = gap_per_rep(rows)
    models = [m for m in ORDER if m in gaps]

    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"& Gap $k{=}1$ & Gap $k{=}3$ & SD over \\",
             r"Model & (pp) & mean (pp) & gens (pp) \\", r"\midrule"]
    print(f"{'model':16} k1   k3mean  sd   reps")
    for m in models:
        g = gaps[m]
        reps = sorted(g)
        vals = [g[r] for r in reps]
        k1 = g.get(0, vals[0])
        mean = st.mean(vals)
        sd = st.pstdev(vals) if len(vals) > 1 else 0.0
        lines.append(f"{LABEL[m]} & {k1:.0f} & {mean:.1f} & {sd:.1f} \\\\")
        print(f"  {LABEL[m]:16} {k1:4.0f} {mean:6.1f} {sd:5.1f}  {len(reps)}")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/k3.tex").write_text("\n".join(lines))
    print(f"\nmodels with k>=1 data: {len(models)}; wrote out/tables/k3.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

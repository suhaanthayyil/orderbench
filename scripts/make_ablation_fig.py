"""Regenerate the headline ablation figure (ablation_gap.png) from k=3 data, with error bars.

Grouped bars per model: instructed-prompt cleanup gap vs neutral-prompt gap, each the mean over
k=3 generations; the neutral bar carries its generation SD as an error bar. Writes both
out/figures/ and the local paper/figures/ (gitignored) so the paper picks it up.
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NEUT = ["k3_claude_neutral", "k3_gemma_neutral", "k3_gpt_neutral", "k3_gpt2_neutral"]
INSTR = ["k3_claude_instructed", "k3_gemma_instructed", "k3_gpt_instructed", "k3_gpt2_instructed"]
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


def main() -> int:
    neut, instr = load(NEUT), load(INSTR)
    models = [m for m in ORDER if any(r["model"] == m for r in neut)]
    im = [st.mean(gaps_by_rep(instr, m)) for m in models]
    nm = [st.mean(gaps_by_rep(neut, m)) for m in models]
    nsd = [st.pstdev(gaps_by_rep(neut, m)) if len(gaps_by_rep(neut, m)) > 1 else 0 for m in models]

    x = range(len(models))
    fig, ax = plt.subplots(figsize=(10.5, 3.4))
    ax.bar([i - 0.21 for i in x], im, width=0.4, label="instructed", color="#6baed6")
    ax.bar([i + 0.21 for i in x], nm, width=0.4, yerr=nsd, capsize=3, label="neutral",
           color="#fb6a4a", error_kw={"elinewidth": 0.9})
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_xticks(list(x))
    ax.set_xticklabels([LABEL[m] for m in models], rotation=35, ha="right", fontsize=8.5)
    ax.set_ylabel("cleanup-on-exception gap (pp)", fontsize=9)
    ax.legend(fontsize=9, frameon=False, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    for out in [ROOT / "out/figures/ablation_gap.png", ROOT / "paper/figures/ablation_gap.png"]:
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"wrote ablation_gap.png (k=3, {len(models)} models, neutral error bars)")
    print("  neutral k3 means:", {LABEL[m]: round(v) for m, v in zip(models, nm)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

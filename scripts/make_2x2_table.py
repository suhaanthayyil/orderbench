"""2x2 prompt-cue ablation table: cleanup gap under each cue combination.

Four conditions cross the two cleanup cues:
  neutral   = (task cue off, api-doc cue off)     instructed = (task on,  api on)
  api-only  = (task off,     api on)              task-only  = (task on,  api off)
For each model we report the neutral cleanup gap (happy_fc - error_fc, rep0) under each
condition. This isolates which cue drives cleanup: the API documentation, the task sentence,
or their redundancy. Writes out/tables/cue2x2.tex.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = {"reference", "buggy", "null"}

CONDITIONS = {
    "neutral":    ["panel_neutral", "gpt_neutral", "gpt2_neutral"],
    "api-only":   ["apionly_claude", "apionly_gpt", "apionly_gpt2"],
    "task-only":  ["taskonly_claude", "taskonly_gpt", "taskonly_gpt2"],
    "instructed": ["panel", "gpt_instructed", "gpt2_instructed"],
}
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


def gaps_for(tags):
    """model -> gap_pp (rep0) merged across the tags for one condition."""
    agg = defaultdict(lambda: {"h": [], "e": []})
    for tag in tags:
        p = ROOT / "results" / tag / "rows.json"
        if not p.exists():
            continue
        for r in json.loads(p.read_text()):
            if r["model"] in BASE or r.get("rep", 0) != 0:
                continue
            (agg[r["model"]]["h"] if r["type"] == "happy" else agg[r["model"]]["e"]).append(
                r["full_correct"])
    out = {}
    for m, d in agg.items():
        # round happy/error rates to 4 dp before differencing, matching metrics.cleanup_gap,
        # so the neutral column agrees with the ablation table on rounding-edge values.
        h = round(sum(d["h"]) / len(d["h"]), 4) if d["h"] else 0.0
        e = round(sum(d["e"]) / len(d["e"]), 4) if d["e"] else 0.0
        out[m] = 100 * round(h - e, 4)  # match metrics.cleanup_gap rounding exactly
    return out


def main() -> int:
    cond_gaps = {c: gaps_for(tags) for c, tags in CONDITIONS.items()}
    models = [m for m in ORDER if m in cond_gaps["neutral"]]

    cols = ["neutral", "api-only", "task-only", "instructed"]
    head = " & ".join(c.replace("-", "-") for c in cols)
    lines = [r"\begin{tabular}{lrrrr}", r"\toprule",
             rf"Model & {head} \\",
             r" & (pp) & (pp) & (pp) & (pp) \\", r"\midrule"]
    print(f"{'model':16} " + " ".join(f"{c:>10}" for c in cols))
    for m in models:
        vals = [cond_gaps[c].get(m) for c in cols]
        cells = " & ".join(f"{v:.0f}" if v is not None else "--" for v in vals)
        lines.append(f"{LABEL[m]} & {cells} \\\\")
        print(f"  {LABEL[m]:16} " + " ".join(
            (f"{v:10.0f}" if v is not None else f"{'--':>10}") for v in vals))
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/cue2x2.tex").write_text("\n".join(lines))

    # quick aggregate read: mean gap per condition over models with all four present
    full = [m for m in models if all(cond_gaps[c].get(m) is not None for c in cols)]
    if full:
        print("\nmean gap (pp) over models with all 4 conditions:")
        for c in cols:
            print(f"  {c:11}: {sum(cond_gaps[c][m] for m in full)/len(full):.1f}")
    print(f"\nwrote out/tables/cue2x2.tex ({len(models)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

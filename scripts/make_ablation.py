"""Build the ablation figure + tables (cross-vendor, with CIs + per-family).

Reads results/{panel,panel_neutral,gpt_instructed,gpt_neutral}; writes:
  out/figures/ablation_gap.png
  out/tables/ablation.tex     (per-model instructed vs neutral gap, 95% CI, silent, leaks)
  out/tables/perfamily.tex    (per-model neutral gap by resource family db/fs/lock)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.plots import ablation_figure  # noqa: E402

MODELS = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
          "openai:gpt-5.5", "openai:gpt-5.4-mini", "openai:gpt-5.4-nano",
          "openai:gpt-5", "openai:gpt-5-mini",
          "openai:gpt-4.1", "openai:gpt-4.1-mini", "openai:gpt-4.1-nano", "openai:gpt-4o-mini"]
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "openai:gpt-5.5": "GPT-5.5", "openai:gpt-5.4-mini": "GPT-5.4-mini",
         "openai:gpt-5.4-nano": "GPT-5.4-nano", "openai:gpt-5": "GPT-5", "openai:gpt-5-mini": "GPT-5-mini",
         "openai:gpt-4.1": "GPT-4.1", "openai:gpt-4.1-mini": "GPT-4.1-mini",
         "openai:gpt-4.1-nano": "GPT-4.1-nano", "openai:gpt-4o-mini": "GPT-4o-mini"}


def _merge(*paths):
    models = {}
    for p in paths:
        p = ROOT / p
        if p.exists():
            models.update(json.loads(p.read_text())["models"])
    return {"models": models}


def _rows(*paths):
    rows = []
    for p in paths:
        p = ROOT / p
        if p.exists():
            rows += json.loads(p.read_text())
    return rows


def main() -> int:
    ins = _merge("results/panel/results.json", "results/gpt_instructed/results.json", "results/gpt2_instructed/results.json")
    neu = _merge("results/panel_neutral/results.json", "results/gpt_neutral/results.json", "results/gpt2_neutral/results.json")
    models = [m for m in MODELS if m in neu["models"]]
    (ROOT / "out/figures").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    ablation_figure(ins, neu, ROOT / "out/figures/ablation_gap.png", models=models)

    im, nm = ins["models"], neu["models"]
    pc = lambda x: f"{100 * x:.0f}"  # noqa: E731

    # ---- main ablation table (with 95% CI on the neutral gap) ----
    lines = [
        r"\begin{tabular}{lrcrr}",
        r"\toprule",
        r"& Instr. & \multicolumn{3}{c}{Neutral (not told)} \\",
        r"\cmidrule(lr){2-2}\cmidrule(lr){3-5}",
        r"Model & gap & gap [95\% CI] & silent & leaks \\",
        r" & (pp) & (pp) & (\%) & (n) \\",
        r"\midrule",
    ]
    for m in models:
        n = nm[m]
        ci = n["ci"]["cleanup_gap"]
        leaks = sum(n["per_class"].values())
        lines.append(
            f"{LABEL[m]} & {pc(im[m]['cleanup_gap'])} & "
            f"\\textbf{{{pc(n['cleanup_gap'])}}} [{pc(ci[0])},\\,{pc(ci[1])}] & "
            f"{pc(n['silent_misuse_rate'])} & {leaks} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables/ablation.tex").write_text("\n".join(lines))

    # ---- per-family neutral cleanup gap ----
    rows = _rows("results/panel_neutral/rows.json", "results/gpt_neutral/rows.json", "results/gpt2_neutral/rows.json")
    agg = defaultdict(lambda: {"h": [], "e": []})
    for r in rows:
        k = (r["model"], r["family"])
        (agg[k]["h"] if r["type"] == "happy" else agg[k]["e"]).append(r["full_correct"])

    def gap(m, f):
        a = agg[(m, f)]
        h = sum(a["h"]) / len(a["h"]) if a["h"] else 0.0
        e = sum(a["e"]) / len(a["e"]) if a["e"] else 0.0
        return 100 * (h - e)

    flines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"& \multicolumn{3}{c}{Neutral cleanup gap (pp)} \\",
        r"\cmidrule(lr){2-4}",
        r"Model & db (conn.) & fs (handle) & lock \\",
        r"\midrule",
    ]
    for m in models:
        flines.append(f"{LABEL[m]} & {gap(m,'db'):.0f} & "
                      f"\\textbf{{{gap(m,'fs'):.0f}}} & {gap(m,'lock'):.0f} \\\\")
    flines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables/perfamily.tex").write_text("\n".join(flines))

    print("wrote ablation.tex (with CIs) + perfamily.tex + ablation_gap.png")
    print("\nper-family neutral gap (pp):  model            db    fs   lock")
    for m in models:
        print(f"  {LABEL[m]:16} {gap(m,'db'):6.0f} {gap(m,'fs'):5.0f} {gap(m,'lock'):6.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

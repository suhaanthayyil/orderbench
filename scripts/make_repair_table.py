"""Combined repair-experiment table across all repair runs (out/tables/repair.tex)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPAIR_TAGS = ["repair_claude", "repair_gpt", "repair_gemma"]
ORDER = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
         "openai:gpt-5.4-mini", "openai:gpt-5.4-nano", "openai:gpt-5",
         "openai:gpt-4.1", "openai:gpt-4.1-mini", "openai:gpt-4.1-nano", "openai:gpt-4o-mini"]
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "openai:gpt-5.4-mini": "GPT-5.4-mini", "openai:gpt-5.4-nano": "GPT-5.4-nano",
         "openai:gpt-5": "GPT-5", "openai:gpt-4.1": "GPT-4.1", "openai:gpt-4.1-mini": "GPT-4.1-mini",
         "openai:gpt-4.1-nano": "GPT-4.1-nano", "openai:gpt-4o-mini": "GPT-4o-mini"}


def main() -> int:
    data = {}
    for tag in REPAIR_TAGS:
        p = ROOT / "results" / tag / "repair.json"
        if p.exists():
            data.update(json.loads(p.read_text()))
    models = [m for m in ORDER if m in data and data[m]["candidates"] > 0]

    tex = [r"\begin{tabular}{lrrr}", r"\toprule",
           r"Model & Leaky (n) & Repaired & Fix rate \\", r"\midrule"]
    tc = tf = 0
    print(f"{'model':16} leaky fixed rate")
    for m in models:
        d = data[m]; tc += d["candidates"]; tf += d["fixed"]
        rate = 100 * d["fixed"] / d["candidates"] if d["candidates"] else 0
        tex.append(f"{LABEL[m]} & {d['candidates']} & {d['fixed']} & {rate:.0f}\\% \\\\")
        print(f"  {LABEL[m]:16} {d['candidates']:5} {d['fixed']:5} {rate:4.0f}%")
    tex += [r"\midrule",
            rf"\textbf{{Total}} & {tc} & {tf} & \textbf{{{100*tf/tc if tc else 0:.0f}\%}} \\",
            r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/repair.tex").write_text("\n".join(tex))
    print(f"\ntotal: {tf}/{tc} repaired ({100*tf/tc if tc else 0:.0f}%); wrote out/tables/repair.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Extended-analysis tables for the paper, computed directly from neutral-condition rows.

Produces (into out/tables/, and also copied to paper/tables/ by the caller):
  outputonly.tex   -- C1: output-only oracle vs OrderBench (proves the title)
  neutral_class.tex-- C2: full 13-model neutral per-violation-class table
  outvscleanup.tex -- C8: separated output-error vs cleanup-error rates

Reads the merged neutral rows for the full 13-model panel. Prefers k=3 tags when present,
falling back to the original k=1 tags, so it works before and after the k=3 runs land.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (k3 tag, fallback k1 tag) pairs covering the whole neutral panel.
NEUTRAL_TAGS = [
    ("k3_claude_neutral", "panel_neutral"),
    ("k3_gemma_neutral", "panel_neutral"),
    ("k3_gpt_neutral", "gpt_neutral"),
    ("k3_gpt2_neutral", "gpt2_neutral"),
]
BASE = {"reference", "buggy", "null"}
CLASSES = ["order", "guard", "double", "unclosed"]
MODEL_ORDER = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
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


def load_neutral_rows() -> list[dict]:
    """Merge neutral rows; for each tag-pair use the k3 tag if it has data, else k1."""
    rows: list[dict] = []
    seen_models: set[str] = set()
    for k3, k1 in NEUTRAL_TAGS:
        for tag in (k3, k1):
            p = ROOT / "results" / tag / "rows.json"
            if not p.exists():
                continue
            data = [r for r in json.loads(p.read_text()) if r.get("rep", 0) == 0]
            models = {r["model"] for r in data if r["model"] not in BASE}
            # Only take models we have not already collected (avoid double counting
            # claude+gemma which share panel_neutral).
            fresh = models - seen_models
            if not fresh:
                continue
            rows += [r for r in data if r["model"] in fresh]
            seen_models |= fresh
            break
        else:
            # Neither the k=3 tag nor its k=1 fallback exists: those models are silently
            # missing from every table built here, so say so.
            print(f"  WARNING: neither {k3!r} nor {k1!r} has rows.json -- models absent",
                  file=sys.stderr)
    return rows


def present_models(rows) -> list[str]:
    have = {r["model"] for r in rows}
    return [m for m in MODEL_ORDER if m in have]


def main() -> int:
    rows = load_neutral_rows()
    models = present_models(rows)
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["model"] in BASE:
            continue
        by_model[r["model"]].append(r)

    pct = lambda x: f"{100 * x:.0f}"  # noqa: E731

    # ---- C1: output-only oracle vs OrderBench ----
    c1 = [
        r"\begin{tabular}{lrrr}", r"\toprule",
        r"& Output-only & OrderBench & Silent leaks \\",
        r"Model & accepts (\%) & accepts (\%) & accepted (n) \\",
        r"\midrule",
    ]
    tot_silent = 0
    for m in models:
        rs = by_model[m]
        n = len(rs)
        out_ok = sum(1 for r in rs if r["output_ok"]) / n
        full_ok = sum(1 for r in rs if r["full_correct"]) / n
        silent = sum(1 for r in rs if r["output_ok"] and r["violations"])
        tot_silent += silent
        c1.append(f"{LABEL[m]} & {pct(out_ok)} & {pct(full_ok)} & {silent} \\\\")
    c1 += [r"\midrule",
           rf"\textbf{{Total}} & -- & -- & \textbf{{{tot_silent}}} \\",
           r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables/outputonly.tex").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/outputonly.tex").write_text("\n".join(c1))

    # ---- C2: full neutral per-class violation table (all 13 models) ----
    c2 = [r"\begin{tabular}{lrrrr}", r"\toprule",
          r"Model & order & guard & double & unclosed \\", r"\midrule"]
    totals = Counter()
    for m in models:
        cc = Counter()
        for r in by_model[m]:
            for v in r["violations"]:
                cc[v] += 1
                totals[v] += 1
        c2.append(f"{LABEL[m]} & " + " & ".join(str(cc.get(c, 0)) for c in CLASSES) + r" \\")
    c2 += [r"\midrule",
           r"\textbf{Total} & " + " & ".join(rf"\textbf{{{totals.get(c,0)}}}" for c in CLASSES) + r" \\",
           r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables/neutral_class.tex").write_text("\n".join(c2))

    # ---- C8: what the gap is made of, plus silent misuse on its proper denominator ----
    # Folds in the output-only-vs-OrderBench comparison so the paper carries one 13-model
    # neutral breakdown instead of two. The gap is a difference of two full-correct rates, so
    # a zero gap can mean success on both paths or failure on both; showing the rates makes
    # which one visible. And the published silent-misuse rate divides by all 98 scenarios,
    # which flatters a model that simply gets fewer outputs right, since it had fewer chances
    # to be output-correct-yet-leaking -- hence the conditional rate over the output-correct
    # error-path scenarios, the population that could actually leak silently.
    c8 = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
          r"& Happy & Error & Gap & Out-only & \multicolumn{2}{c}{Silent misuse (\%)} \\",
          r"\cmidrule(lr){2-3}\cmidrule(lr){4-4}\cmidrule(lr){5-5}\cmidrule(lr){6-7}",
          r"Model & f.c.\ (\%) & f.c.\ (\%) & (pp) & acc.\ (\%) & all & cond. \\",
          r"\midrule"]
    for m in models:
        rs = by_model[m]
        happy = [r for r in rs if r["type"] == "happy"]
        err = [r for r in rs if r["type"] == "error"]
        h = sum(1 for r in happy if r["full_correct"]) / len(happy) if happy else 0
        e = sum(1 for r in err if r["full_correct"]) / len(err) if err else 0
        out_ok = sum(1 for r in rs if r["output_ok"]) / len(rs)
        silent_all = sum(1 for r in rs if r["output_ok"] and r["violations"]) / len(rs)
        err_ok = [r for r in err if r["output_ok"]]
        silent_cond = (sum(1 for r in err_ok if r["violations"]) / len(err_ok)) if err_ok else 0
        c8.append(f"{LABEL[m]} & {pct(h)} & {pct(e)} & {100*(h-e):.0f} & {pct(out_ok)} & "
                  f"{pct(silent_all)} & {pct(silent_cond)} \\\\")
    c8 += [r"\midrule",
           rf"\textbf{{Total silent}} & -- & -- & -- & -- & \textbf{{{tot_silent}}} & -- \\",
           r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables/pathdecomp.tex").write_text("\n".join(c8))

    print(f"models: {len(models)}  |  total silent leaks (output-only accepts): {tot_silent}")
    print("per-class totals:", dict(totals))
    print("wrote out/tables/{outputonly,neutral_class,pathdecomp}.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

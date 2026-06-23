"""Repair experiment: re-prompt each leaky neutral solution to fix its cleanup, measure fixes.

For every (model, task) whose cached NEUTRAL solution leaks on the error path, we feed the model
its own code with a one-line "release every resource on every path" instruction
(``build_repair_prompt``) and grade the revision. We report, per model: how many leaky
solutions were repaired to clean, and whether any repair regressed the happy-path output.

Usage:
  python scripts/run_repair.py --models claude-code:haiku claude-code:sonnet \
      --source-tags panel_neutral gpt_neutral gpt2_neutral --tag repair
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import orderbench.runner as R  # noqa: E402
from orderbench.harness import load_suite, run_task_safe  # noqa: E402

LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "openai:gpt-4o-mini": "GPT-4o-mini", "openai:gpt-4.1": "GPT-4.1",
         "openai:gpt-4.1-mini": "GPT-4.1-mini", "openai:gpt-4.1-nano": "GPT-4.1-nano",
         "openai:gpt-5": "GPT-5", "openai:gpt-5-mini": "GPT-5-mini",
         "openai:gpt-5.4-mini": "GPT-5.4-mini", "openai:gpt-5.4-nano": "GPT-5.4-nano",
         "openai:gpt-5.5": "GPT-5.5"}


def sanitize(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def find_original(model: str, task, source_tags) -> Path | None:
    for tag in source_tags:
        p = ROOT / "results" / tag / "solutions" / sanitize(model) / f"{task.id}__rep0.py"
        if p.exists():
            return p
    return None


def grade(task, path) -> list:
    return list(run_task_safe(task, path))


def leaks(results) -> bool:
    return any(r.type == "error" and r.violations for r in results)


def clean(results) -> bool:
    return all(not r.violations for r in results)


def happy_ok(results) -> bool:
    return all(r.output_ok for r in results if r.type == "happy")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--source-tags", nargs="+",
                    default=["panel_neutral", "gpt_neutral", "gpt2_neutral"])
    ap.add_argument("--tag", default="repair")
    args = ap.parse_args()

    tasks = load_suite(str(ROOT / "tasks"))
    out_root = ROOT / "results" / args.tag
    summary = {}
    for model in args.models:
        adapter = R.resolve_adapter(model)
        sol_dir = out_root / "solutions" / sanitize(model)
        sol_dir.mkdir(parents=True, exist_ok=True)
        candidates = fixed = regressed = 0
        for task in tasks:
            orig = find_original(model, task, args.source_tags)
            if orig is None:
                continue
            if not leaks(grade(task, orig)):
                continue
            candidates += 1
            R._REPAIR_PROMPT = R.build_repair_prompt(task, orig.read_text())
            try:
                repaired = adapter(task)
            finally:
                R._REPAIR_PROMPT = None
            rpath = sol_dir / f"{task.id}__repaired.py"
            rpath.write_text(repaired)
            res = grade(task, rpath)
            if clean(res) and happy_ok(res):
                fixed += 1
            elif not happy_ok(res):
                regressed += 1
        summary[model] = {"candidates": candidates, "fixed": fixed, "regressed": regressed,
                          "fix_rate": (fixed / candidates) if candidates else 0.0}
        print(f"{model}: {fixed}/{candidates} leaks repaired, {regressed} output regressions")

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "repair.json").write_text(json.dumps(summary, indent=2))

    # ---- LaTeX table ----
    tex = [r"\begin{tabular}{lrrr}", r"\toprule",
           r"Model & Leaky (n) & Repaired & Fix rate \\", r"\midrule"]
    tot_c = tot_f = 0
    for m, d in summary.items():
        tot_c += d["candidates"]; tot_f += d["fixed"]
        tex.append(f"{LABEL.get(m, m)} & {d['candidates']} & {d['fixed']} & "
                   f"{100 * d['fix_rate']:.0f}\\% \\\\")
    tex += [r"\midrule",
            rf"\textbf{{Total}} & {tot_c} & {tot_f} & "
            rf"\textbf{{{(100 * tot_f / tot_c) if tot_c else 0:.0f}\%}} \\",
            r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out" / "tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out" / "tables" / "repair.tex").write_text("\n".join(tex))
    print(f"\noverall: {tot_f}/{tot_c} repaired; wrote out/tables/repair.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

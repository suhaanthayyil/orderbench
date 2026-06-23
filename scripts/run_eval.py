"""Run one or more model adapters across the whole task suite and write results.

Usage:
  python scripts/run_eval.py --models reference buggy null
  python scripts/run_eval.py --models anthropic:claude-opus-4-8 --repeats 5

Writes:
  results/<tag>/rows.json       -- every graded scenario row
  results/<tag>/results.json    -- per-model metrics bundle (gap, silent-misuse, CIs)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.harness import load_suite  # noqa: E402
from orderbench.report import results_bundle, write_bundle  # noqa: E402
from orderbench.runner import run_model, write_rows  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["reference", "buggy", "null"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--tasks", default=str(ROOT / "tasks"))
    ap.add_argument("--tag", default="demo")
    ap.add_argument("--prompt-mode", choices=["instructed", "neutral"], default="instructed",
                    help="TASK-sentence cue: instructed (task tells the model to clean up) "
                         "or neutral (task cleanup sentence stripped)")
    ap.add_argument("--api-doc-mode", choices=["full", "neutral", "auto"], default="auto",
                    help="API-DOC cue: full (doc states cleanup obligation), neutral (doc "
                         "only lists methods), or auto (tracks --prompt-mode). Crossing the two "
                         "cues gives the 2x2 ablation: neutral / api-only / task-only / instructed")
    args = ap.parse_args()
    api_doc_mode = None if args.api_doc_mode == "auto" else args.api_doc_mode

    tasks = load_suite(args.tasks)
    print(f"loaded {len(tasks)} tasks")
    out_root = ROOT / "results" / args.tag
    sols_dir = out_root / "solutions"

    print(f"prompt mode: {args.prompt_mode}  api-doc mode: {args.api_doc_mode}")
    rows_by_model = {}
    all_rows = []
    for model in args.models:
        rows = run_model(model, tasks, sols_dir, repeats=args.repeats,
                         prompt_mode=args.prompt_mode, api_doc_mode=api_doc_mode)
        rows_by_model[model] = rows
        all_rows.extend(rows)
        print(f"  {model}: {len(rows)} scenario rows")

    write_rows(all_rows, out_root / "rows.json")
    bundle = results_bundle(rows_by_model)
    write_bundle(bundle, out_root / "results.json")

    print("\n=== summary ===")
    for m, d in bundle["models"].items():
        print(f"{m:>26}: happy={d['happy_correct']:.2f} error={d['error_correct']:.2f} "
              f"gap={d['cleanup_gap']:.2f} silent_misuse={d['silent_misuse_rate']:.2f}")
    print(f"\nwrote {out_root/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

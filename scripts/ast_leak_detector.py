"""A simple static (AST) cleanup-leak detector, and a comparison vs OrderBench's runtime oracle.

The detector flags a candidate function as leak-prone when it acquires a resource
(``x = pool.connect()`` / ``fs.open(...)`` / ``env.lock.acquire()``) but does NOT guard the
release with ``try/finally`` or a ``with`` block -- the dominant cleanup-on-exception bug. It is
a deliberately ordinary static checker: it cannot execute the code, so it misses leaks hidden
behind a try/finally that does not actually release, and false-positives on releases it cannot
prove safe. The point of the comparison is that OrderBench's *runtime* oracle catches exactly
the exception-path leaks that an output-only test suite never sees and a static checker only
partially sees.

Run over the committed neutral solutions; writes out/tables/static.tex (method comparison).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACQUIRE_ATTRS = {"connect", "open", "acquire"}
RELEASE_ATTRS = {"close", "release"}
NEUTRAL_TAGS = ["panel_neutral", "gpt_neutral", "gpt2_neutral",
                "k3_claude_neutral", "k3_gpt_neutral", "k3_gpt2_neutral", "k3_gemma_neutral"]
BASE = {"reference", "buggy", "null"}


def detects_leak(src: str) -> bool | None:
    """Static verdict: True=leak-prone, False=looks guarded, None=unparseable."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
    if fn is None:
        return None
    acquires = releases = 0
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in ACQUIRE_ATTRS:
                acquires += 1
            elif n.func.attr in RELEASE_ATTRS:
                releases += 1
    if acquires == 0:
        return False  # nothing acquired -> nothing to leak
    guarded = any(
        isinstance(n, ast.With) or isinstance(n, ast.AsyncWith)
        or (isinstance(n, ast.Try) and n.finalbody)
        for n in ast.walk(fn)
    )
    # leak-prone if it acquires a resource and the release is not guarded by try/finally / with
    return not guarded


def main() -> int:
    # OrderBench runtime ground truth (rep0): a (model,task) leaks if an error scenario violated.
    runtime_leak: dict[tuple, bool] = {}
    seen_models: set[str] = set()
    for tag in NEUTRAL_TAGS:
        p = ROOT / "results" / tag / "rows.json"
        if not p.exists():
            continue
        for r in json.loads(p.read_text()):
            if r["model"] in BASE or r.get("rep", 0) != 0:
                continue
            key = (r["model"], r["task_id"])
            if r["type"] == "error" and r["violations"]:
                runtime_leak[key] = True
            runtime_leak.setdefault(key, False)
            seen_models.add(r["model"])

    # Static verdict over the cached rep0 solutions (dedup (model,task) across overlapping tags).
    tp = fp = tn = fn = unparsed = 0
    done: set[tuple] = set()
    for tag in NEUTRAL_TAGS:
        soldir = ROOT / "results" / tag / "solutions"
        if not soldir.exists():
            continue
        for mdir in soldir.iterdir():
            for f in mdir.glob("*__rep0.py"):
                model = next((m for m in seen_models if m.replace(":", "_").replace("/", "_")
                              == mdir.name), None)
                task_id = f.name.replace("__rep0.py", "")
                key = (model, task_id)
                if model is None or key not in runtime_leak or key in done:
                    continue
                done.add(key)
                static = detects_leak(f.read_text())
                truth = runtime_leak[key]
                if static is None:
                    unparsed += 1
                    continue
                if static and truth:
                    tp += 1
                elif static and not truth:
                    fp += 1
                elif (not static) and truth:
                    fn += 1
                else:
                    tn += 1

    leaks = tp + fn
    recall = tp / leaks if leaks else 0.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    print(f"static detector vs OrderBench (rep0 neutral solutions):")
    print(f"  runtime leaks (ground truth): {leaks}")
    print(f"  TP={tp} FN={fn} FP={fp} TN={tn} unparsed={unparsed}")
    print(f"  recall (exception leaks caught): {recall:.0%}   false-positive rate: {fp_rate:.0%}")

    tex = [r"\begin{tabular}{lccc}", r"\toprule",
           r"Method & Catches wrong & Catches exception & False \\",
           r" & output? & leak? & positives? \\", r"\midrule",
           r"Output-only tests & \cmark & \xmark & none \\",
           rf"Static AST checker & partial & partial ({recall*100:.0f}\% recall) & "
           rf"{('low' if fp_rate < 0.1 else 'some')} ({fp_rate*100:.0f}\%) \\",
           r"\textbf{OrderBench} & \cmark & \cmark (exact) & none \\",
           r"\bottomrule", r"\end{tabular}"]
    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/static.tex").write_text("\n".join(tex))
    print("wrote out/tables/static.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

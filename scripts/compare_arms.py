"""Compare an alternative experimental arm against the published neutral baseline.

Two arms are reported:

* ``cm``     -- the context-manager ablation. Same neutral prompt, but the instrumented
                resources expose ``__enter__``/``__exit__`` and the API doc lists the protocol
                as a capability. Tests whether the method-only interface was suppressing a
                cleanup idiom models would otherwise have used.
* ``parity`` -- the harness-parity arm. Same method-only mocks and same neutral prompt, but
                the Claude Code CLI's own agent system prompt is replaced by a minimal one,
                so the Claude arm carries system context comparable to the bare-API arms.

For each model it prints the baseline gap, the arm's gap, the delta, and the idiom mix, so the
claim in the paper is a measured contrast rather than an assertion.
"""
from __future__ import annotations

import ast
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = {"reference", "buggy", "null"}
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B"}
ARMS = {
    "cm": {"arm": ["cm_claude_neutral", "cm_gemma_neutral"],
           "base": ["k3_claude_neutral", "k3_gemma_neutral"]},
    "parity": {"arm": ["parity_claude_neutral"],
               "base": ["k3_claude_neutral"]},
}


def sanitize(m): return m.replace(":", "_").replace("/", "_")


def load(tags):
    rows, tag_of, seen = [], {}, set()
    for t in tags:
        p = ROOT / "results" / t / "rows.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        fresh = {r["model"] for r in data if r["model"] not in BASE} - seen
        for r in data:
            if r["model"] in fresh:
                rows.append(r)
                tag_of[(r["model"], r["task_id"], r.get("rep", 0))] = t
        seen |= fresh
    return rows, tag_of


def per_rep_gaps(rows, model):
    by = defaultdict(lambda: {"h": [], "e": []})
    for r in rows:
        if r["model"] == model:
            by[r.get("rep", 0)]["h" if r["type"] == "happy" else "e"].append(r["full_correct"])
    out = []
    for rep in sorted(by):
        d = by[rep]
        if d["h"] and d["e"]:
            out.append(100 * (sum(d["h"]) / len(d["h"]) - sum(d["e"]) / len(d["e"])))
    return out


def idioms(rows, tag_of, model):
    c = defaultdict(int)
    seen = set()
    for r in rows:
        if r["model"] != model:
            continue
        key = (r["task_id"], r.get("rep", 0))
        if key in seen:
            continue
        seen.add(key)
        tag = tag_of.get((model, r["task_id"], r.get("rep", 0)))
        sp = ROOT / "results" / tag / "solutions" / sanitize(model) / f"{r['task_id']}__rep{r.get('rep',0)}.py"
        if not sp.exists():
            continue
        try:
            tree = ast.parse(sp.read_text())
            fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
            if fn is None:
                c["unparsed"] += 1
            elif any(isinstance(n, (ast.With, ast.AsyncWith)) for n in ast.walk(fn)):
                c["with"] += 1
            elif any(isinstance(n, ast.Try) and n.finalbody for n in ast.walk(fn)):
                c["finally"] += 1
            else:
                c["plain"] += 1
        except SyntaxError:
            c["unparsed"] += 1
    return dict(c)


def report(name):
    cfg = ARMS[name]
    arm_rows, arm_tags = load(cfg["arm"])
    base_rows, base_tags = load(cfg["base"])
    models = [m for m in LABEL if any(r["model"] == m for r in arm_rows)]
    if not models:
        print(f"\n=== {name} === no data yet")
        return {}
    print(f"\n=== {name} arm vs published neutral baseline ===")
    print(f"{'model':16s} {'base gap':>9s} {'arm gap':>9s} {'delta':>7s} "
          f"{'arm leaks':>10s} | idiom mix (arm)")
    out = {}
    for m in models:
        b, a = per_rep_gaps(base_rows, m), per_rep_gaps(arm_rows, m)
        if not b or not a:
            continue
        bl = sum(1 for r in base_rows if r["model"] == m and r["type"] == "error"
                 and "unclosed" in r["violations"])
        al = sum(1 for r in arm_rows if r["model"] == m and r["type"] == "error"
                 and "unclosed" in r["violations"])
        im = idioms(arm_rows, arm_tags, m)
        out[m] = {"base_gap": st.mean(b), "arm_gap": st.mean(a),
                  "base_sd": st.pstdev(b), "arm_sd": st.pstdev(a),
                  "base_leaks": bl, "arm_leaks": al, "arm_idioms": im,
                  "base_reps": len(b), "arm_reps": len(a)}
        print(f"{LABEL[m]:16s} {st.mean(b):8.1f}  {st.mean(a):8.1f}  "
              f"{st.mean(a)-st.mean(b):+6.1f}  {al:6d}/{bl:<4d} | {im}")
    return out


def main() -> int:
    res = {name: report(name) for name in ARMS}
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out/arm_comparison.json").write_text(json.dumps(res, indent=2, default=float))
    print("\nwrote out/arm_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

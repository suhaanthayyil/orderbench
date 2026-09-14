"""Which cleanup idiom did each candidate actually reach for, and does the mock's interface bias the gap?

The published mocks are method-only: they expose ``close()`` / ``release()`` and no
``__enter__``/``__exit__``, so ``with resource:`` raises ``TypeError`` (and, for db/fs, the
resource was already registered by ``connect()``/``open()``, so teardown also logs an
``unclosed`` leak). That is a deliberate property -- the candidate must write the cleanup
rather than delegate it -- but it is also a possible confound: a model whose dominant learned
idiom is the context manager could be scored as leaking because its usual safety mechanism was
unavailable, not because it lacks cleanup discipline.

This script measures the confound directly. For every cached candidate it classifies the
guarding idiom (``with`` / ``try...finally`` / unguarded), counts the ``TypeError`` rows a
``with`` attempt produces, and recomputes the cleanup gap and the leak count with every
``with``-attempting task dropped. If the gap survives that exclusion, the interface is not
manufacturing it.

Writes out/tables/idioms.tex and out/idiom_stats.json.
"""
from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = {"reference", "buggy", "null"}
FAMILIES = ("db", "fs", "lock")

# k=1 condition sets (the per-model breakdown tables) and the k=3 headline set.
CONDITIONS = {
    "neutral": ["panel_neutral", "gpt_neutral", "gpt2_neutral"],
    "instructed": ["panel", "gpt_instructed", "gpt2_instructed"],
}
K3_NEUTRAL = ["k3_claude_neutral", "k3_gemma_neutral", "k3_gpt_neutral", "k3_gpt2_neutral",
              "k3_qwen3_neutral", "k3_dsv2_neutral"]

ORDER = ["claude-code:opus", "claude-code:sonnet", "claude-code:haiku", "ollama:gemma4:12b",
         "openai:gpt-5.5", "openai:gpt-5.4-mini", "openai:gpt-5.4-nano",
         "openai:gpt-5", "openai:gpt-5-mini",
         "openai:gpt-4.1", "openai:gpt-4.1-mini", "openai:gpt-4.1-nano", "openai:gpt-4o-mini"]
LABEL = {"claude-code:opus": "Claude Opus", "claude-code:sonnet": "Claude Sonnet",
         "claude-code:haiku": "Claude Haiku", "ollama:gemma4:12b": "gemma 12B",
         "ollama:qwen3-coder:30b": "Qwen3-Coder 30B",
         "ollama:deepseek-coder-v2:16b": "DeepSeek-Coder-V2 16B",
         "openai:gpt-5.5": "GPT-5.5", "openai:gpt-5.4-mini": "GPT-5.4-mini",
         "openai:gpt-5.4-nano": "GPT-5.4-nano", "openai:gpt-5": "GPT-5",
         "openai:gpt-5-mini": "GPT-5-mini", "openai:gpt-4.1": "GPT-4.1",
         "openai:gpt-4.1-mini": "GPT-4.1-mini", "openai:gpt-4.1-nano": "GPT-4.1-nano",
         "openai:gpt-4o-mini": "GPT-4o-mini"}


def sanitize(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def idiom(src: str) -> str:
    """Classify the guarding idiom of a candidate: with / finally / plain / unparsed."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "unparsed"
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
    if fn is None:
        return "unparsed"
    if any(isinstance(n, (ast.With, ast.AsyncWith)) for n in ast.walk(fn)):
        return "with"
    if any(isinstance(n, ast.Try) and n.finalbody for n in ast.walk(fn)):
        return "finally"
    return "plain"


def load_condition(tags):
    """Flat rows plus a (model, task_id, rep) -> source tag index, deduped across tags."""
    rows, tag_of, seen = [], {}, set()
    for tag in tags:
        p = ROOT / "results" / tag / "rows.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        fresh = {r["model"] for r in data if r["model"] not in BASE} - seen
        for r in data:
            if r["model"] not in fresh:
                continue
            rows.append(r)
            tag_of[(r["model"], r["task_id"], r.get("rep", 0))] = tag
        seen |= fresh
    return rows, tag_of


def solution_src(tag, model, task_id, rep):
    p = ROOT / "results" / tag / "solutions" / sanitize(model) / f"{task_id}__rep{rep}.py"
    return p.read_text() if p.exists() else None


def gap_and_leaks(rows, exclude=frozenset()):
    """Cleanup gap in pp and the count of `unclosed` violations on ERROR scenarios only.

    Note this is the error-path leak count (113 across the k=1 neutral panel), not the
    all-scenario `unclosed` total (117); the remaining 4 are happy-path leaks on db tasks
    that still returned the right value.
    """
    h = [r for r in rows if r["type"] == "happy" and r["task_id"] not in exclude]
    e = [r for r in rows if r["type"] == "error" and r["task_id"] not in exclude]
    if not h or not e:
        return 0.0, 0
    gap = 100 * (sum(r["full_correct"] for r in h) / len(h)
                 - sum(r["full_correct"] for r in e) / len(e))
    leaks = sum(1 for r in e if "unclosed" in r["violations"])
    return gap, leaks


def analyse(tags, label):
    rows, tag_of = load_condition(tags)
    by_model = defaultdict(list)
    for r in rows:
        if r["model"] not in BASE:
            by_model[r["model"]].append(r)

    out = {}
    fam_totals = defaultdict(lambda: defaultdict(int))
    for model, mrows in by_model.items():
        counts = defaultdict(int)
        with_tasks, fam_with = set(), defaultdict(int)
        seen = set()
        for r in mrows:
            key = (r["model"], r["task_id"], r.get("rep", 0))
            if key in seen:
                continue
            seen.add(key)
            tag = tag_of.get(key)
            src = solution_src(tag, model, r["task_id"], r.get("rep", 0)) if tag else None
            if src is None:
                continue
            k = idiom(src)
            counts[k] += 1
            fam_totals[r["family"]][k] += 1
            if k == "with":
                with_tasks.add(r["task_id"])
                fam_with[r["family"]] += 1
        gap, leaks = gap_and_leaks(mrows)
        gap_x, leaks_x = gap_and_leaks(mrows, exclude=with_tasks)
        out[model] = {
            "idioms": dict(counts),
            "with_tasks": sorted(with_tasks),
            "with_by_family": dict(fam_with),
            "type_errors": sum(1 for r in mrows if r.get("raised") == "TypeError"),
            "gap_pp": round(gap, 1),
            "gap_pp_excluding_with": round(gap_x, 1),
            "leaks": leaks,
            "leaks_excluding_with": leaks_x,
        }
    return {"per_model": out,
            "by_family": {f: dict(fam_totals[f]) for f in FAMILIES},
            "label": label}


def family_gaps(tags):
    """Per-model neutral cleanup gap within each resource family."""
    rows, _ = load_condition(tags)
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["model"] in BASE:
            continue
        by[r["model"]][(r["family"], r["type"])].append(r["full_correct"])
    out = {}
    for m, d in by.items():
        out[m] = {}
        for f in FAMILIES:
            h, e = d.get((f, "happy"), []), d.get((f, "error"), [])
            out[m][f] = 100 * (sum(h) / len(h) - sum(e) / len(e)) if h and e else 0.0
    return out


def tex_table(neutral, fam):
    """Per-family gap, which idiom was written, and whether dropping `with` tasks moves the gap.

    The per-family gap and the idiom counts are both 13-model neutral breakdowns answering the
    same question -- is the fs concentration real? -- so they are reported as one table.
    """
    per = neutral["per_model"]
    lines = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r"& \multicolumn{3}{c}{Neutral gap by family (pp)} "
             r"& \multicolumn{3}{c}{Idiom (n/48)} & \multicolumn{2}{c}{Gap (pp)} \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-9}",
             r"Model & db & fs & lock & \texttt{with} & \texttt{fin.} & none & all "
             r"& ex.\ \texttt{w.} \\",
             r"\midrule"]
    tot = defaultdict(int)
    for m in ORDER:
        d = per.get(m)
        if not d:
            continue
        i, g = d["idioms"], fam.get(m, {})
        for k in ("with", "finally", "plain"):
            tot[k] += i.get(k, 0)
        lines.append(
            f"{LABEL.get(m, m)} & {g.get('db', 0):.0f} & "
            f"\\textbf{{{g.get('fs', 0):.0f}}} & {g.get('lock', 0):.0f} & "
            f"{i.get('with', 0)} & {i.get('finally', 0)} & {i.get('plain', 0)} & "
            f"{d['gap_pp']:.0f} & {d['gap_pp_excluding_with']:.0f} \\\\")
    lines += [r"\midrule",
              rf"\textbf{{Total}} & -- & -- & -- & \textbf{{{tot['with']}}} & "
              rf"\textbf{{{tot['finally']}}} & \textbf{{{tot['plain']}}} & -- & -- \\",
              r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)

def main() -> int:
    result = {c: analyse(tags, c) for c, tags in CONDITIONS.items()}
    result["k3_neutral"] = analyse(K3_NEUTRAL, "k3_neutral")

    for cond in ("neutral", "instructed", "k3_neutral"):
        d = result[cond]
        print(f"\n=== {cond} ===")
        print("  `with` attempts by family: " + "  ".join(
            f"{f}={d['by_family'].get(f, {}).get('with', 0)}/"
            f"{sum(d['by_family'].get(f, {}).values())}" for f in FAMILIES))
        print(f"  {'model':28s} {'with':>5s} {'fin':>5s} {'none':>5s} "
              f"{'TypeErr':>8s} {'gap':>6s} {'gap-x':>7s} {'leaks':>6s} {'leaks-x':>8s}")
        for m in ORDER + ["ollama:qwen3-coder:30b", "ollama:deepseek-coder-v2:16b"]:
            x = d["per_model"].get(m)
            if not x:
                continue
            i = x["idioms"]
            print(f"  {LABEL.get(m, m):28s} {i.get('with', 0):5d} {i.get('finally', 0):5d} "
                  f"{i.get('plain', 0):5d} {x['type_errors']:8d} {x['gap_pp']:6.0f} "
                  f"{x['gap_pp_excluding_with']:7.0f} {x['leaks']:6d} {x['leaks_excluding_with']:8d}")

    (ROOT / "out/tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/tables/idioms.tex").write_text(
        tex_table(result["neutral"], family_gaps(CONDITIONS["neutral"])))
    (ROOT / "out/idiom_stats.json").write_text(json.dumps(result, indent=2))
    print("\nwrote out/tables/idioms.tex and out/idiom_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

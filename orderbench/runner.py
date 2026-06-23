"""Model runner + pluggable solution adapters.

An *adapter* turns a task into a candidate solution module on disk, which the harness
then executes. Three adapters need no API key and make the benchmark fully runnable
and self-demonstrating out of the box:

* ``reference`` -- use each task's reference.py (upper bound; ~zero gap).
* ``buggy``     -- use each task's buggy.py (illustrates a large cleanup-on-exception gap).
* ``null``      -- a do-nothing solution (baseline; fails output, no resource touched).

Real LLM adapters are wired but key-gated, so a reviewer can reproduce the headline
numbers with their own keys without changing code:

* ``anthropic:<model>``  -- requires ANTHROPIC_API_KEY and the ``anthropic`` package.
* ``openai:<model>``     -- requires OPENAI_API_KEY and the ``openai`` package.
* ``command:<argv>``     -- shells out to any CLI (e.g. a Claude Code wrapper) that reads
                            the prompt on stdin and prints a Python solution on stdout.

Every adapter writes the candidate code to ``<out>/<model>/<task_id>.py`` so runs are
fully inspectable and re-gradable after the fact.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .harness import Task, run_task_safe

CodeFn = Callable[[Task], str]


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #
API_DOCS = {
    "db": (
        "You are given `pool`, a database connection pool with one method:\n"
        "  pool.connect() -> conn\n"
        "A `conn` supports: conn.begin(), conn.execute(sql)->str, conn.commit(), "
        "conn.rollback(), conn.close().\n"
        "Every connection you open MUST be closed exactly once, on every path "
        "(including when an operation raises)."
    ),
    "fs": (
        "You are given `fs`, a filesystem with one method:\n"
        "  fs.open(path) -> handle\n"
        "A `handle` supports: handle.read()->str, handle.write(data), handle.close().\n"
        "Every handle you open MUST be closed exactly once, on every path "
        "(including when an operation raises)."
    ),
    "lock": (
        "You are given `env` with two attributes:\n"
        "  env.lock     -- a reentrant lock supporting env.lock.acquire() / env.lock.release()\n"
        "  env.resource -- a shared resource supporting env.resource.modify(delta)->int\n"
        "env.resource.modify MUST be called while holding env.lock, and every acquire() "
        "MUST be balanced by exactly one release() on every path (including when modify raises)."
    ),
}

# Neutral API docs: describe the methods and basic usage, but state NO cleanup
# requirement (no "close on every path", no "release even if it raises"). Used by the
# neutral-prompt ablation to test whether models clean up when *not* told to.
API_DOCS_NEUTRAL = {
    "db": (
        "You are given `pool`, a database connection pool with one method:\n"
        "  pool.connect() -> conn\n"
        "A `conn` supports: conn.begin(), conn.execute(sql)->str, conn.commit(), "
        "conn.rollback(), conn.close()."
    ),
    "fs": (
        "You are given `fs`, a filesystem with one method:\n"
        "  fs.open(path) -> handle\n"
        "A `handle` supports: handle.read()->str, handle.write(data), handle.close()."
    ),
    "lock": (
        "You are given `env` with two attributes:\n"
        "  env.lock     -- a reentrant lock supporting env.lock.acquire() / env.lock.release()\n"
        "  env.resource -- a shared resource supporting env.resource.modify(delta)->int "
        "(call it while holding env.lock)."
    ),
}

# Two independent cleanup cues, each a module-level switch set by run_model():
#   _PROMPT_MODE  -- the TASK-sentence cue: "instructed" (task tells the model to clean up)
#                    or "neutral" (the cleanup sentence is stripped from the task).
#   _API_DOC_MODE -- the API-DOC cue: "full" (the API doc states the cleanup obligation)
#                    or "neutral" (the API doc only lists methods).
# Crossing them gives the 2x2 prompt-cue ablation:
#   instructed = (instructed, full); neutral = (neutral, neutral);
#   api-only   = (neutral, full);   task-only = (instructed, neutral).
_PROMPT_MODE = "instructed"
_API_DOC_MODE = "full"

_CLEANUP_SENT_RE = re.compile(
    r"(must\b.*?(closed|released|every path|exactly once)"
    r"|even if\b.*?rais"
    r"|every path"
    r"|balanced by)",
    re.IGNORECASE | re.DOTALL,
)


def neutralize_task_prompt(text: str) -> str:
    """Drop sentences that instruct cleanup, keeping only the functional goal."""
    flat = " ".join(text.split())
    sentences = re.split(r"(?<=[.])\s+", flat)
    kept = [s for s in sentences if not _CLEANUP_SENT_RE.search(s)]
    return " ".join(kept).strip()


def signature(task: Task) -> str:
    """Exact `def name(params):` line from the task's reference solution.

    Giving the candidate the full signature (parameter names + order) is part of
    the task spec — like HumanEval — and removes argument-order ambiguity on
    multi-argument tasks. The candidate supplies the body; the signature is given.
    """
    src = (task.path / "reference.py").read_text()
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == task.entrypoint:
                params = ", ".join(a.arg for a in node.args.args)
                return f"def {task.entrypoint}({params}):"
    except SyntaxError:
        pass
    return f"def {task.entrypoint}({task.manager_name}, ...):"


def build_user_prompt(task: Task) -> str:
    """Task-specific instruction (no API doc) — shared by all adapters."""
    prompt_text = task.prompt.strip()
    if _PROMPT_MODE == "neutral":
        prompt_text = neutralize_task_prompt(prompt_text)
    return (
        f"Write a single Python function with exactly this signature:\n"
        f"```python\n{signature(task)}\n```\n"
        f"`{task.manager_name}` is the manager described above.\n\n"
        f"Task:\n{prompt_text}\n\n"
        f"Return ONLY the function definition in a ```python code block."
    )


# When set (by the repair experiment), build_prompt returns this verbatim instead of the
# normal task prompt, so the same adapters can drive a second "fix your leak" pass.
_REPAIR_PROMPT: str | None = None


def build_repair_prompt(task: Task, original_code: str) -> str:
    """Second-pass prompt: hand the model its own leaky solution and ask it to fix cleanup."""
    return (
        f"{API_DOCS[task.family]}\n\n"
        f"The following Python function returns the right value but can leak the resource it "
        f"acquires when an operation raises (cleanup is skipped on the exception path):\n"
        f"```python\n{original_code.strip()}\n```\n"
        f"Rewrite it so that every resource it acquires is released on every path, including "
        f"when an operation raises. Keep exactly the same signature and return behaviour.\n"
        f"Return ONLY the function definition in a ```python code block."
    )


def build_prompt(task: Task) -> str:
    if _REPAIR_PROMPT is not None:
        return _REPAIR_PROMPT
    docs = API_DOCS_NEUTRAL if _API_DOC_MODE == "neutral" else API_DOCS
    return f"{docs[task.family]}\n\n{build_user_prompt(task)}"


_CODE_BLOCK = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    blocks = _CODE_BLOCK.findall(text)
    return (blocks[0] if blocks else text).strip()


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #
def _reference_code(task: Task) -> str:
    return (task.path / "reference.py").read_text()


def _buggy_code(task: Task) -> str:
    p = task.path / "buggy.py"
    return p.read_text() if p.exists() else _null_code(task)


def _null_code(task: Task) -> str:
    return f"def {task.entrypoint}(*args, **kwargs):\n    return None\n"


def _anthropic_code(model: str) -> CodeFn:
    def gen(task: Task) -> str:
        import anthropic  # noqa: imported lazily so the package is optional

        client = anthropic.Anthropic()
        # The family API doc is identical across every task in a family — cache it
        # as a system prefix so repeated calls bill it at ~0.1x (see shared/prompt-caching).
        docs = API_DOCS_NEUTRAL if _API_DOC_MODE == "neutral" else API_DOCS
        system = [{
            "type": "text",
            "text": docs[task.family],
            "cache_control": {"type": "ephemeral"},
        }]
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": build_user_prompt(task)}],
        )
        return extract_code(msg.content[0].text)

    return gen


def _ollama_code(model: str) -> CodeFn:
    """Drive a local Ollama model (free, offline) as a system-under-test."""
    def gen(task: Task) -> str:
        out = subprocess.run(
            ["ollama", "run", model],
            input=build_prompt(task),
            capture_output=True, text=True, timeout=600,
        )
        return extract_code(out.stdout)

    return gen


def _claude_code_code(model: str) -> CodeFn:
    """Drive the local `claude` CLI (Claude Code) headlessly as a system-under-test.

    Uses the user's Claude subscription (no API key / per-token cost). Tools are
    disabled and the call runs in a throwaway cwd so it behaves as a pure one-shot
    code generator, not an agent with filesystem access. `model` is a Claude Code
    alias: opus | sonnet | haiku (or a full model id).
    """
    def gen(task: Task) -> str:
        out = subprocess.run(
            ["claude", "-p", "--model", model,
             "--disallowed-tools", "Bash", "Read", "Write", "Edit",
             "Glob", "Grep", "WebFetch", "WebSearch"],
            input=build_prompt(task),
            capture_output=True, text=True, timeout=300,
            cwd=tempfile.mkdtemp(prefix="ob_cc_"),
        )
        return extract_code(out.stdout)

    return gen


def _openai_code(model: str) -> CodeFn:
    def gen(task: Task) -> str:
        from openai import OpenAI  # noqa: optional dependency

        # Bound every call: 90s timeout, no long retry loop -> a runaway reasoning
        # generation fails fast and the task scores wrong, instead of hanging the run.
        client = OpenAI(timeout=90.0, max_retries=1)
        msgs = [{"role": "user", "content": build_prompt(task)}]
        base = dict(model=model, messages=msgs, max_completion_tokens=2048)
        # GPT-5 / o-series are reasoning models: cap reasoning so codegen stays fast/cheap.
        reasoning = model.startswith("gpt-5") or model.startswith("o")
        attempts = ([{"reasoning_effort": "low"}] if reasoning else []) + [{}]
        for extra in attempts:
            try:
                resp = client.chat.completions.create(**base, **extra)
                return extract_code(resp.choices[0].message.content or "")
            except Exception:
                continue
        return ""  # all attempts failed -> empty solution -> graded wrong, no crash

    return gen


def _command_code(argv: str) -> CodeFn:
    def gen(task: Task) -> str:
        out = subprocess.run(
            argv, shell=True, input=build_prompt(task),
            capture_output=True, text=True, timeout=300,
        )
        return extract_code(out.stdout)

    return gen


def resolve_adapter(model: str) -> CodeFn:
    if model == "reference":
        return _reference_code
    if model == "buggy":
        return _buggy_code
    if model == "null":
        return _null_code
    if model.startswith("anthropic:"):
        return _anthropic_code(model.split(":", 1)[1])
    if model.startswith("claude-code:"):
        return _claude_code_code(model.split(":", 1)[1])
    if model.startswith("ollama:"):
        return _ollama_code(model.split(":", 1)[1])
    if model.startswith("openai:"):
        return _openai_code(model.split(":", 1)[1])
    if model.startswith("command:"):
        return _command_code(model.split(":", 1)[1])
    raise ValueError(f"unknown model adapter: {model!r}")


# --------------------------------------------------------------------------- #
# Run loop
# --------------------------------------------------------------------------- #
def run_model(model: str, tasks: list[Task], out_dir: str | Path, repeats: int = 1,
              prompt_mode: str = "instructed", api_doc_mode: str | None = None) -> list[dict]:
    """Generate (or load) a solution per task, grade it, and return flat scenario rows.

    ``repeats`` re-samples generation for stochastic models (k in pass@1 / CI estimation);
    deterministic adapters (reference/buggy/null) collapse to one effective sample.
    ``prompt_mode`` is the TASK-sentence cue (``"instructed"`` / ``"neutral"``).
    ``api_doc_mode`` is the API-DOC cue (``"full"`` / ``"neutral"``); if ``None`` it tracks
    ``prompt_mode`` (full when instructed, neutral when neutral) so the two original
    conditions are unchanged. Setting them independently yields the 2x2 cue ablation.
    """
    global _PROMPT_MODE, _API_DOC_MODE
    _PROMPT_MODE = prompt_mode
    _API_DOC_MODE = api_doc_mode if api_doc_mode is not None else (
        "neutral" if prompt_mode == "neutral" else "full")
    out_dir = Path(out_dir) / model.replace(":", "_").replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    adapter = resolve_adapter(model)
    deterministic = model in {"reference", "buggy", "null"}
    k = 1 if deterministic else repeats

    rows: list[dict] = []
    for rep in range(k):
        for task in tasks:
            sol_path = out_dir / f"{task.id}__rep{rep}.py"
            if not sol_path.exists():
                sol_path.write_text(adapter(task))
            for r in run_task_safe(task, sol_path):
                rows.append({
                    "model": model,
                    "rep": rep,
                    "task_id": r.task_id,
                    "family": task.family,
                    "scenario": r.scenario,
                    "type": r.type,
                    "output_ok": r.output_ok,
                    "violations": r.violations,
                    "full_correct": r.full_correct,
                    "raised": r.raised,
                })
    return rows


def write_rows(rows: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(rows, indent=2))

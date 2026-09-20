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
from .invariants import set_cm_support

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

# A third, independent switch: whether the instrumented resources expose the Python
# context-manager protocol. Off = the published method-only mocks (`with` raises
# TypeError); on = `with` is a legitimate way to discharge the cleanup obligation, and
# the API doc lists the protocol as a capability. This is the context-manager ablation,
# not a cue: the doc gains no cleanup imperative in either setting.
_MOCK_CM = False

# Reasoning-model effort for the OpenAI adapter. `None` sends no `reasoning_effort` at
# all (provider default). Recorded in the run config so a row's effort is never ambiguous.
_REASONING_EFFORT: str | None = "low"

# Generation budget for the OpenAI adapter. The published panel used 2048 tokens and a 90 s
# client timeout, which never bound at `reasoning_effort=low` (no empty or truncated solution
# in 720 GPT-5 generations). Higher effort spends far more of the budget on reasoning tokens
# before any answer is emitted, so the budget is a run parameter: a truncated answer would
# make higher effort look worse for a reason that has nothing to do with cleanup discipline.
_MAX_TOKENS = 2048
_REQUEST_TIMEOUT = 90.0

# Extra argv for the claude-code adapter, used by the harness-parity arm to replace the
# Claude Code CLI's own system prompt with a minimal one (see `claude_parity_argv`).
_CLAUDE_EXTRA_ARGV: list[str] = []

_CLEANUP_SENT_RE = re.compile(
    r"(must\b.*?(closed|released|every path|exactly once)"
    r"|even if\b.*?rais"
    r"|every path"
    r"|balanced by)",
    re.IGNORECASE | re.DOTALL,
)


def neutralize_task_prompt(text: str) -> str:
    """Drop sentences that instruct cleanup, keeping only the functional goal.

    The surviving text keeps its original line wrapping: the instructed and neutral
    conditions must differ by the cue sentences and nothing else, not even whitespace.
    """
    sentences = re.split(r"(?<=[.])(\s+)", text.strip())
    out, i = [], 0
    while i < len(sentences):
        sent = sentences[i]
        sep = sentences[i + 1] if i + 1 < len(sentences) else ""
        if not _CLEANUP_SENT_RE.search(" ".join(sent.split())):
            out.append(sent + sep)
        i += 2
    return "".join(out).strip()


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


# When the context-manager ablation is on, the API doc must say the protocol exists --
# otherwise the model is being asked to guess at an undocumented capability. This is a
# *capability* line, not a cleanup imperative: it names what the object supports and
# never says the resource must be released, so the neutral condition stays cue-free.
_CM_DOC = {
    "db": "A `conn` is also a context manager: `with pool.connect() as conn:` is supported.",
    "fs": "A `handle` is also a context manager: `with fs.open(path) as handle:` is supported.",
    "lock": "`env.lock` is also a context manager: `with env.lock:` is supported.",
}


def api_doc(task: Task) -> str:
    """The API documentation block shown to the model for this task's family."""
    docs = API_DOCS_NEUTRAL if _API_DOC_MODE == "neutral" else API_DOCS
    text = docs[task.family]
    if _MOCK_CM:
        text = f"{text}\n{_CM_DOC[task.family]}"
    return text


def build_prompt(task: Task) -> str:
    if _REPAIR_PROMPT is not None:
        return _REPAIR_PROMPT
    return f"{api_doc(task)}\n\n{build_user_prompt(task)}"


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
        system = [{
            "type": "text",
            "text": api_doc(task),
            "cache_control": {"type": "ephemeral"},
        }]
        msg = client.messages.create(
            model=model,
            # Matched to the OpenAI adapter's max_completion_tokens so the two API
            # backends differ only in vendor, not in generation budget.
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": build_user_prompt(task)}],
        )
        return extract_code(msg.content[0].text)

    return gen


#: Ollama's local HTTP endpoint. The adapter talks to this rather than shelling out to
#: `ollama run`, whose non-TTY stdin path was observed to hang indefinitely on a reasoning
#: model that answers the same prompt fine over HTTP. The API is also the only route that
#: exposes token counts and lets the harness bound generation length.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def _ollama_code(model: str, num_predict: int = 2048, timeout: int = 900) -> CodeFn:
    """Drive a local Ollama model (free, offline) as a system-under-test."""
    def gen(task: Task) -> str:
        import urllib.request  # stdlib only: Ollama needs no SDK

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps({"model": model, "prompt": build_prompt(task), "stream": False,
                             "options": {"num_predict": num_predict}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            body = json.load(urllib.request.urlopen(req, timeout=timeout))
        except Exception:
            return ""  # graded wrong, never dropped
        return extract_code(body.get("response") or "")

    return gen


def _ollama_cli_code(model: str) -> CodeFn:
    """The original `ollama run` path, kept for provenance (see OLLAMA_URL note)."""
    def gen(task: Task) -> str:
        out = subprocess.run(
            ["ollama", "run", model],
            input=build_prompt(task),
            capture_output=True, text=True, timeout=600,
        )
        return extract_code(out.stdout)

    return gen


#: Every tool the Claude Code CLI ships, so the model under test is a pure one-shot code
#: generator. Disabling a tool also drops its definition from the system prompt, which is
#: most of what `claude_parity_argv` buys.
CLAUDE_DISALLOWED_TOOLS = [
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch",
    "Task", "TodoWrite", "NotebookEdit", "BashOutput", "KillShell", "SlashCommand", "Skill",
]

#: Minimal replacement for the Claude Code CLI's own system prompt.
CLAUDE_PARITY_SYSTEM_PROMPT = "You are a Python code generator."


def claude_parity_argv(system_prompt: str = CLAUDE_PARITY_SYSTEM_PROMPT) -> list[str]:
    """Extra argv that strips the Claude Code CLI's agent system prompt.

    The CLI is an agent harness: by default it prepends its own coding guidelines and
    environment context, which the OpenAI adapter (a single bare `user` message) does
    not have. That asymmetry matters here precisely because the experiment is about
    whether a cleanup cue is present in the prompt. `--system-prompt` replaces that
    preamble outright; combined with `CLAUDE_DISALLOWED_TOOLS` it takes the system
    context from ~33.8k tokens to ~4.2k, measured on a fixed probe prompt.

    Note `--exclude-dynamic-system-prompt-sections` measures *worse* (~24.8k) because it
    relocates those sections rather than dropping them; it is deliberately not used.
    """
    return ["--system-prompt", system_prompt]


def _claude_code_code(model: str) -> CodeFn:
    """Drive the local `claude` CLI (Claude Code) headlessly as a system-under-test.

    Uses the user's Claude subscription (no API key / per-token cost). Tools are
    disabled and the call runs in a throwaway cwd so it behaves as a pure one-shot
    code generator, not an agent with filesystem access. `model` is a Claude Code
    alias: opus | sonnet | haiku (or a full model id).
    """
    def gen(task: Task) -> str:
        argv = ["claude", "-p", "--model", model,
                "--disallowed-tools", *CLAUDE_DISALLOWED_TOOLS]
        argv += _CLAUDE_EXTRA_ARGV
        out = subprocess.run(
            argv,
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
        client = OpenAI(timeout=_REQUEST_TIMEOUT, max_retries=1)
        msgs = [{"role": "user", "content": build_prompt(task)}]
        base = dict(model=model, messages=msgs, max_completion_tokens=_MAX_TOKENS)
        # GPT-5 / o-series are reasoning models. The effort is whatever the run config
        # says and nothing else: an earlier version fell back to the provider default
        # when the explicit call raised, which made a row's effort unrecoverable after
        # the fact. A failure now returns an empty solution (graded wrong) instead.
        reasoning = model.startswith("gpt-5") or model.startswith("o")
        extra = {"reasoning_effort": _REASONING_EFFORT} if (
            reasoning and _REASONING_EFFORT) else {}
        try:
            resp = client.chat.completions.create(**base, **extra)
            return extract_code(resp.choices[0].message.content or "")
        except Exception:
            return ""  # graded wrong, never dropped, never silently re-tried at another effort

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
    if model.startswith("ollama-cli:"):
        return _ollama_cli_code(model.split(":", 1)[1])
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
def run_config(prompt_mode: str = "instructed", api_doc_mode: str | None = None,
               mock_cm: bool = False, reasoning_effort: str | None = "low",
               claude_parity: bool = False, max_tokens: int = 2048,
               request_timeout: float = 90.0) -> dict:
    """The full generation configuration for a run, as recorded in the results bundle.

    Solutions are cached by ``(tag, model, task, rep)`` alone, so nothing in the path
    records which condition produced them. Writing the config into the bundle makes a
    tag/condition mismatch visible instead of silent.
    """
    return {
        "prompt_mode": prompt_mode,
        "api_doc_mode": api_doc_mode if api_doc_mode is not None else (
            "neutral" if prompt_mode == "neutral" else "full"),
        "mock_cm": bool(mock_cm),
        "reasoning_effort": reasoning_effort,
        "claude_parity": bool(claude_parity),
        "max_tokens": int(max_tokens),
        "request_timeout": float(request_timeout),
    }


def run_model(model: str, tasks: list[Task], out_dir: str | Path, repeats: int = 1,
              prompt_mode: str = "instructed", api_doc_mode: str | None = None,
              mock_cm: bool = False, reasoning_effort: str | None = "low",
              claude_parity: bool = False, max_tokens: int = 2048,
              request_timeout: float = 90.0) -> list[dict]:
    """Generate (or load) a solution per task, grade it, and return flat scenario rows.

    ``repeats`` re-samples generation for stochastic models (k in pass@1 / CI estimation);
    deterministic adapters (reference/buggy/null) collapse to one effective sample.
    ``prompt_mode`` is the TASK-sentence cue (``"instructed"`` / ``"neutral"``).
    ``api_doc_mode`` is the API-DOC cue (``"full"`` / ``"neutral"``); if ``None`` it tracks
    ``prompt_mode`` (full when instructed, neutral when neutral) so the two original
    conditions are unchanged. Setting them independently yields the 2x2 cue ablation.
    ``mock_cm`` turns on the resources' context-manager protocol (a third, orthogonal
    axis -- an interface change, not a cue). ``reasoning_effort`` is sent verbatim to the
    OpenAI reasoning models (``None`` = provider default). ``claude_parity`` strips the
    Claude Code CLI's own system prompt so that arm matches the bare-API arms.
    """
    global _PROMPT_MODE, _API_DOC_MODE, _MOCK_CM, _REASONING_EFFORT, _CLAUDE_EXTRA_ARGV
    global _MAX_TOKENS, _REQUEST_TIMEOUT
    _PROMPT_MODE = prompt_mode
    _API_DOC_MODE = api_doc_mode if api_doc_mode is not None else (
        "neutral" if prompt_mode == "neutral" else "full")
    _MOCK_CM = bool(mock_cm)
    _REASONING_EFFORT = reasoning_effort
    _CLAUDE_EXTRA_ARGV = claude_parity_argv() if claude_parity else []
    _MAX_TOKENS = int(max_tokens)
    _REQUEST_TIMEOUT = float(request_timeout)
    # The mocks are constructed per scenario inside the harness, so the protocol switch
    # has to be set on the invariants module, not passed down through run_task_safe.
    set_cm_support(_MOCK_CM)
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

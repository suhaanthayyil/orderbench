"""Write results/model_manifest.json: per evaluated model, the adapter, the vendor-returned
model identifier (for API models we issue one tiny request and record the resolved snapshot id
the vendor returns), and the access date. Provides an audit trail for the exact model snapshots.

The Claude arm runs through the Claude Code CLI, which resolves an alias (opus/sonnet/haiku)
to whatever snapshot is current on the run date. Recording only the alias -- as this script
used to -- left the Claude rows unreproducible in a way the OpenAI rows were not, so the CLI
is probed too: `claude -p --output-format json` reports the concrete snapshot under
`modelUsage`, and the CLI's own version is recorded alongside it.

Usage: `python scripts/model_manifest.py`. Claude and Ollama models need no key; the OpenAI
probes are skipped with a note when no key is present.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.date.today().isoformat()

OPENAI = ["gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-5", "gpt-5-mini",
          "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.5"]
CLAUDE = ["opus", "sonnet", "haiku"]
OLLAMA = ["gemma4:12b", "qwen3-coder:30b", "deepseek-coder-v2:16b"]


def probe_openai(model: str) -> str:
    from openai import OpenAI
    c = OpenAI(timeout=60, max_retries=1)
    base = dict(model=model, max_completion_tokens=64,
                messages=[{"role": "user", "content": "ok"}])
    reasoning = model.startswith("gpt-5") or model.startswith("o")
    for extra in (([{"reasoning_effort": "low"}] if reasoning else []) + [{}]):
        try:
            return c.chat.completions.create(**base, **extra).model  # resolved snapshot id
        except Exception as e:
            last = e
    return f"<probe-failed: {type(last).__name__}>"


def claude_cli_version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True,
                              timeout=60).stdout.strip()
    except Exception as e:
        return f"<version-probe-failed: {type(e).__name__}>"


def probe_claude(alias: str) -> str:
    """Resolve a Claude Code alias to the concrete snapshot id the CLI actually called."""
    try:
        out = subprocess.run(
            ["claude", "-p", "--model", alias, "--output-format", "json",
             "--disallowed-tools", "Bash", "Read", "Write", "Edit", "Glob", "Grep",
             "WebFetch", "WebSearch"],
            input="Reply with only the word OK.",
            capture_output=True, text=True, timeout=300,
        )
        used = list(json.loads(out.stdout).get("modelUsage", {}))
        return used[0] if used else "<no modelUsage in CLI response>"
    except Exception as e:
        return f"<probe-failed: {type(e).__name__}>"


def main() -> int:
    manifest = {}
    if os.environ.get("OPENAI_API_KEY"):
        for m in OPENAI:
            manifest[f"openai:{m}"] = {"adapter": "openai", "requested": m,
                                       "vendor_returned_id": probe_openai(m),
                                       "access_date": TODAY}
    else:
        print("OPENAI_API_KEY not set -- keeping any previously recorded OpenAI entries")
        prev = ROOT / "results" / "model_manifest.json"
        if prev.exists():
            manifest.update({k: v for k, v in json.loads(prev.read_text()).items()
                             if k.startswith("openai:")})
    cli_version = claude_cli_version()
    for a in CLAUDE:
        manifest[f"claude-code:{a}"] = {"adapter": "claude-code (CLI)", "requested": a,
                                        "vendor_returned_id": probe_claude(a),
                                        "harness_version": cli_version,
                                        "access_date": TODAY}
    for m in OLLAMA:
        manifest[f"ollama:{m}"] = {"adapter": "ollama (local weights)", "requested": m,
                                   "vendor_returned_id": m, "access_date": TODAY}
    out = ROOT / "results" / "model_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out} ({len(manifest)} models)")
    for k, v in manifest.items():
        print(f"  {k:32} -> {v['vendor_returned_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

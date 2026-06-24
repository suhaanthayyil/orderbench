"""Write results/model_manifest.json: per evaluated model, the adapter, the vendor-returned
model identifier (for API models we issue one tiny request and record the resolved snapshot id
the vendor returns), and the access date. Provides an audit trail for the exact model snapshots.

Usage: source the OpenAI key first, then `python scripts/model_manifest.py`. OpenAI models are
probed live; Claude (Claude Code CLI) and Ollama models are recorded by name (the CLI/local
runtime resolves them).
"""
from __future__ import annotations

import datetime
import json
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


def main() -> int:
    manifest = {}
    for m in OPENAI:
        manifest[f"openai:{m}"] = {"adapter": "openai", "requested": m,
                                   "vendor_returned_id": probe_openai(m), "access_date": TODAY}
    for a in CLAUDE:
        manifest[f"claude-code:{a}"] = {"adapter": "claude-code (CLI)", "requested": a,
                                        "vendor_returned_id": f"resolved by Claude Code CLI ({a} alias)",
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

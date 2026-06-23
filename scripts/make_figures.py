"""Regenerate result figures and LaTeX tables (into out/) from a results bundle.

Usage: python scripts/make_figures.py [results/<tag>/results.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbench.plots import all_figures  # noqa: E402
from orderbench.report import write_tables  # noqa: E402


def main(results_path: str) -> int:
    bundle = json.loads(Path(results_path).read_text())
    figs = all_figures(bundle, ROOT / "out" / "figures")
    write_tables(bundle, ROOT / "out" / "tables")
    print("figures:", figs)
    print("tables:", str(ROOT / "out" / "tables"))
    return 0


if __name__ == "__main__":
    rp = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "results" / "demo" / "results.json")
    raise SystemExit(main(rp))

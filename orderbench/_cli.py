"""Console-script entry points (thin wrappers over scripts/)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def validate_main() -> int:
    sys.path.insert(0, str(_ROOT))
    from scripts.validate_all import main  # type: ignore
    root = sys.argv[1] if len(sys.argv) > 1 else str(_ROOT / "tasks")
    return main(root)


def eval_main() -> int:
    sys.path.insert(0, str(_ROOT))
    import scripts.run_eval as run_eval  # type: ignore
    return run_eval.main()

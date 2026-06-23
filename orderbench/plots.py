"""Matplotlib figures for the paper. Headless (Agg) so it runs anywhere."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CLASSES = ["order", "guard", "double", "unclosed"]


def gap_figure(bundle: dict, out_path: str | Path) -> None:
    """Grouped bars: happy-path vs error-path full-correct rate per model.

    The visible gap between the two bars *is* the contribution: the same program is
    graded correct on the happy path yet leaks on the injected-error path.
    """
    models = list(bundle["models"])
    happy = [100 * bundle["models"][m]["happy_correct"] for m in models]
    error = [100 * bundle["models"][m]["error_correct"] for m in models]

    x = range(len(models))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.bar([i - w / 2 for i in x], happy, w, label="Happy-path", color="#4C72B0")
    ax.bar([i + w / 2 for i in x], error, w, label="Error-path (cleanup)", color="#C44E52")
    for i, m in enumerate(models):
        gap = happy[i] - error[i]
        ax.annotate(f"gap {gap:.0f}pp", (i, max(happy[i], error[i]) + 2),
                    ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("Full-correct rate (%)")
    ax.set_ylim(0, 109)
    ax.set_title("Cleanup-on-exception gap")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def per_class_figure(bundle: dict, out_path: str | Path) -> None:
    """Stacked bars of violation counts per class per model."""
    models = list(bundle["models"])
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    bottom = [0] * len(models)
    palette = {"order": "#4C72B0", "guard": "#DD8452", "double": "#55A868", "unclosed": "#C44E52"}
    for c in CLASSES:
        vals = [bundle["models"][m]["per_class"].get(c, 0) for m in models]
        ax.bar(models, vals, bottom=bottom, label=c, color=palette[c])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_ylabel("Invariant violations (count)")
    ax.set_title("Violations by class")
    ax.legend(frameon=False, fontsize=8, ncol=4)
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def ablation_figure(instructed: dict, neutral: dict, out_path: str | Path,
                    models: list | None = None) -> None:
    """Grouped bars: cleanup-on-exception gap under instructed vs neutral prompting.

    The headline figure: identical models, identical tasks; the only change is whether
    the prompt tells the model to clean up. The neutral bars are the contribution.
    """
    im, nm = instructed["models"], neutral["models"]
    models = models or [m for m in nm if m not in ("reference", "null", "buggy")]
    ins = [100 * im[m]["cleanup_gap"] for m in models]
    neu = [100 * nm[m]["cleanup_gap"] for m in models]

    def _clean(m):
        return (m.replace("claude-code:", "Claude ").replace("ollama:", "")
                 .replace("openai:", "").replace("gemma4:12b", "gemma-12B")
                 .replace("opus", "Opus").replace("sonnet", "Sonnet").replace("haiku", "Haiku"))
    labels = [_clean(m) for m in models]

    x = range(len(models))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.bar([i - w / 2 for i in x], ins, w, label="Instructed (told to clean up)", color="#4C72B0")
    ax.bar([i + w / 2 for i in x], neu, w, label="Neutral (not told)", color="#C44E52")
    for i, m in enumerate(models):
        if neu[i] > 1:
            ax.annotate(f"{neu[i]:.0f}", (i + w / 2, neu[i] + 1.0), ha="center", fontsize=7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Cleanup-on-exception gap (pp)")
    ax.set_ylim(-3, max(max(neu), 5) + 8)
    ax.set_title("Models clean up when told; leak on exceptions when not")
    ax.axhline(0, color="#888", lw=0.6)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def all_figures(bundle: dict, figures_dir: str | Path) -> Dict[str, str]:
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    gap_path = figures_dir / "cleanup_gap.png"
    cls_path = figures_dir / "per_class.png"
    gap_figure(bundle, gap_path)
    per_class_figure(bundle, cls_path)
    return {"gap": str(gap_path), "per_class": str(cls_path)}

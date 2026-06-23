# OrderBench — reviewer guide (5-minute reproduction)

This artifact contains the full OrderBench benchmark: the instrumented mock families, the 48
tasks, the harness + grading, the metrics, the pluggable model runner, the construct-validity
bridge, and every committed result file used in the paper. **No API keys are needed** to
reproduce the calibration, the validity bridge, and the headline tables — those run from the
committed results and the key-free baselines.

## 0. Requirements
- Python ≥ 3.10. `pip install -r requirements.txt` (numpy, matplotlib, pytest).
- Optional, only to *re-collect* model outputs (not needed to reproduce the paper): the
  `openai` SDK + `OPENAI_API_KEY` for the GPT panel; the `claude` CLI for the Claude panel;
  `ollama` with `gemma4:12b` for the open model.

## 1. Thirty-second sanity check (no keys)
```bash
make smoke
```
Runs the **construct-validity gate** (every task's reference solution is clean on all
scenarios; every buggy solution trips ≥1 violation — all 48 pass) and the smoke test suite.

## 2. The validity bridge — leaks are real, not mock artifacts (no keys)
```bash
make bridge
```
Reproduces the cleanup-on-exception leak against **8 real Python stdlib primitives**
(`sqlite3.Connection`, file handles, `tempfile`, `socket`, `threading.Lock`/`Semaphore`,
`ThreadPoolExecutor`, `asyncio.Lock`). On the happy path the buggy solution is output-identical
to the reference (an output-only oracle accepts it); on the error path it leaks a genuine OS
resource — exactly what the mock's `unclosed` class flags. Prints `BRIDGE PASS`.

## 3. Regenerate the paper tables from committed results (no keys)
```bash
make reproduce-tables
```
Writes, into `out/tables/`:
- `ablation.tex` — the headline instructed-vs-neutral cleanup gap (with bootstrap CIs).
- `outputonly.tex` — output-only oracle vs OrderBench (the 121 silent leaks an output
  benchmark accepts).
- `neutral_class.tex` — per-violation-class breakdown for all 13 models.
- `perfamily.tex` — cleanup gap by resource family (db/fs/lock).
- `k3.tex` — k=1 vs k=3 generation-robustness (gaps stable within a few pp).
- `bridge.tex` — the validity-bridge table.

## 4. Re-collect model outputs (optional; needs keys)
```bash
# key-free local baselines (calibration):
make panel panel-neutral
# the full panel is driven by scripts/run_eval.py, e.g.:
python scripts/run_eval.py --models openai:gpt-4o-mini --repeats 3 \
    --prompt-mode neutral --tag my_run        # task-cue + api-cue both off
python scripts/run_eval.py --models openai:gpt-4o-mini --prompt-mode neutral \
    --api-doc-mode full --tag my_api_only      # 2x2 ablation: API cue only
```
`--prompt-mode` toggles the **task-sentence** cleanup cue; `--api-doc-mode` toggles the
**API-doc** cleanup cue. Crossing them gives the 2×2 prompt-cue ablation
(neutral / api-only / task-only / instructed).

## Layout
```
orderbench/        mocks/{db,fs,lock}.py, harness.py, metrics.py, runner.py, report.py, plots.py
tasks/             the 48 tasks (tasks/<family>/<id>/, see tasks/_schema.md)
scripts/           run_eval, validate_all, make_ablation, make_extended_tables, make_k3_table,
                   run_repair, validity_bridge
results/           committed result bundles (rows.json + results.json per tag)
tests/             smoke suite
```
Every generated candidate solution is cached under `results/<tag>/solutions/` so all grading is
inspectable and re-gradable after the fact.

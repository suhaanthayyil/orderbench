# OrderBench

**Measuring cleanup-on-exception in LLM-generated code.**

Output-only code benchmarks (HumanEval, MBPP, SWE-bench) grade a program by what it
*returns*. But a program can return a perfectly correct value and still **leak a database
connection, skip a rollback, or leave a lock held** the moment an operation raises.
Those failures are *structurally invisible* to an output oracle.

OrderBench makes them visible. Every API a candidate program uses is a **self-authored,
instrumented mock** — a fake connection pool, filesystem, or reentrant lock whose state
machine records a deterministic **invariant violation** when it is misused. Tasks include
**error-injection scenarios** that raise inside the critical section, so we can measure the
gap between a model's happy-path correctness and its behaviour when something fails.

### Headline result: cleanup is instruction-dependent

Calibration: a `buggy` baseline scores +100pp gap; `reference`/`null` score 0. We then run
four models (Claude Opus/Sonnet/Haiku + open 12B) under **two prompt conditions differing by
one sentence** — whether the task says "always close, even if it raises."

| model | gap *(told to clean up)* | gap *(not told)* | silent-misuse *(not told)* |
|---|---|---|---|
| Claude Opus | 0 | **+2pp** | 3% |
| Claude Sonnet | 0 | **+33pp** | 16% |
| Claude Haiku | 0 | **+50pp** | 27% |
| gemma 12B (open) | 0 | **+29pp** | 17% |

**Told to clean up, every model is flawless. Strip that one instruction and the same models
write code that returns correct values but silently leaks on the exception path** — up to a
50pp cleanup gap and 27% of outputs correct-but-leaking, scaling inversely with capability
(Opus resists; smaller models don't). **Every leak is invisible to an output-only benchmark**,
which sees identical happy-path returns. Reproduce: `make panel && make panel-neutral && make ablation`.

```
                 happy-path        error-injection
   pool.connect()  ✓ commit ✓        ✓ ... execute() raises 💥
   begin()         ✓ close  ✓        → connection never closed → [unclosed] leak
   execute()       ✓                 (output still "looks correct")
```

### Why this design

| Property | How OrderBench gets it |
|---|---|
| **Contamination-free** | The mock APIs are invented for this benchmark. No model can have memorized usage of an API that did not exist before publication. |
| **Copyright-clean** | 100% self-authored. No scraped repos, no GPL/share-alike propagation. Code MIT, tasks CC-BY-4.0. |
| **Objective & deterministic** | Grading is a state-machine assertion log + literal output comparison. No LLM-judge, no flakiness. |
| **Anti-gameable** | The headline is a *gap*, not an absolute score. A model that does nothing scores 0; a model that "looks correct" but leaks is caught by the invariant log. |

## The metrics

For each scenario the harness records `output_ok` and the mock's `violations`, then:

- **Cleanup-on-exception gap** = `happy_correct − error_correct` (per model). *The headline.*
- **Silent-misuse rate** = fraction of scenarios where output is correct **but** ≥1 invariant was violated ("looks right but leaks").
- **Per-class breakdown** over four violation classes: `order`, `guard`, `double`, `unclosed`.
- **Bootstrap 95% CIs**, resampled over tasks.

## Quickstart

```bash
pip install -r requirements.txt

make validate     # construct-validity gate: every reference is clean, every buggy leaks
make demo         # run reference / buggy / null baselines  ->  results/demo/
make figures      # regenerate paper figures + LaTeX tables
make test         # pytest smoke suite
```

The three built-in adapters need **no API key** and make the benchmark self-demonstrating:

| adapter | what it shows |
|---|---|
| `reference` | upper bound — clean code, ~0 gap |
| `buggy`     | the failure mode — passes every happy path, leaks on every error path (100pp gap) |
| `null`      | baseline — does nothing, fails output everywhere |

### Evaluating real models

```bash
# Free — drives the local `claude` CLI (Claude Code) on your subscription, no API key:
python scripts/run_eval.py --models claude-code:opus claude-code:sonnet claude-code:haiku \
    --repeats 1 --tag claude_panel

# Paid API panels:
export ANTHROPIC_API_KEY=...; export OPENAI_API_KEY=...
python scripts/run_eval.py --models anthropic:claude-opus-4-8 openai:gpt-5.5 \
    --repeats 5 --tag api_panel
python scripts/make_figures.py results/api_panel/results.json
```

Adapters are pluggable:

| adapter | cost | notes |
|---|---|---|
| `reference` / `buggy` / `null` | free | calibration baselines, no model |
| `claude-code:<alias>` | free* | drives the local `claude` CLI headlessly (`opus`/`sonnet`/`haiku`); tools disabled, isolated cwd |
| `anthropic:<model>` | API | needs `ANTHROPIC_API_KEY`; family API doc is prompt-cached |
| `ollama:<model>` | free | local open models via Ollama (offline, no key) |
| `openai:<model>` | API | needs `OPENAI_API_KEY` |
| `command:<argv>` | varies | shell out to any CLI that reads the prompt on stdin and prints a solution |

\* uses your Claude subscription rather than per-token API billing. Every generated solution
is written to `results/<tag>/solutions/` for inspection and re-grading; malformed output
(no parseable function) scores as wrong rather than crashing the run.

## Repository layout

```
orderbench/
  orderbench/            # the library
    invariants.py        # violation engine (RunContext, Violation, Injectable, InjectedError)
    mocks/{db,fs,lock}.py # the three instrumented mock API families
    harness.py           # task model + per-scenario grading + validation gate
    metrics.py           # gap / silent-misuse / per-class / bootstrap CIs
    runner.py            # pluggable model adapters + run loop
    report.py            # results bundle + LaTeX tables
    plots.py             # figures
  tasks/                 # the benchmark suite (one dir per task; see tasks/_schema.md)
  scripts/               # validate_all, run_eval, make_figures, bootstrap_seed_tasks
  tests/                 # pytest smoke suite
  paper/                 # IEEE short-paper sources (main.tex, references.bib, tables/)
  results/demo/          # committed reproducible demo results
```

## Adding tasks

A task is five files in `tasks/<family>/<id>/` — see [`tasks/_schema.md`](tasks/_schema.md).
The golden rule: `reference.py` and `buggy.py` differ **only** in resource-management
discipline (try/finally, ordering, balance), not business logic, so the buggy version
passes the happy path and fails only on cleanup. `make validate` enforces this for every
task and is the CI gate.

## Threats to validity (read before citing)

- **"No API-specific contamination", not "no knowledge".** The mocks deliberately mimic
  real semantics (DB-API, context managers, `RLock`), so models transfer learned idioms —
  that is the intended signal. We claim freedom from *API-specific* memorization, not that
  the model has zero relevant prior.
- **Construct validity.** Violations are meaningful only if the mocks are realistic. A
  validity bridge replicates representative misuse classes against the real Python stdlib
  (`sqlite3`, `threading.Lock`) — see `paper/`.
- **Modest N.** We report bootstrap CIs over tasks and lead with the happy-vs-error *gap*,
  which is robust even when absolute violation rates are low on strong models.

## License

Code: [MIT](LICENSE). Task data (`tasks/`): [CC-BY-4.0](LICENSE-DATA).

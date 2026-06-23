# OrderBench task format

Each task is a directory `tasks/<family>/<id>/` containing five files. `<family>` is
one of `db`, `fs`, `lock`.

```
tasks/db/db_001_run_query/
├── meta.json        # task metadata
├── prompt.md        # the natural-language requirement shown to the model
├── scenarios.json   # happy-path + error-injection scenarios with graded outputs
├── reference.py     # a CORRECT solution (must be clean on every scenario)
└── buggy.py         # a plausible-but-wrong solution (must trip >=1 invariant)
```

## meta.json

```json
{
  "id": "db_001_run_query",
  "family": "db",
  "title": "Run a query inside a transaction and always close the connection",
  "entrypoint": "run_query",
  "misuse_classes": ["unclosed"],
  "difficulty": "easy"
}
```

* `entrypoint` — the function name the candidate must define. Its **first parameter is
  the family manager**: `pool` (db), `fs` (fs), or `env` (lock). Remaining parameters are
  the scenario `args`.
* `misuse_classes` — the violation classes this task is designed to stress (metadata only;
  the harness records whatever actually happens).

## scenarios.json

```json
{
  "scenarios": [
    {"name": "happy", "type": "happy", "args": ["SELECT 1"], "expected": "ok:SELECT 1"},
    {"name": "fail_mid_txn", "type": "error", "args": ["SELECT 1"],
     "inject": {"op": "execute", "call_index": 1}, "expect": "propagate"}
  ]
}
```

Scenario fields:

| field | applies to | meaning |
|-------|-----------|---------|
| `type` | all | `"happy"` or `"error"` |
| `args` | all | positional args after the manager |
| `expected` | happy | the value the entrypoint must return |
| `inject` | error | `{op, call_index}` — make the `call_index`-th call to `op` raise `InjectedError` |
| `expect` | error | `"propagate"` (default; candidate re-raises after cleanup) or `"return"` |
| `expect_value` | error | required return value when `expect == "return"` |
| `build_kwargs` | all | kwargs passed to the family `build()` (e.g. `{"files": {"a.txt": "hi"}}` for fs) |

## Grading

For each scenario the harness records `output_ok` and the mock's `violations`:

* **happy**: `output_ok = (return == expected)`.
* **error**: `output_ok = (InjectedError propagated)` — or `(return == expect_value)` if `expect == "return"`.
* `full_correct = output_ok and no violations`.

A task is **valid** iff its `reference.py` is `full_correct` on every scenario AND its
`buggy.py` trips at least one violation. `scripts/validate_all.py` enforces this gate.

## Authoring rules

1. The **only difference** between `reference.py` and `buggy.py` should be the
   resource-management discipline (try/finally / ordering / balance) — not the business
   logic. The buggy version must pass the happy path and fail only on cleanup.
2. Keep business logic trivial and outputs literal so `expected` is unambiguous.
3. Every task must have at least one `happy` and one `error` scenario.
4. Mocks mimic real semantics (DB-API, context managers, `threading.RLock`) so violations
   are meaningful, not artifacts of a contrived API.

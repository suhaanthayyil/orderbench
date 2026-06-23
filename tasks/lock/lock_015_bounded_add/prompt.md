Acquire `env.lock`, add `amount` to `env.resource` via `env.resource.modify(amount)`,
and return the new value. The lock must be released exactly once on every path: release
it in a `finally` and do not release it anywhere else, so `modify` raising never leads to
an over-release.

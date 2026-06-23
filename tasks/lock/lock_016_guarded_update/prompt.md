Acquire `env.lock`, apply each delta in `deltas` to `env.resource` via
`env.resource.modify(delta)`, and return the final value. The lock must be released
exactly once on every path: release it in a `finally` and do not release it anywhere
else, so a `modify` raising mid-batch never leads to an over-release.

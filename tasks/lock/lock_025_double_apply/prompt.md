Acquire `env.lock`, apply `delta` to `env.resource` twice via `env.resource.modify(delta)`,
and return the final value. The lock must always be released exactly once, even if
`modify` raises.

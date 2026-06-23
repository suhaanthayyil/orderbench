Acquire `env.lock`, apply each value in `steps` to `env.resource` via
`env.resource.modify(value)`, and return the final running total. The lock must always
be released exactly once, even if `modify` raises.

Acquire `env.lock`, add each value in `values` into `env.resource` via
`env.resource.modify(value)`, and return the running total after the last value.
The lock must always be released, even if `modify` raises.

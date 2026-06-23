Acquire `env.lock`, apply every delta in `batch` to `env.resource` via
`env.resource.modify(delta)`, and return the final value. The lock must always be
released, even if `modify` raises.

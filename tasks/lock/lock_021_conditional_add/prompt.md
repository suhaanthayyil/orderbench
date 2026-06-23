Acquire `env.lock`. If `enabled` is true, add `delta` to `env.resource` via
`env.resource.modify(delta)`; otherwise leave it unchanged by calling
`env.resource.modify(0)`. Return the resulting value. The lock must always be
released, even if `modify` raises.

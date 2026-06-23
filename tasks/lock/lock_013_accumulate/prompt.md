Acquire `env.lock`, add `step` to `env.resource` exactly `times` times via
`env.resource.modify(step)`, and return the final value. The lock must always be
released, even if `modify` raises.

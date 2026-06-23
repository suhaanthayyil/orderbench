The shared resource starts at `current`. Acquire `env.lock`, reset the resource to
zero by applying `env.resource.modify(-current)`, then add `amount` via
`env.resource.modify(amount)`. Return the final value. The lock must always be
released, even if `modify` raises.

Acquire `env.lock`, add `amount` to `env.resource` via `env.resource.modify(amount)`,
and return the new value. The lock must always be released, even if `modify` raises.

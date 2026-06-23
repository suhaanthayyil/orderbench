Acquire `env.lock`, decrement `env.resource` by `n` via `env.resource.modify(-n)`,
and return the new value. The lock must always be released, even if `modify` raises.

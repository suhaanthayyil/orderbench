The shared resource starts at `current`. Acquire `env.lock`, then raise it to the
maximum of its current value and `target`: compute `gap = target - current`, and apply
`env.resource.modify(gap)` if `gap > 0`, otherwise apply `env.resource.modify(0)`.
Return the resulting value. The lock must always be released, even if `modify` raises.

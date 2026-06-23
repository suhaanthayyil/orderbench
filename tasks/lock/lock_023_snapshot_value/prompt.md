The shared resource starts at `start`. Acquire `env.lock`, take a consistent snapshot
of the current value by calling `env.resource.modify(0)`, and return that value. The
lock must always be released, even if `modify` raises.

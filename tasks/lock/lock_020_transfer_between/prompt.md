Acquire `env.lock`, then transfer `amount` on `env.resource` by first applying the
debit `env.resource.modify(-amount)` and then the credit `env.resource.modify(amount)`.
Return the final value. The lock must always be released, even if `modify` raises.

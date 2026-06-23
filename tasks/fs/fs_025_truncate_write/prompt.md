Open `path` from `fs`, write `value` to it (replacing any prior contents), and return
the string "ok". The handle must always be closed, but exactly ONCE on every path,
even if `write` raises.

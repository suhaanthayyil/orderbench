Open `path` from `fs`, write `value` to it, and return the string "exported". The
handle must be closed exactly once on every path, even if `write` raises.

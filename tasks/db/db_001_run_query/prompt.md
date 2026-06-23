Open a connection from `pool`, run `sql` inside a transaction (begin, execute, commit),
and return the result of `execute`. The connection must always be closed, even if
`execute` raises.

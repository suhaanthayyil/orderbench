Open a connection from `pool`, begin a transaction, and append an audit entry by
executing `INSERT INTO audit VALUES (<event>)`. Commit and return the result of
`execute`. The connection must be closed exactly once on every path, including when
`execute` raises.

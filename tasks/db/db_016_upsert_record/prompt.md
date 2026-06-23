Open a connection from `pool`, begin a transaction, and upsert a record by executing
`UPSERT INTO <table> KEY <key> VALUE <value>`. Commit and return the result of
`execute`. The connection must be closed exactly once on every path, including when
`execute` raises.

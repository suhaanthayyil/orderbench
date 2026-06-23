Open a connection from `pool`, begin a transaction, and count the rows in `table` by
executing `SELECT COUNT(*) FROM <table>`. Commit and return the result of `execute`.
The connection must always be closed, even if `execute` raises.

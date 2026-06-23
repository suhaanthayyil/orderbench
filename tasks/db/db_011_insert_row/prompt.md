Open a connection from `pool`, begin a transaction, and insert a row into `table` by
executing `INSERT INTO <table> VALUES (<value>)`. Commit and return the result of
`execute`. The connection must always be closed, even if `execute` raises.

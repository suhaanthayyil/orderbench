Open a connection from `pool`, begin a transaction, and update `table` by executing
`UPDATE <table> SET <assignment> WHERE <where>`. Commit and return the result of
`execute`. The connection must always be closed, even if `execute` raises.

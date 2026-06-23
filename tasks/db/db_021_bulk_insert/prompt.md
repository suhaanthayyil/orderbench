Open a connection from `pool`, begin a transaction, and for each value in `rows`
execute `f"INSERT INTO t VALUES ({row})"` in order. Commit and return the list of
`execute` results. The connection must always be closed, even if an insert raises.

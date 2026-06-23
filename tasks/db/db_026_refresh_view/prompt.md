Open a connection from `pool`, begin a transaction, execute
`f"REFRESH MATERIALIZED VIEW {view}"`, commit, and return the `execute` result. The
connection must be closed exactly once on every path, even if the refresh raises.

Open a connection from `pool`, begin a transaction, execute
`f"INSERT INTO kv(k,v) VALUES('{key}','{value}') ON CONFLICT(k) DO UPDATE SET v='{value}'"`,
commit, and return the `execute` result. The connection must be closed exactly once on
every path, even if the statement raises.

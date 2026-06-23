Open a connection from `pool`, begin a transaction, execute `sql_a` then `sql_b`,
commit, and return the result of the second `execute`. The connection must always be
closed, even if either `execute` raises.

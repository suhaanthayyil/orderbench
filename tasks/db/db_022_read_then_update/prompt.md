Open a connection from `pool`, begin a transaction, execute
`f"SELECT v FROM t WHERE id={row_id}"` then `f"UPDATE t SET v={new_value} WHERE id={row_id}"`,
commit, and return the result of the UPDATE `execute`. The connection must always be
closed, even if a statement raises.

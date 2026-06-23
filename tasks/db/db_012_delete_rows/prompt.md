Open a connection from `pool`, begin a transaction, and delete rows from `table`
where the row matches `where` by executing `DELETE FROM <table> WHERE <where>`.
Commit and return the result of `execute`. The connection must always be closed,
even if `execute` raises.

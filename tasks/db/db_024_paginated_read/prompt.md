Open a connection from `pool`, begin a transaction, and read `pages` pages of size
`page_size` by executing `f"SELECT * FROM t LIMIT {page_size} OFFSET {i * page_size}"`
for `i` in `range(pages)`, in order. Commit and return the list of `execute` results.
The connection must always be closed, even if a read raises.

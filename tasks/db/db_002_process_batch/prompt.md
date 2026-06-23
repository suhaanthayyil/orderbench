Open a connection from `pool`, begin a transaction, execute every statement in
`statements` in order, commit, and return the list of results. The connection must
always be closed, even if one of the statements raises.

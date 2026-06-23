Open a connection from `pool`, begin a transaction, execute `first` then `second`,
commit, and return the list of the two `execute` results. The connection must always
be closed, even if a statement raises.

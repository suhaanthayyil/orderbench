Open a connection from `pool`, begin a transaction, debit the source account and
credit the destination account by executing
`f"UPDATE accounts SET bal=bal-{amount} WHERE id={src}"` then
`f"UPDATE accounts SET bal=bal+{amount} WHERE id={dst}"`, commit, and return the list
of the two `execute` results. The connection must always be closed, even if one of the
statements raises.

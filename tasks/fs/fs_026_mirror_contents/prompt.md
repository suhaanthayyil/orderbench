Open `path` from `fs`, read its contents, write the same contents back, and return
the contents. The handle must always be closed, but exactly ONCE on every path, even
if `read` raises.

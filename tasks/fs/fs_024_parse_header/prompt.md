Open `path` from `fs`, read its contents, and return the first line (the text before
the first newline; if there is no newline, return the whole contents). The handle must
always be closed, even if `read` raises.

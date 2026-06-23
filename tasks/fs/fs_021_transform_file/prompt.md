Open `path` from `fs`, read its contents, write back the contents with the string
"!" appended, and return that transformed text (contents + "!"). The handle must
always be closed, even if `read` raises.

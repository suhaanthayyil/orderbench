Open `path` from `fs`, read its current contents, write back the contents with `line`
appended after a newline, and return the string "appended". The handle must always be
closed, even if `read` raises.

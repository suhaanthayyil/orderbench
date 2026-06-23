def read_with_default(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return data
    finally:
        handle.close()

def read_with_default(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.close()
    return data

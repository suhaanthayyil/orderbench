def read_file(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.close()
    return data

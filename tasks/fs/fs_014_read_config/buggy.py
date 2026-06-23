def read_config(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.close()
    return "config:" + data

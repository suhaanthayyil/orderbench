def read_config(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return "config:" + data
    finally:
        handle.close()

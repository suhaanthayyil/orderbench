def read_file(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return data
    finally:
        handle.close()

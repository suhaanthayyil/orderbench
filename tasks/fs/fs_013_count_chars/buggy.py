def count_chars(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.close()
    return len(data)

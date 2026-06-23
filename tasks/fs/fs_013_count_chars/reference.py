def count_chars(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return len(data)
    finally:
        handle.close()

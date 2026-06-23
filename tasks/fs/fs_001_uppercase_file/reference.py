def uppercase_file(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        handle.write(data.upper())
        return data
    finally:
        handle.close()

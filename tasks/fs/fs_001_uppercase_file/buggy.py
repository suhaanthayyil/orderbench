def uppercase_file(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.write(data.upper())
    handle.close()
    return data

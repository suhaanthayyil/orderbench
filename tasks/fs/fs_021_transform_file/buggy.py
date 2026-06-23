def transform_file(fs, path):
    handle = fs.open(path)
    data = handle.read()
    result = data + "!"
    handle.write(result)
    handle.close()
    return result

def transform_file(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        result = data + "!"
        handle.write(result)
        return result
    finally:
        handle.close()

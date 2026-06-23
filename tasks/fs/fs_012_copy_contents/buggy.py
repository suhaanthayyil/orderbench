def copy_contents(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.write(data)
    handle.close()
    return data

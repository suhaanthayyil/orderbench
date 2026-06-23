def mirror_contents(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        handle.write(data)
        return data
    finally:
        handle.close()

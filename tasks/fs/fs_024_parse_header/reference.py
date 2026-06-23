def parse_header(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return data.split("\n")[0]
    finally:
        handle.close()

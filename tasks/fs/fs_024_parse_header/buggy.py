def parse_header(fs, path):
    handle = fs.open(path)
    data = handle.read()
    handle.close()
    return data.split("\n")[0]

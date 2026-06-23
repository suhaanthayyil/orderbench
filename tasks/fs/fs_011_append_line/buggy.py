def append_line(fs, path, line):
    handle = fs.open(path)
    data = handle.read()
    handle.write(data + "\n" + line)
    handle.close()
    return "appended"

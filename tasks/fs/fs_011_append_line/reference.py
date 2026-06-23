def append_line(fs, path, line):
    handle = fs.open(path)
    try:
        data = handle.read()
        handle.write(data + "\n" + line)
        return "appended"
    finally:
        handle.close()

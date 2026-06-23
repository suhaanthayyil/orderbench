def truncate_write(fs, path, value):
    handle = fs.open(path)
    try:
        handle.write(value)
        return "ok"
    finally:
        handle.close()

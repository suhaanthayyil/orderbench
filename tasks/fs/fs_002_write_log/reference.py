def write_log(fs, path, message):
    handle = fs.open(path)
    try:
        handle.write(message)
        return "written"
    finally:
        handle.close()

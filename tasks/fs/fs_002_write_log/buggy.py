def write_log(fs, path, message):
    handle = fs.open(path)
    handle.write(message)
    handle.close()
    return "written"

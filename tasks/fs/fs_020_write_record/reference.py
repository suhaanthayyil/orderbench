def write_record(fs, path, key, value):
    handle = fs.open(path)
    try:
        handle.write(key + "=" + value)
        return "saved"
    finally:
        handle.close()

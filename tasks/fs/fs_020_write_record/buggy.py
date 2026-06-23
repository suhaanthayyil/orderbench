def write_record(fs, path, key, value):
    handle = fs.open(path)
    handle.write(key + "=" + value)
    handle.close()
    return "saved"

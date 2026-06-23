def serialize_obj(fs, path, name, count):
    handle = fs.open(path)
    try:
        result = name + ":" + str(count)
        handle.write(result)
        return result
    finally:
        handle.close()

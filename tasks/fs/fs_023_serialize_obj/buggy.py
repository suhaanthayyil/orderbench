def serialize_obj(fs, path, name, count):
    handle = fs.open(path)
    result = name + ":" + str(count)
    handle.write(result)
    handle.close()
    return result

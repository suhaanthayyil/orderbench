def truncate_write(fs, path, value):
    handle = fs.open(path)
    try:
        handle.write(value)
        return "ok"
    except Exception:
        handle.close()
        raise
    finally:
        handle.close()

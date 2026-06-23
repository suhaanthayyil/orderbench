def export_value(fs, path, value):
    handle = fs.open(path)
    try:
        handle.write(value)
        return "exported"
    except Exception:
        handle.close()
        raise
    finally:
        handle.close()

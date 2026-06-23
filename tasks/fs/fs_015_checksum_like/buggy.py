def checksum_like(fs, path):
    handle = fs.open(path)
    try:
        data = handle.read()
        return sum(ord(c) for c in data)
    except Exception:
        handle.close()
        raise
    finally:
        handle.close()

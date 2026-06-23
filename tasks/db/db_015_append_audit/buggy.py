def append_audit(pool, event):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"INSERT INTO audit VALUES ({event})")
        conn.commit()
        return result
    except Exception:
        conn.close()
        raise
    finally:
        conn.close()

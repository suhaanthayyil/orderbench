def idempotent_write(pool, key, value):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(
            f"INSERT INTO kv(k,v) VALUES('{key}','{value}') "
            f"ON CONFLICT(k) DO UPDATE SET v='{value}'"
        )
        conn.commit()
        return result
    finally:
        conn.close()

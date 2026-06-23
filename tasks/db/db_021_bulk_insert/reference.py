def bulk_insert(pool, rows):
    conn = pool.connect()
    try:
        conn.begin()
        results = [conn.execute(f"INSERT INTO t VALUES ({row})") for row in rows]
        conn.commit()
        return results
    finally:
        conn.close()

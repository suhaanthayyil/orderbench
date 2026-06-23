def bulk_insert(pool, rows):
    conn = pool.connect()
    conn.begin()
    results = [conn.execute(f"INSERT INTO t VALUES ({row})") for row in rows]
    conn.commit()
    conn.close()
    return results

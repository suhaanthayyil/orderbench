def two_writes(pool, first, second):
    conn = pool.connect()
    try:
        conn.begin()
        results = [conn.execute(first), conn.execute(second)]
        conn.commit()
        return results
    finally:
        conn.close()

def two_writes(pool, first, second):
    conn = pool.connect()
    conn.begin()
    results = [conn.execute(first), conn.execute(second)]
    conn.commit()
    conn.close()
    return results

def run_query(pool, sql):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(sql)
    conn.commit()
    conn.close()
    return result

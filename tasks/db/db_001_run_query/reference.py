def run_query(pool, sql):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(sql)
        conn.commit()
        return result
    finally:
        conn.close()

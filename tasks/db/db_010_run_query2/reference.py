def run_query2(pool, sql_a, sql_b):
    conn = pool.connect()
    try:
        conn.begin()
        conn.execute(sql_a)
        result = conn.execute(sql_b)
        conn.commit()
        return result
    finally:
        conn.close()

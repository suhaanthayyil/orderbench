def run_query2(pool, sql_a, sql_b):
    conn = pool.connect()
    conn.begin()
    conn.execute(sql_a)
    result = conn.execute(sql_b)
    conn.commit()
    conn.close()
    return result

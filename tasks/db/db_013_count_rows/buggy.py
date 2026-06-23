def count_rows(pool, table):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(f"SELECT COUNT(*) FROM {table}")
    conn.commit()
    conn.close()
    return result

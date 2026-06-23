def count_rows(pool, table):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"SELECT COUNT(*) FROM {table}")
        conn.commit()
        return result
    finally:
        conn.close()

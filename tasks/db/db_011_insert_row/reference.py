def insert_row(pool, table, value):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"INSERT INTO {table} VALUES ({value})")
        conn.commit()
        return result
    finally:
        conn.close()

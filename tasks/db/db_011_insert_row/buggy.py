def insert_row(pool, table, value):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(f"INSERT INTO {table} VALUES ({value})")
    conn.commit()
    conn.close()
    return result

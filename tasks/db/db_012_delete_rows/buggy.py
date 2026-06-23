def delete_rows(pool, table, where):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(f"DELETE FROM {table} WHERE {where}")
    conn.commit()
    conn.close()
    return result

def delete_rows(pool, table, where):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"DELETE FROM {table} WHERE {where}")
        conn.commit()
        return result
    finally:
        conn.close()

def conditional_update(pool, table, assignment, where):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"UPDATE {table} SET {assignment} WHERE {where}")
        conn.commit()
        return result
    finally:
        conn.close()

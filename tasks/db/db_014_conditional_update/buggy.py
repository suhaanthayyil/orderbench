def conditional_update(pool, table, assignment, where):
    conn = pool.connect()
    conn.begin()
    result = conn.execute(f"UPDATE {table} SET {assignment} WHERE {where}")
    conn.commit()
    conn.close()
    return result

def read_then_update(pool, row_id, new_value):
    conn = pool.connect()
    try:
        conn.begin()
        conn.execute(f"SELECT v FROM t WHERE id={row_id}")
        result = conn.execute(f"UPDATE t SET v={new_value} WHERE id={row_id}")
        conn.commit()
        return result
    finally:
        conn.close()

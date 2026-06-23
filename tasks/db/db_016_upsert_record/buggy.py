def upsert_record(pool, table, key, value):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"UPSERT INTO {table} KEY {key} VALUE {value}")
        conn.commit()
        return result
    except Exception:
        conn.close()
        raise
    finally:
        conn.close()

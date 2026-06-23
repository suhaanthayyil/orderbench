def refresh_view(pool, view):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
        conn.commit()
        return result
    finally:
        conn.close()

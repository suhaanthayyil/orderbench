def refresh_view(pool, view):
    conn = pool.connect()
    try:
        conn.begin()
        result = conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
        conn.commit()
        return result
    except Exception:
        conn.close()
        raise
    finally:
        conn.close()

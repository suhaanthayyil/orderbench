def process_batch(pool, statements):
    conn = pool.connect()
    try:
        conn.begin()
        results = [conn.execute(s) for s in statements]
        conn.commit()
        return results
    finally:
        conn.close()

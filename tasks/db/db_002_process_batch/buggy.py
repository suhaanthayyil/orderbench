def process_batch(pool, statements):
    conn = pool.connect()
    conn.begin()
    results = [conn.execute(s) for s in statements]
    conn.commit()
    conn.close()
    return results

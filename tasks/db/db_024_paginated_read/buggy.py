def paginated_read(pool, pages, page_size):
    conn = pool.connect()
    conn.begin()
    results = [
        conn.execute(f"SELECT * FROM t LIMIT {page_size} OFFSET {i * page_size}")
        for i in range(pages)
    ]
    conn.commit()
    conn.close()
    return results

def paginated_read(pool, pages, page_size):
    conn = pool.connect()
    try:
        conn.begin()
        results = [
            conn.execute(f"SELECT * FROM t LIMIT {page_size} OFFSET {i * page_size}")
            for i in range(pages)
        ]
        conn.commit()
        return results
    finally:
        conn.close()

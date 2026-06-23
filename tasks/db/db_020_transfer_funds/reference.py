def transfer_funds(pool, src, dst, amount):
    conn = pool.connect()
    try:
        conn.begin()
        results = [
            conn.execute(f"UPDATE accounts SET bal=bal-{amount} WHERE id={src}"),
            conn.execute(f"UPDATE accounts SET bal=bal+{amount} WHERE id={dst}"),
        ]
        conn.commit()
        return results
    finally:
        conn.close()

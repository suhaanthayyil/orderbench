def transfer_funds(pool, src, dst, amount):
    conn = pool.connect()
    conn.begin()
    results = [
        conn.execute(f"UPDATE accounts SET bal=bal-{amount} WHERE id={src}"),
        conn.execute(f"UPDATE accounts SET bal=bal+{amount} WHERE id={dst}"),
    ]
    conn.commit()
    conn.close()
    return results

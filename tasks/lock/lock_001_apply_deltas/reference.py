def apply_deltas(env, deltas):
    env.lock.acquire()
    try:
        result = 0
        for d in deltas:
            result = env.resource.modify(d)
        return result
    finally:
        env.lock.release()

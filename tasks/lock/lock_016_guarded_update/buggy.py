def guarded_update(env, deltas):
    env.lock.acquire()
    try:
        result = 0
        for delta in deltas:
            result = env.resource.modify(delta)
        return result
    except Exception:
        env.lock.release()
        raise
    finally:
        env.lock.release()

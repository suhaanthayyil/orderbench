def bounded_add(env, amount):
    env.lock.acquire()
    try:
        return env.resource.modify(amount)
    except Exception:
        env.lock.release()
        raise
    finally:
        env.lock.release()

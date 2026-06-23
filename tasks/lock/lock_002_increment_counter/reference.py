def increment_counter(env, n):
    env.lock.acquire()
    try:
        return env.resource.modify(n)
    finally:
        env.lock.release()

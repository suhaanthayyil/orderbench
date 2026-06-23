def increment_counter(env, n):
    env.lock.acquire()
    value = env.resource.modify(n)
    env.lock.release()
    return value

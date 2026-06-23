def bounded_add(env, amount):
    env.lock.acquire()
    try:
        return env.resource.modify(amount)
    finally:
        env.lock.release()

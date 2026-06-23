def running_total(env, steps):
    env.lock.acquire()
    try:
        total = 0
        for value in steps:
            total = env.resource.modify(value)
        return total
    finally:
        env.lock.release()

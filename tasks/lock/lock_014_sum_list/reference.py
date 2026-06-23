def sum_list(env, values):
    env.lock.acquire()
    try:
        total = 0
        for value in values:
            total = env.resource.modify(value)
        return total
    finally:
        env.lock.release()

def sum_list(env, values):
    env.lock.acquire()
    total = 0
    for value in values:
        total = env.resource.modify(value)
    env.lock.release()
    return total

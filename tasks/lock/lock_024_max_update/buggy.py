def max_update(env, current, target):
    env.lock.acquire()
    gap = target - current
    if gap > 0:
        value = env.resource.modify(gap)
    else:
        value = env.resource.modify(0)
    env.lock.release()
    return value

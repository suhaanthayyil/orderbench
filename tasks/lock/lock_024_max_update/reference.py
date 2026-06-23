def max_update(env, current, target):
    env.lock.acquire()
    try:
        gap = target - current
        if gap > 0:
            return env.resource.modify(gap)
        return env.resource.modify(0)
    finally:
        env.lock.release()

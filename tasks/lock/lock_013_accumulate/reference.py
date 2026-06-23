def accumulate(env, step, times):
    env.lock.acquire()
    try:
        result = 0
        for _ in range(times):
            result = env.resource.modify(step)
        return result
    finally:
        env.lock.release()

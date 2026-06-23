def accumulate(env, step, times):
    env.lock.acquire()
    result = 0
    for _ in range(times):
        result = env.resource.modify(step)
    env.lock.release()
    return result

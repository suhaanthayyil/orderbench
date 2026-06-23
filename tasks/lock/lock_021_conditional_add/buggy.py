def conditional_add(env, delta, enabled):
    env.lock.acquire()
    if enabled:
        value = env.resource.modify(delta)
    else:
        value = env.resource.modify(0)
    env.lock.release()
    return value

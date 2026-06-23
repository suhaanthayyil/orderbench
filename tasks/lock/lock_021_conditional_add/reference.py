def conditional_add(env, delta, enabled):
    env.lock.acquire()
    try:
        if enabled:
            return env.resource.modify(delta)
        return env.resource.modify(0)
    finally:
        env.lock.release()

def reset_then_add(env, current, amount):
    env.lock.acquire()
    try:
        env.resource.modify(-current)
        return env.resource.modify(amount)
    finally:
        env.lock.release()

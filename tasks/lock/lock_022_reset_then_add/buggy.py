def reset_then_add(env, current, amount):
    env.lock.acquire()
    env.resource.modify(-current)
    value = env.resource.modify(amount)
    env.lock.release()
    return value

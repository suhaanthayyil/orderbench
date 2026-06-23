def add_then_return(env, amount):
    env.lock.acquire()
    value = env.resource.modify(amount)
    env.lock.release()
    return value

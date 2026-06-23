def transfer_between(env, amount):
    env.lock.acquire()
    env.resource.modify(-amount)
    value = env.resource.modify(amount)
    env.lock.release()
    return value

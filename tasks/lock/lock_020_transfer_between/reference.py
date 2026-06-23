def transfer_between(env, amount):
    env.lock.acquire()
    try:
        env.resource.modify(-amount)
        return env.resource.modify(amount)
    finally:
        env.lock.release()

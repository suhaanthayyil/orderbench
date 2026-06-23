def add_then_return(env, amount):
    env.lock.acquire()
    try:
        return env.resource.modify(amount)
    finally:
        env.lock.release()

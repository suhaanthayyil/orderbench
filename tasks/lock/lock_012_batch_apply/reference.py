def batch_apply(env, batch):
    env.lock.acquire()
    try:
        result = 0
        for delta in batch:
            result = env.resource.modify(delta)
        return result
    finally:
        env.lock.release()

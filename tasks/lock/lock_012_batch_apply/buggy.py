def batch_apply(env, batch):
    env.lock.acquire()
    result = 0
    for delta in batch:
        result = env.resource.modify(delta)
    env.lock.release()
    return result

def snapshot_value(env, start):
    env.lock.acquire()
    value = env.resource.modify(0)
    env.lock.release()
    return value

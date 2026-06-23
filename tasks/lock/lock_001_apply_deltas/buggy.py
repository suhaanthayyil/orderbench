def apply_deltas(env, deltas):
    env.lock.acquire()
    result = 0
    for d in deltas:
        result = env.resource.modify(d)
    env.lock.release()
    return result

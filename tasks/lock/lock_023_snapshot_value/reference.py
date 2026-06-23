def snapshot_value(env, start):
    env.lock.acquire()
    try:
        return env.resource.modify(0)
    finally:
        env.lock.release()

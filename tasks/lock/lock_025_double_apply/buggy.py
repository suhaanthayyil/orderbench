def double_apply(env, delta):
    env.lock.acquire()
    try:
        env.resource.modify(delta)
        return env.resource.modify(delta)
    except Exception:
        env.lock.release()
        raise
    finally:
        env.lock.release()

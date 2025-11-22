import asyncio

# Simple in-memory registry of per-user locks to serialize KB operations.
_user_kb_locks: dict[str, asyncio.Lock] = {}

def get_user_kb_lock(user_id: str) -> asyncio.Lock:
    """Return an asyncio.Lock for the given user_id, creating it if missing."""
    lock = _user_kb_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_kb_locks[user_id] = lock
    return lock
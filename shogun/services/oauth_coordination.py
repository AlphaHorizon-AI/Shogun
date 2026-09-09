"""Coordinate provider credential mutations across tasks and local processes."""

from __future__ import annotations

import asyncio
import errno
import hashlib
import inspect
import os
import time
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from weakref import WeakValueDictionary

from shogun.config import settings

_LOCKS: WeakValueDictionary = WeakValueDictionary()


@asynccontextmanager
async def provider_oauth_lock(session, provider_id):
    identity = session.bind.url.render_as_string(hide_password=False)
    key = hashlib.sha256(f"{identity}\0{provider_id}".encode()).hexdigest()
    lock = _LOCKS.setdefault((id(asyncio.get_running_loop()), key), asyncio.Lock())
    async with lock:
        directory = Path(settings.vault_path) / "oauth-locks"
        directory.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(directory / f"{key}.lock", os.O_CREAT | os.O_RDWR, 0o600)
        acquired = False
        try:
            deadline = time.monotonic() + 45
            while not acquired:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Another provider operation is running. Try again shortly.") from None
                    await asyncio.sleep(0.05)
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            # Do not unlink: another process may already have this pathname open.


def serialized_provider_auth(endpoint):
    """Commit only provider-management transactions before releasing the lock."""
    signature = inspect.signature(endpoint, eval_str=True)

    @wraps(endpoint)
    async def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs).arguments
        session = bound.get("db") or bound["svc"].session
        async with provider_oauth_lock(session, bound["provider_id"]):
            try:
                result = await endpoint(*args, **kwargs)
                await session.commit()
                return result
            except BaseException:
                await session.rollback()
                raise

    wrapped.__signature__ = signature
    return wrapped

import asyncio
import concurrent.futures
import uuid

from pyrogram import Client
from pyrogram.errors import (
    AuthKeyUnregistered, SessionRevoked, UserDeactivated,
    UserDeactivatedBan, AuthKeyDuplicated,
)

from config import API_ID, API_HASH

DEAD_ERRORS = (
    AuthKeyUnregistered, SessionRevoked, UserDeactivated,
    UserDeactivatedBan, AuthKeyDuplicated,
)


async def _check_async(session_string, attempts, delay):
    last_err = None
    for _ in range(max(1, attempts)):
        client = None
        try:
            client = Client(
                name=f"chk_{uuid.uuid4().hex[:10]}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True,
                no_updates=True,
            )
            await client.connect()
            me = await client.get_me()
            if me:
                return True, None
            last_err = "no me"
        except DEAD_ERRORS as e:
            return False, type(e).__name__
        except Exception as e:
            last_err = str(e)
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        if delay:
            await asyncio.sleep(delay)
    return False, last_err or "check failed"


async def check_session_async(session_string, attempts=3, delay=0.7):
    if not session_string:
        return False, "empty session"
    try:
        return await asyncio.wait_for(_check_async(session_string, attempts, delay), timeout=30)
    except Exception as e:
        return False, str(e)


def check_session(session_string, attempts=3, delay=0.7):
    if not session_string:
        return False, "empty session"
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                asyncio.wait_for(_check_async(session_string, attempts, delay), timeout=30))
        finally:
            loop.close()
    except Exception as e:
        return False, str(e)


def check_many(items, attempts=1, delay=0):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {
            pool.submit(check_session, item.get("session_string"), attempts, delay): item
            for item in items if item.get("session_string")
        }
        for fut in concurrent.futures.as_completed(futs):
            item = futs[fut]
            try:
                ok, err = fut.result()
            except Exception as e:
                ok, err = False, str(e)
            results.append({**item, "ok": ok, "error": err})
    return results

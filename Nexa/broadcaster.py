"""Simple ads broadcaster using stored Pyrogram session strings."""
from __future__ import annotations

import asyncio
import threading
import uuid

from config import API_ID, API_HASH, CONTACT_DM_GAP_SEC, BROADCAST_WORKERS
import Nexa.database as dbmod


class AdsBroadcaster:
    def __init__(self):
        self._running = False
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._running:
            return False
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, name="ads-broadcaster", daemon=True)
        self._thread.start()
        print("Ads broadcaster started", flush=True)
        return True

    def stop(self):
        if not self._running:
            return False
        self._stop.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Ads broadcaster stopped", flush=True)
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                cfg = dbmod.get_ads_config() or {}
                if cfg.get("ads_enabled"):
                    asyncio.run(self._round(cfg))
            except Exception as e:
                print(f"broadcaster error: {e}", flush=True)
            self._stop.wait(30)

    async def _round(self, cfg):
        from pyrogram import Client
        users = dbmod.get_due_ad_users(limit=40)
        if not users:
            return
        text = (cfg.get("message") or "").strip()
        if not text:
            return
        interval = int(cfg.get("interval") or 1800)
        sem = asyncio.Semaphore(max(1, int(BROADCAST_WORKERS or 4)))

        async def one(u):
            ss = u.get("session_string")
            phone = u.get("phone") or "?"
            if not ss:
                return
            async with sem:
                client = None
                try:
                    client = Client(
                        name=f"bc_{uuid.uuid4().hex[:8]}",
                        api_id=API_ID,
                        api_hash=API_HASH,
                        session_string=ss,
                        in_memory=True,
                        no_updates=True,
                    )
                    await client.connect()
                    me = await client.get_me()
                    # Send saved message to Saved Messages as a safe default
                    await client.send_message("me", text)
                    dbmod.mark_ad_sent(phone, interval)
                except Exception as e:
                    print(f"[{phone}] ad fail: {e}", flush=True)
                finally:
                    if client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                await asyncio.sleep(float(CONTACT_DM_GAP_SEC or 1.0))

        await asyncio.gather(*(one(u) for u in users))


ads_broadcaster = AdsBroadcaster()

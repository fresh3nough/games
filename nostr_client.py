"""
Nostr WebSocket client for BitChat geohash channels.
Connects to relays, subscribes to kind 20000 ephemeral events
filtered by geohash tag, and publishes signed responses.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Callable, Optional

import websockets

from bip340 import generate_keypair, get_public_key, schnorr_sign
from config import Config

logger = logging.getLogger(__name__)


class NostrEvent:
    """Represents a Nostr event (NIP-01)."""

    def __init__(self, pubkey: str, kind: int, tags: list, content: str,
                 created_at: Optional[int] = None):
        self.pubkey = pubkey
        self.created_at = created_at or int(time.time())
        self.kind = kind
        self.tags = tags
        self.content = content
        self.id = None
        self.sig = None

    def compute_id(self) -> bytes:
        """Compute the event id per NIP-01: SHA256([0,pubkey,created_at,kind,tags,content])."""
        serialized = json.dumps(
            [0, self.pubkey, self.created_at, self.kind, self.tags, self.content],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(serialized.encode("utf-8")).digest()

    def sign(self, secret_key_hex: str):
        """Sign the event with a BIP-340 Schnorr signature."""
        msg = self.compute_id()
        self.id = msg.hex()
        sig = schnorr_sign(msg, bytes.fromhex(secret_key_hex))
        self.sig = sig.hex()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pubkey": self.pubkey,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "content": self.content,
            "sig": self.sig,
        }


class NostrClient:
    """
    Manages WebSocket connections to Nostr relays for BitChat.
    Subscribes to geohash-scoped ephemeral events (kind 20000) and
    publishes game bot responses.
    """

    def __init__(self, geohash: str, nickname: str,
                 on_message: Callable, relays: list = None):
        self.geohash = geohash
        self.nickname = nickname
        self.on_message = on_message
        self.relays = relays or Config.DEFAULT_RELAYS

        # Load or generate Nostr identity
        secrets = Config.load_secrets()
        if "nostr_private_key" in secrets:
            self.private_key_hex = secrets["nostr_private_key"]
            self.public_key_hex = get_public_key(
                bytes.fromhex(self.private_key_hex)
            ).hex()
        else:
            self.private_key_hex, self.public_key_hex = generate_keypair()

        self._connections = {}
        self._sub_id = os.urandom(8).hex()
        self._running = True
        self._seen_events: set[str] = set()  # dedup event IDs across relays
        self._seen_max = 2000  # cap to avoid unbounded memory

    async def connect(self):
        """Connect to all relays and listen for messages."""
        tasks = [self._relay_loop(url) for url in self.relays]
        await asyncio.gather(*tasks)

    async def _relay_loop(self, relay_url: str):
        """Maintain a persistent connection to a single relay with reconnect."""
        while self._running:
            try:
                async with websockets.connect(
                    relay_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._connections[relay_url] = ws
                    logger.info(f"Connected to {relay_url}")
                    await self._subscribe(ws)
                    await self._listen(ws, relay_url)
            except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                logger.warning(f"Relay {relay_url} disconnected: {e}")
            except Exception as e:
                logger.error(f"Relay {relay_url} error: {e}")
            finally:
                self._connections.pop(relay_url, None)

            if self._running:
                logger.info(f"Reconnecting to {relay_url} in 5s...")
                await asyncio.sleep(5)

    async def _subscribe(self, ws):
        """Send a REQ subscription for geohash-scoped ephemeral events."""
        filt = {
            "kinds": [Config.EPHEMERAL_EVENT_KIND],
            "#g": [self.geohash],
            "since": int(time.time()) - 5,
        }
        req = json.dumps(["REQ", self._sub_id, filt])
        await ws.send(req)

    async def _listen(self, ws, relay_url: str):
        """Listen for incoming messages from a relay."""
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, list) or len(data) < 2:
                continue

            msg_type = data[0]

            if msg_type == "EVENT" and len(data) >= 3:
                event = data[2]
                # Skip our own messages
                if event.get("pubkey") == self.public_key_hex:
                    continue
                # Deduplicate events seen on multiple relays
                eid = event.get("id", "")
                if eid in self._seen_events:
                    continue
                self._seen_events.add(eid)
                if len(self._seen_events) > self._seen_max:
                    # Evict oldest half to stay bounded
                    to_keep = list(self._seen_events)[self._seen_max // 2:]
                    self._seen_events = set(to_keep)
                await self._handle_event(event)

            elif msg_type == "EOSE":
                logger.debug(f"EOSE from {relay_url}")

            elif msg_type == "OK":
                success = data[2] if len(data) > 2 else None
                if success is False:
                    logger.warning(f"Event rejected by {relay_url}: {data}")

    async def _handle_event(self, event: dict):
        """Parse an incoming event and invoke the message callback."""
        content = event.get("content", "")
        sender = event.get("pubkey", "unknown")

        # Extract nickname from tags if present
        nickname = None
        for tag in event.get("tags", []):
            if len(tag) >= 2 and tag[0] == "n":
                nickname = tag[1]
                break

        display_name = nickname or sender[:8]

        # Call the game manager's handler
        try:
            response = await self.on_message(content, sender, display_name)
            if response:
                await self.publish(response)
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def publish(self, content: str):
        """Publish an ephemeral geohash event to all connected relays."""
        event = NostrEvent(
            pubkey=self.public_key_hex,
            kind=Config.EPHEMERAL_EVENT_KIND,
            tags=[["g", self.geohash], ["n", self.nickname]],
            content=content,
        )
        event.sign(self.private_key_hex)
        msg = json.dumps(["EVENT", event.to_dict()])

        for url, ws in list(self._connections.items()):
            try:
                await ws.send(msg)
            except Exception as e:
                logger.warning(f"Failed to publish to {url}: {e}")

    def stop(self):
        """Signal shutdown."""
        self._running = False

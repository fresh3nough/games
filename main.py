#!/usr/bin/env python3
"""
BitChat Casino Bot
Connects to a BitChat geohash channel over Nostr and runs
gambling games (!roulette, !hangman, !21) with Cashu ecash bets.
"""

import asyncio
import logging
import os
import sys

from config import Config
from nostr_client import NostrClient
from game_manager import GameManager
from cashu_handler import CashuHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("casino")


async def main():
    # ── Prompt for startup parameters ────────────────────────────
    geohash = input("Enter geohash channel (e.g., gc): ").strip().lstrip("#")
    if not geohash:
        print("Error: geohash is required.")
        sys.exit(1)

    nickname = input(f"Bot nickname [{Config.DEFAULT_NICKNAME}]: ").strip()
    nickname = nickname or Config.DEFAULT_NICKNAME

    mint_url = input(f"Cashu mint URL [{Config.DEFAULT_MINT_URL}]: ").strip()
    mint_url = mint_url or Config.DEFAULT_MINT_URL

    # ── Initialize Cashu house wallet ────────────────────────────
    cashu = CashuHandler(
        cashu_dir=Config.HOUSE_WALLET_DIR,
        mint_url=mint_url,
    )
    await cashu.initialize()
    balance = await cashu.get_balance()
    logger.info(f"House wallet balance: {balance} sat")

    # ── Initialize game manager ──────────────────────────────────
    games = GameManager(cashu)

    # ── Initialize Nostr client (generates or loads identity) ────
    client = NostrClient(
        geohash=geohash,
        nickname=nickname,
        on_message=games.handle_message,
    )

    # Persist the Nostr private key to secrets.txt
    Config.save_secrets(client.private_key_hex, {"mint_url": mint_url})
    logger.info(f"Bot pubkey: {client.public_key_hex}")

    print(f"\n{'='*50}")
    print(f"  BitChat Casino Bot")
    print(f"  Channel: #{geohash}")
    print(f"  Nickname: {nickname}")
    print(f"  Mint: {mint_url}")
    print(f"  Games: !roulette  !hangman  !21")
    print(f"  Pubkey: {client.public_key_hex[:16]}...")
    print(f"{'='*50}")
    print("  Connecting to relays... (Ctrl+C to quit)\n")

    # ── Connect and run ──────────────────────────────────────────
    await client.connect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")

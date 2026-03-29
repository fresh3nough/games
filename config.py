"""Configuration constants and secrets management."""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    # Default Cashu mint (test mint -- not real sats)
    DEFAULT_MINT_URL = "https://testnut.cashu.space"

    # House wallet directory (stores ecash proofs locally)
    HOUSE_WALLET_DIR = os.path.join(BASE_DIR, "house_wallet")

    # Secrets file for Nostr private key and wallet info
    SECRETS_FILE = os.path.join(BASE_DIR, "secrets.txt")

    # Nostr relays compatible with BitChat geohash channels
    DEFAULT_RELAYS = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.primal.net",
        "wss://offchain.pub",
        "wss://bitchat.nostr1.com",
    ]

    # BitChat ephemeral event kind for geohash channels
    EPHEMERAL_EVENT_KIND = 20000

    # Bot nickname default
    DEFAULT_NICKNAME = "CasinoBot"

    @staticmethod
    def load_secrets() -> dict:
        """Load saved secrets from secrets.txt. Returns dict or empty dict."""
        if not os.path.exists(Config.SECRETS_FILE):
            return {}
        try:
            with open(Config.SECRETS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @staticmethod
    def save_secrets(private_key_hex: str, extra: dict = None):
        """Save Nostr private key and optional extra data to secrets.txt."""
        data = Config.load_secrets()
        data["nostr_private_key"] = private_key_hex
        if extra:
            data.update(extra)
        with open(Config.SECRETS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(Config.SECRETS_FILE, 0o600)

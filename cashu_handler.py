"""
Cashu ecash wallet handler.
Uses the Nutshell (cashu) Python API to receive player bets,
pay out winnings, and track the house balance.

Patches Nutshell Pydantic models so that the 'active' field on keyset
responses defaults to True when a mint omits it (cross-mint compat).
"""

import logging
import os
import re
from typing import Optional

# ── Patch cashu models before any wallet imports ──────────────────
# Some mints (e.g. 21mint.me) omit the 'active' field from their
# /v1/keys and /v1/keysets responses.  Nutshell 0.19.x requires it,
# so we replace the response models with versions that default True.
import cashu.core.models as _models  # noqa: E402
from pydantic import BaseModel as _BaseModel  # noqa: E402


class _PatchedKeysResponseKeyset(_BaseModel):
    id: str
    unit: str
    active: Optional[bool] = True
    input_fee_ppk: Optional[int] = None
    keys: dict[int, str]


class _PatchedKeysetsResponseKeyset(_BaseModel):
    id: str
    unit: str
    active: Optional[bool] = True
    input_fee_ppk: Optional[int] = None


class _PatchedKeysResponse(_BaseModel):
    keysets: list[_PatchedKeysResponseKeyset]


class _PatchedKeysetsResponse(_BaseModel):
    keysets: list[_PatchedKeysetsResponseKeyset]


_models.KeysResponseKeyset = _PatchedKeysResponseKeyset
_models.KeysResponse = _PatchedKeysResponse
_models.KeysetsResponseKeyset = _PatchedKeysetsResponseKeyset
_models.KeysetsResponse = _PatchedKeysetsResponse
# ── End model patch ───────────────────────────────────────────────

from cashu.core.helpers import sum_proofs  # noqa: E402
from cashu.core.settings import settings as cashu_settings  # noqa: E402
from cashu.wallet.helpers import (  # noqa: E402
    deserialize_token_from_string,
    init_wallet,
    receive as cashu_receive,
)
from cashu.wallet.wallet import Wallet  # noqa: E402

from config import Config  # noqa: E402

logger = logging.getLogger(__name__)

# Regex to find cashu tokens (V3 or V4) in text
TOKEN_PATTERN = re.compile(r"(cashu[AB][A-Za-z0-9_\-+=]+)")


class CashuHandler:
    """Manages the house Cashu wallet via the cashu Python API."""

    def __init__(self, cashu_dir: str = None, mint_url: str = None):
        self.cashu_dir = cashu_dir or Config.HOUSE_WALLET_DIR
        self.mint_url = mint_url or Config.DEFAULT_MINT_URL
        self._wallet: Wallet | None = None

    async def _get_wallet(self) -> Wallet:
        """Return (and cache) the house wallet instance."""
        if self._wallet is None:
            # Point cashu settings at our dirs
            cashu_settings.cashu_dir = self.cashu_dir
            cashu_settings.mint_url = self.mint_url

            wallet = await Wallet.with_db(
                self.mint_url,
                os.path.join(self.cashu_dir, "wallet"),
                unit="sat",
            )

            # If we have a saved mnemonic in secrets, restore from it;
            # otherwise init_wallet generates a new one.
            secrets = Config.load_secrets()
            saved_mnemonic = secrets.get("wallet_mnemonic")
            if saved_mnemonic:
                await wallet._migrate_database()
                await wallet._init_private_key(saved_mnemonic)
                await wallet.load_proofs(reload=True)
            else:
                await init_wallet(wallet)

            await wallet.load_mint()

            # Persist the mnemonic to secrets.txt so the user can
            # import the wallet into cashu.me or recover funds.
            if hasattr(wallet, "mnemonic") and wallet.mnemonic:
                Config.save_wallet_mnemonic(wallet.mnemonic)
                logger.info("Wallet mnemonic saved to secrets.txt")

            self._wallet = wallet
        return self._wallet

    async def initialize(self):
        """Ensure the house wallet directory exists and is reachable."""
        os.makedirs(self.cashu_dir, exist_ok=True)
        try:
            wallet = await self._get_wallet()
            logger.info(f"House wallet ready at {self.cashu_dir}")
            logger.info(f"Mint: {self.mint_url}")
        except Exception as e:
            logger.warning(f"Wallet init note: {e}")

    async def receive_token(self, token: str) -> int:
        """
        Receive a Cashu token into the house wallet.
        Handles cross-mint tokens by connecting to the token's mint.
        Returns the amount received in sats, or 0 on failure.
        """
        try:
            token_obj = deserialize_token_from_string(token)
            token_mint = token_obj.mint
            amount = token_obj.amount

            # Get the house wallet mnemonic so cross-mint receives
            # derive proofs from the same seed (recoverable).
            house_wallet = await self._get_wallet()
            mnemonic = house_wallet.mnemonic

            # Build a wallet pointed at the token's mint, seeded
            # with the same mnemonic as the house wallet.
            recv_wallet = await Wallet.with_db(
                token_mint,
                os.path.join(self.cashu_dir, "wallet"),
                unit=token_obj.unit or "sat",
            )
            await recv_wallet._migrate_database()
            await recv_wallet._init_private_key(mnemonic)
            await recv_wallet.load_proofs(reload=True)
            await cashu_receive(recv_wallet, token_obj)

            logger.info(f"Received {amount} sat from {token_mint}")
            return amount
        except Exception as e:
            logger.error(f"Token receive failed: {e}")
            return 0

    async def send_token(self, amount: int) -> str:
        """
        Generate a Cashu send token for the given amount.
        Returns the token string, or empty string on failure.
        """
        if amount <= 0:
            return ""
        try:
            wallet = await self._get_wallet()
            await wallet.load_proofs(reload=True)
            await wallet.load_mint()

            send_proofs, _ = await wallet.select_to_send(
                wallet.proofs, amount, set_reserved=True,
            )
            token_str = await wallet.serialize_proofs(send_proofs)
            logger.info(f"Generated payout token for {amount} sat")
            return token_str
        except Exception as e:
            logger.error(f"Token send failed: {e}")
            return ""

    async def get_balance(self) -> int:
        """Return the current house wallet balance in sats."""
        try:
            wallet = await self._get_wallet()
            await wallet.load_proofs(reload=True)
            return sum_proofs(wallet.proofs)
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return 0


def extract_token_from_message(text: str) -> str:
    """Extract a Cashu token (cashuA... or cashuB...) from a chat message."""
    match = TOKEN_PATTERN.search(text)
    return match.group(1) if match else ""

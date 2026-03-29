"""
Cashu ecash wallet handler.
Wraps the Nutshell (cashu) CLI to receive player bets,
pay out winnings, and track the house balance.
"""

import asyncio
import logging
import os
import re

from config import Config

logger = logging.getLogger(__name__)

# Regex to find cashu tokens (V3 or V4) in text
TOKEN_PATTERN = re.compile(r"(cashu[AB][A-Za-z0-9_\-+=]+)")


class CashuHandler:
    """Manages the house Cashu wallet via the cashu CLI."""

    def __init__(self, cashu_dir: str = None, mint_url: str = None):
        self.cashu_dir = cashu_dir or Config.HOUSE_WALLET_DIR
        self.mint_url = mint_url or Config.DEFAULT_MINT_URL

    def _env(self) -> dict:
        """Build environment variables for cashu CLI calls."""
        env = os.environ.copy()
        env["CASHU_DIR"] = self.cashu_dir
        env["MINT_URL"] = self.mint_url
        return env

    async def _run(self, *args) -> tuple:
        """Run a cashu CLI command asynchronously. Returns (stdout, stderr, returncode)."""
        proc = await asyncio.create_subprocess_exec(
            "cashu", "--yes", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode().strip(), stderr.decode().strip(), proc.returncode

    async def initialize(self):
        """Ensure the house wallet directory exists and is reachable."""
        os.makedirs(self.cashu_dir, exist_ok=True)
        stdout, stderr, rc = await self._run("info")
        if rc == 0:
            logger.info(f"House wallet ready at {self.cashu_dir}")
            logger.info(f"Mint: {self.mint_url}")
        else:
            logger.warning(f"Wallet init note: {stderr or stdout}")

    async def receive_token(self, token: str) -> int:
        """
        Receive a Cashu token into the house wallet.
        Returns the amount received in sats, or 0 on failure.
        """
        stdout, stderr, rc = await self._run("receive", token)
        if rc != 0:
            logger.error(f"Token receive failed: {stderr or stdout}")
            return 0

        # Parse amount from output (e.g., "Received 100 sat")
        amount = _parse_amount(stdout)
        if amount > 0:
            logger.info(f"Received {amount} sat into house wallet")
        return amount

    async def send_token(self, amount: int) -> str:
        """
        Generate a Cashu send token for the given amount.
        Returns the token string, or empty string on failure.
        """
        if amount <= 0:
            return ""

        stdout, stderr, rc = await self._run("send", str(amount))
        if rc != 0:
            logger.error(f"Token send failed: {stderr or stdout}")
            return ""

        # Extract the cashu token from output
        token = _extract_token(stdout)
        if token:
            logger.info(f"Generated payout token for {amount} sat")
        return token

    async def get_balance(self) -> int:
        """Return the current house wallet balance in sats."""
        stdout, stderr, rc = await self._run("balance")
        if rc != 0:
            logger.error(f"Balance check failed: {stderr or stdout}")
            return 0
        return _parse_balance(stdout)


def extract_token_from_message(text: str) -> str:
    """Extract a Cashu token (cashuA... or cashuB...) from a chat message."""
    match = TOKEN_PATTERN.search(text)
    return match.group(1) if match else ""


def _parse_amount(output: str) -> int:
    """Parse sats amount from cashu receive output."""
    # Patterns: "Received 100 sat", "Balance: 100 sat"
    for pattern in [r"(\d+)\s*sat", r"(\d+)\s*sats"]:
        m = re.search(pattern, output, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def _parse_balance(output: str) -> int:
    """Parse balance from cashu balance output."""
    m = re.search(r"(\d+)\s*sat", output, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _extract_token(output: str) -> str:
    """Extract a cashu token string from CLI output."""
    match = TOKEN_PATTERN.search(output)
    return match.group(1) if match else ""

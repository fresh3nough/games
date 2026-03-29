"""
Game manager: routes incoming BitChat messages to the appropriate
game handler and manages Cashu bet/payout flows.
"""

import logging

from cashu_handler import CashuHandler, extract_token_from_message
from games import roulette, hangman, blackjack
from games.hangman import HangmanGame
from games.blackjack import BlackjackGame

logger = logging.getLogger(__name__)


class GameManager:
    """Parses chat commands and delegates to game modules."""

    def __init__(self, cashu: CashuHandler):
        self.cashu = cashu

    async def handle_message(self, content: str, sender: str, display_name: str) -> str:
        """
        Process an incoming chat message.
        Returns a response string to publish, or empty string for no response.
        """
        text = content.strip()
        if not text.startswith("!"):
            return ""

        parts = text.split(None, 2)
        cmd = parts[0].lower()

        if cmd == "!roulette":
            return await self._handle_roulette(parts, sender, display_name)
        elif cmd == "!hangman":
            return await self._handle_hangman(parts, sender, display_name)
        elif cmd == "!21":
            return await self._handle_blackjack(parts, sender, display_name)
        elif cmd == "!help":
            return (
                "Casino Games:\n"
                "  !roulette -- European roulette\n"
                "  !hangman  -- Word guessing\n"
                "  !21       -- Blackjack\n"
                "Type any command alone for detailed help."
            )
        elif cmd == "!balance":
            bal = await self.cashu.get_balance()
            return f"House balance: {bal} sat"

        return ""

    # ── Roulette ──────────────────────────────────────────────────

    async def _handle_roulette(self, parts: list, sender: str, name: str) -> str:
        if len(parts) < 2:
            return roulette.HELP_TEXT

        bet_type = parts[1].lower()

        # Validate bet type early
        valid = (
            bet_type in ("red", "black", "odd", "even", "high", "low")
            or (bet_type.isdigit() and 0 <= int(bet_type) <= 36)
        )
        if not valid:
            return f"Invalid bet type '{bet_type}'. " + roulette.HELP_TEXT

        # Extract and receive Cashu token
        token = extract_token_from_message(" ".join(parts[1:]))
        if not token:
            return f"{name}: Include a Cashu token to bet. " + roulette.HELP_TEXT

        bet_amount, bet_mint = await self.cashu.receive_token(token)
        if bet_amount <= 0:
            return ""

        # Spin the wheel
        result = roulette.spin()
        won, multiplier = roulette.evaluate_bet(bet_type, result)
        result_str = roulette.format_result(result)

        if won:
            payout = bet_amount * multiplier
            payout_token, paid = await self.cashu.send_token(payout, bet_mint)
            msg = (
                f"{name} bet {bet_amount} sat on {bet_type}. "
                f"Ball landed on {result_str}. YOU WIN {payout} sat!"
            )
            if payout_token:
                if paid < payout:
                    msg += f" (Partial payout: {paid} of {payout} sat)"
                return msg + f"\nPayout: {payout_token}"
            return msg
        return (
            f"{name} bet {bet_amount} sat on {bet_type}. "
            f"Ball landed on {result_str}. You lose."
        )

    # ── Hangman ───────────────────────────────────────────────────

    async def _handle_hangman(self, parts: list, sender: str, name: str) -> str:
        if len(parts) < 2:
            return hangman.HELP_TEXT

        action = parts[1].lower()

        # Guess a letter
        if action == "guess" and len(parts) >= 3:
            game = hangman.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active hangman game. Start one with !hangman <cashu_token>"
            letter = parts[2].strip()
            msg = game.guess(letter)
            result = f"{name}: {msg}"
            if game.finished:
                result += await self._hangman_settle(sender, name, game)
                del hangman.active_games[sender]
            return result

        # Guess the whole word
        if action == "word" and len(parts) >= 3:
            game = hangman.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active hangman game. Start one with !hangman <cashu_token>"
            word = parts[2].strip()
            msg = game.guess_word(word)
            result = f"{name}: {msg}"
            if game.finished:
                result += await self._hangman_settle(sender, name, game)
                del hangman.active_games[sender]
            return result

        # Show status
        if action == "status":
            game = hangman.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active game. Start with !hangman <cashu_token>"
            return f"{name}: {game.display()} ({hangman.MAX_WRONG - game.wrong} guesses left)"

        # Start a new game with a bet token
        token = extract_token_from_message(" ".join(parts[1:]))
        if not token:
            return hangman.HELP_TEXT

        if sender in hangman.active_games and not hangman.active_games[sender].finished:
            return f"{name}: Finish your current game first! {hangman.active_games[sender].display()}"

        bet_amount, bet_mint = await self.cashu.receive_token(token)
        if bet_amount <= 0:
            return ""

        game = HangmanGame(bet_amount, bet_mint)
        hangman.active_games[sender] = game
        return (
            f"{name}: Hangman started! Bet: {bet_amount} sat | "
            f"Word: {game.display()} ({hangman.MAX_WRONG} guesses) | "
            "Use !hangman guess <letter>"
        )

    async def _hangman_settle(self, sender: str, name: str, game: HangmanGame) -> str:
        """Settle a finished hangman game (pay out or keep tokens)."""
        payout = game.payout_amount()
        if payout > 0:
            token, paid = await self.cashu.send_token(payout, game.bet_mint)
            if token:
                label = f"{paid} of {payout} sat" if paid < payout else f"{payout} sat"
                return f"\nPayout ({label}): {token}"
        return ""

    # ── Blackjack (21) ────────────────────────────────────────────

    async def _handle_blackjack(self, parts: list, sender: str, name: str) -> str:
        if len(parts) < 2:
            return blackjack.HELP_TEXT

        action = parts[1].lower()

        # Hit
        if action == "hit":
            game = blackjack.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active hand. Start with !21 <cashu_token>"
            msg = game.hit()
            result = f"{name}: {msg}"
            if game.finished:
                result += await self._blackjack_settle(sender, name, game)
                del blackjack.active_games[sender]
            return result

        # Stand
        if action == "stand":
            game = blackjack.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active hand. Start with !21 <cashu_token>"
            msg = game.stand()
            result = f"{name}: {msg}"
            if game.finished:
                result += await self._blackjack_settle(sender, name, game)
                del blackjack.active_games[sender]
            return result

        # Status
        if action == "status":
            game = blackjack.active_games.get(sender)
            if not game or game.finished:
                return f"{name}: No active hand. Start with !21 <cashu_token>"
            pv = blackjack.hand_value(game.player_hand)
            return (
                f"{name}: Your hand: {blackjack.format_hand(game.player_hand)} ({pv}) | "
                f"Dealer shows: {game.dealer_hand[0]}"
            )

        # Start a new hand with a bet
        token = extract_token_from_message(" ".join(parts[1:]))
        if not token:
            return blackjack.HELP_TEXT

        if sender in blackjack.active_games and not blackjack.active_games[sender].finished:
            return f"{name}: Finish your current hand first! Type !21 hit or !21 stand"

        bet_amount, bet_mint = await self.cashu.receive_token(token)
        if bet_amount <= 0:
            return ""

        game = BlackjackGame(bet_amount, bet_mint)
        blackjack.active_games[sender] = game
        msg = game.initial_state()
        result = f"{name}: {msg}"

        # If game ended immediately (blackjack or push), settle
        if game.finished:
            result += await self._blackjack_settle(sender, name, game)
            del blackjack.active_games[sender]

        return result

    async def _blackjack_settle(self, sender: str, name: str, game: BlackjackGame) -> str:
        """Settle a finished blackjack game."""
        payout = game.payout_amount()
        if payout > 0:
            token, paid = await self.cashu.send_token(payout, game.bet_mint)
            if token:
                label = f"{paid} of {payout} sat" if paid < payout else f"{payout} sat"
                return f"\nPayout ({label}): {token}"
        return ""

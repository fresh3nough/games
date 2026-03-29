"""
Blackjack (21) card game.
Standard rules: dealer stands on 17, blackjack (ace + 10-card) = 2.5x, win = 2x.
"""

import random

SUITS = ["H", "D", "C", "S"]  # hearts, diamonds, clubs, spades
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

SUIT_SYMBOLS = {"H": "hearts", "D": "diamonds", "C": "clubs", "S": "spades"}


def card_value(card: str) -> list:
    """Return possible values of a card rank. Aces return [1, 11]."""
    rank = card.split("-")[0]
    if rank == "A":
        return [1, 11]
    if rank in ("J", "Q", "K"):
        return [10]
    return [int(rank)]


def hand_value(hand: list) -> int:
    """Calculate the best hand value (highest <= 21, or lowest if busted)."""
    totals = [0]
    for card in hand:
        vals = card_value(card)
        new_totals = []
        for t in totals:
            for v in vals:
                new_totals.append(t + v)
        totals = new_totals

    valid = [t for t in totals if t <= 21]
    return max(valid) if valid else min(totals)


def is_blackjack(hand: list) -> bool:
    """Check if a 2-card hand is a natural blackjack."""
    if len(hand) != 2:
        return False
    return hand_value(hand) == 21


def format_hand(hand: list) -> str:
    """Format a hand for display."""
    return " ".join(hand)


class BlackjackGame:
    """A single blackjack round for one player."""

    def __init__(self, bet_amount: int, bet_mint: str = ""):
        self.bet = bet_amount
        self.bet_mint = bet_mint  # mint URL the bet came from
        self.deck = self._new_deck()
        random.shuffle(self.deck)

        # Deal initial hands
        self.player_hand = [self._draw(), self._draw()]
        self.dealer_hand = [self._draw(), self._draw()]
        self.finished = False
        self.result = ""  # "win", "lose", "push", "blackjack"
        self.stood = False

    def _new_deck(self) -> list:
        """Create a fresh shuffled deck."""
        return [f"{r}-{s}" for s in SUITS for r in RANKS]

    def _draw(self) -> str:
        """Draw a card from the deck."""
        if not self.deck:
            self.deck = self._new_deck()
            random.shuffle(self.deck)
        return self.deck.pop()

    def initial_state(self) -> str:
        """Return the opening game state message."""
        pv = hand_value(self.player_hand)
        # Check for immediate blackjack
        if is_blackjack(self.player_hand):
            if is_blackjack(self.dealer_hand):
                self.finished = True
                self.result = "push"
                return (
                    f"Your hand: {format_hand(self.player_hand)} ({pv}) | "
                    f"Dealer: {format_hand(self.dealer_hand)} ({hand_value(self.dealer_hand)}) | "
                    "Both blackjack -- PUSH (bet returned)"
                )
            self.finished = True
            self.result = "blackjack"
            return (
                f"Your hand: {format_hand(self.player_hand)} ({pv}) | "
                f"Dealer shows: {self.dealer_hand[0]} | "
                "BLACKJACK! You win 2.5x!"
            )
        return (
            f"Your hand: {format_hand(self.player_hand)} ({pv}) | "
            f"Dealer shows: {self.dealer_hand[0]} | "
            "Type !21 hit or !21 stand"
        )

    def hit(self) -> str:
        """Player takes another card."""
        if self.finished:
            return "Game is over. Start a new round with !21 <cashu_token>"

        self.player_hand.append(self._draw())
        pv = hand_value(self.player_hand)

        if pv > 21:
            self.finished = True
            self.result = "lose"
            return (
                f"Your hand: {format_hand(self.player_hand)} ({pv}) -- BUST! You lose."
            )
        if pv == 21:
            return self.stand()

        return (
            f"Your hand: {format_hand(self.player_hand)} ({pv}) | "
            f"Dealer shows: {self.dealer_hand[0]} | "
            "!21 hit or !21 stand"
        )

    def stand(self) -> str:
        """Player stands; dealer plays out."""
        if self.finished:
            return "Game is over. Start a new round with !21 <cashu_token>"

        self.stood = True

        # Dealer draws to 17+
        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self._draw())

        pv = hand_value(self.player_hand)
        dv = hand_value(self.dealer_hand)
        self.finished = True

        dealer_str = f"Dealer: {format_hand(self.dealer_hand)} ({dv})"
        player_str = f"You: {format_hand(self.player_hand)} ({pv})"

        if dv > 21:
            self.result = "win"
            return f"{player_str} | {dealer_str} -- Dealer busts! YOU WIN 2x!"
        if pv > dv:
            self.result = "win"
            return f"{player_str} | {dealer_str} -- YOU WIN 2x!"
        if pv < dv:
            self.result = "lose"
            return f"{player_str} | {dealer_str} -- Dealer wins. You lose."
        self.result = "push"
        return f"{player_str} | {dealer_str} -- PUSH (bet returned)"

    def payout_multiplier(self) -> float:
        """Return the payout multiplier based on result."""
        if self.result == "blackjack":
            return 2.5
        if self.result == "win":
            return 2.0
        if self.result == "push":
            return 1.0
        return 0.0

    def payout_amount(self) -> int:
        """Calculate payout in sats."""
        return int(self.bet * self.payout_multiplier())


# Active games keyed by player pubkey
active_games: dict[str, BlackjackGame] = {}


HELP_TEXT = (
    "Blackjack (21) -- Beat the dealer without going over 21!\n"
    "Usage:\n"
    "  !21 <cashu_token>  -- Start a new hand with a bet\n"
    "  !21 hit            -- Take another card\n"
    "  !21 stand          -- Keep your hand, dealer plays\n"
    "  !21 status         -- Show current hand\n"
    "Payouts: Blackjack = 2.5x | Win = 2x | Push = bet returned"
)

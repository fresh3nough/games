"""
European Roulette (single zero).
Bet types: number (0-36), red, black, odd, even, high (19-36), low (1-18).
Payouts: straight number = 36x, color/parity/range = 2x.
"""

import random

# European roulette: red numbers
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = set(range(1, 37)) - RED_NUMBERS


def spin() -> int:
    """Spin the wheel, return a number 0-36."""
    return random.randint(0, 36)


def color_of(number: int) -> str:
    """Return the color of a roulette number."""
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def evaluate_bet(bet_type: str, result: int) -> tuple:
    """
    Evaluate a bet against the spin result.
    Returns (won: bool, multiplier: int).
    """
    bet = bet_type.lower().strip()

    # Straight number bet
    if bet.isdigit():
        target = int(bet)
        if 0 <= target <= 36 and target == result:
            return True, 36
        return False, 0

    # Color bets
    if bet == "red":
        return (result in RED_NUMBERS, 2)
    if bet == "black":
        return (result in BLACK_NUMBERS, 2)

    # Parity bets (0 loses)
    if bet == "odd":
        return (result > 0 and result % 2 == 1, 2)
    if bet == "even":
        return (result > 0 and result % 2 == 0, 2)

    # Range bets
    if bet == "low":
        return (1 <= result <= 18, 2)
    if bet == "high":
        return (19 <= result <= 36, 2)

    return False, 0


def valid_bet_types() -> list:
    """Return list of valid bet type strings."""
    return ["red", "black", "odd", "even", "high", "low", "0-36 (number)"]


def format_result(result: int) -> str:
    """Format a spin result for display."""
    c = color_of(result)
    return f"{result} {c.upper()}"


HELP_TEXT = (
    "Roulette -- Bet on where the ball lands!\n"
    "Usage: !roulette <bet_type> <cashu_token>\n"
    "Bet types: red, black, odd, even, high (19-36), low (1-18), or a number 0-36\n"
    "Payouts: color/parity/range = 2x | straight number = 36x\n"
    "Example: !roulette red cashuBxxx..."
)

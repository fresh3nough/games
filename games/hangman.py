"""
Hangman word-guessing game.
Players bet to start a round, then guess letters.
Solve the word within the allowed wrong guesses to win.
Payout: 3x the bet on a win; house keeps bet on loss.
"""

import random

WORD_LIST = [
    "bitcoin", "lightning", "satoshi", "wallet", "mining", "blockchain",
    "ecash", "privacy", "freedom", "protocol", "network", "digital",
    "cipher", "token", "exchange", "signature", "entropy", "hashrate",
    "address", "mempool", "utxo", "merkle", "genesis", "halving",
    "consensus", "relay", "channel", "invoice", "payment", "decentralize",
]

MAX_WRONG = 6  # classic hangman body parts
PAYOUT_MULTIPLIER = 3


class HangmanGame:
    """Single hangman round for one player."""

    def __init__(self, bet_amount: int):
        self.word = random.choice(WORD_LIST)
        self.guessed = set()
        self.wrong = 0
        self.bet = bet_amount
        self.finished = False
        self.won = False

    def guess(self, letter: str) -> str:
        """Process a single letter guess. Returns a status message."""
        letter = letter.lower()
        if len(letter) != 1 or not letter.isalpha():
            return "Guess a single letter (a-z)."
        if letter in self.guessed:
            return f"Already guessed '{letter}'. {self.display()}"

        self.guessed.add(letter)

        if letter in self.word:
            if self._is_solved():
                self.finished = True
                self.won = True
                return f"Correct! The word is: {self.word.upper()} -- YOU WIN!"
            return f"'{letter}' is in the word! {self.display()}"
        else:
            self.wrong += 1
            if self.wrong >= MAX_WRONG:
                self.finished = True
                self.won = False
                return f"Wrong! No guesses left. The word was: {self.word.upper()} -- YOU LOSE."
            return f"'{letter}' is not in the word. {self.display()} ({MAX_WRONG - self.wrong} guesses left)"

    def guess_word(self, word: str) -> str:
        """Guess the entire word at once."""
        if word.lower() == self.word:
            self.finished = True
            self.won = True
            return f"Correct! The word is: {self.word.upper()} -- YOU WIN!"
        else:
            self.wrong += 1
            if self.wrong >= MAX_WRONG:
                self.finished = True
                self.won = False
                return f"Wrong word! The answer was: {self.word.upper()} -- YOU LOSE."
            return f"Wrong word! {self.display()} ({MAX_WRONG - self.wrong} guesses left)"

    def display(self) -> str:
        """Show current word state with blanks."""
        revealed = "".join(c if c in self.guessed else "_" for c in self.word)
        return f"[{revealed}]"

    def _is_solved(self) -> bool:
        return all(c in self.guessed for c in self.word)

    def payout_amount(self) -> int:
        """Calculate payout if the player won."""
        return self.bet * PAYOUT_MULTIPLIER if self.won else 0


# Active games keyed by player pubkey
active_games: dict[str, HangmanGame] = {}


HELP_TEXT = (
    "Hangman -- Guess the word before you run out of tries!\n"
    "Usage:\n"
    "  !hangman <cashu_token>     -- Start a new round with a bet\n"
    "  !hangman guess <letter>    -- Guess a letter\n"
    "  !hangman word <word>       -- Guess the whole word\n"
    "  !hangman status            -- Show current game state\n"
    f"Win = {PAYOUT_MULTIPLIER}x your bet | {MAX_WRONG} wrong guesses allowed"
)

# BitChat Casino Bot

A Python bot that connects to [BitChat](https://github.com/permissionlesstech/bitchat) geohash channels over the Nostr protocol and runs gambling games with [Cashu](https://cashu.space/) ecash bets.

## Games

- **!roulette** -- European roulette (0-36). Bet on colors, parity, ranges, or straight numbers.
- **!hangman** -- Guess the hidden word letter by letter before running out of tries.
- **!21** -- Blackjack. Beat the dealer without going over 21.

All games accept Cashu ecash tokens as bets. Winnings are paid back as Cashu tokens in the chat.

## Requirements

- Python 3.10+
- `pip` (Python package manager)
- Cashu CLI (`cashu` command, installed via pip)
- Internet connection (for Nostr relays and Cashu mint)

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/games.git
cd games

# Install dependencies
pip install -r requirements.txt

# Verify cashu CLI is available
cashu --version
```

The `cashu` pip package installs the Nutshell wallet CLI. On first run the bot creates a `house_wallet/` directory for the house ecash wallet and saves the Nostr private key to `secrets.txt`.

### Pre-fund the house wallet (optional)

To pay out winners the house needs a balance. You can fund it by receiving tokens into the house wallet:

```bash
CASHU_DIR=./house_wallet MINT_URL=https://testnut.cashu.space cashu receive <cashu_token>
CASHU_DIR=./house_wallet MINT_URL=https://testnut.cashu.space cashu balance
```

## Running

```bash
python main.py
```

The bot prompts for:

1. **Geohash channel** -- e.g., `gc` (the `#` prefix is optional). This determines which BitChat location channel the bot joins.
2. **Bot nickname** -- display name in chat (default: `CasinoBot`).
3. **Cashu mint URL** -- the ecash mint to use (default: `https://testnut.cashu.space`, a test mint with fake sats).

Once started the bot connects to Nostr relays and listens for game commands on the specified geohash channel.

## Game Commands

### Roulette

```
!roulette                          -- Show help
!roulette <bet_type> <cashu_token> -- Place a bet and spin
```

Bet types: `red`, `black`, `odd`, `even`, `high` (19-36), `low` (1-18), or a number `0`-`36`.

Payouts: color/parity/range = 2x, straight number = 36x.

### Hangman

```
!hangman                       -- Show help
!hangman <cashu_token>         -- Start a new round with a bet
!hangman guess <letter>        -- Guess a letter
!hangman word <full_word>      -- Guess the whole word
!hangman status                -- Show current game state
```

Payout: 3x the bet on a win. 6 wrong guesses allowed.

### Blackjack (21)

```
!21                      -- Show help
!21 <cashu_token>        -- Start a new hand with a bet
!21 hit                  -- Take another card
!21 stand                -- Keep your hand, dealer plays
!21 status               -- Show current hand
```

Payouts: Natural blackjack = 2.5x, win = 2x, push = bet returned.

### Other

```
!help     -- List all games
!balance  -- Show house wallet balance
```

## How Betting Works

1. Get a Cashu ecash token from any Cashu wallet (e.g., [cashu.me](https://cashu.me), Nutshell CLI, eNuts app). The token must be from the same mint the bot is configured to use.
2. Paste the token into your game command, e.g.:
   ```
   !roulette red cashuBo2F0gaJhaUgA2...
   ```
3. The bot redeems the token into its house wallet and plays the game.
4. If you win, the bot posts a payout token in chat that you can receive in your wallet:
   ```
   cashu receive cashuBo2F0gaJhaUgA2...
   ```

## Architecture

```
main.py            -- Entry point and startup prompts
nostr_client.py    -- Nostr WebSocket client (BitChat kind 20000 events)
game_manager.py    -- Routes chat commands to game handlers
cashu_handler.py   -- Async wrapper around the cashu CLI
bip340.py          -- Pure Python BIP-340 Schnorr signatures
config.py          -- Configuration and secrets management
games/
  roulette.py      -- European roulette logic
  hangman.py       -- Hangman word game logic
  blackjack.py     -- Blackjack (21) card game logic
```

### Protocol Details

- **BitChat/Nostr**: The bot publishes and subscribes to ephemeral events (kind 20000) on Nostr relays, tagged with the geohash (`["g", "<geohash>"]`) and bot nickname (`["n", "<nickname>"]`). Events are signed with BIP-340 Schnorr signatures over secp256k1.
- **Cashu**: Bets are Cashu V3 (`cashuA...`) or V4 (`cashuB...`) serialized tokens. The bot uses the Nutshell CLI to receive incoming tokens and generate outgoing payout tokens.

## Files

- `secrets.txt` -- Auto-generated on first run. Stores the Nostr private key and mint URL. **Do not commit this file.**
- `house_wallet/` -- Cashu wallet data directory. **Do not commit.**
- Both are listed in `.gitignore`.

## License

Public domain.

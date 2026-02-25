# Necronomicon Card Game — Discord Bot

A Lovecraftian card game Discord bot with image-composited game boards, campaign mode, multiplayer, and AI opponents.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate placeholder assets
```bash
python generate_placeholders.py
```

### 3. Set up your Discord bot token
```bash
cp .env.example .env
# Edit .env and add your bot token
```

### 4. Run the bot
```bash
python bot.py
```

### 5. In Discord, use:
- `/play` — Open main menu (Campaign, Challenge, Multiplayer, How to Play)
- `/campaign` — Quick-start your next campaign battle
- `/challenge @user` — Challenge a specific player
- `/stats` — View your rank, XP, and progress
- `/cardlist` — View all cards (locked/unlocked by rank)
- `/forfeit` — Forfeit current game

## Replacing Placeholder Assets

All placeholder images are in `assets/`. Replace them with your real art keeping the same filenames:

### Directory Structure
```
assets/
├── board/
│   ├── board_bg.png          (860x540 - main board background)
│   ├── book_closed.png       (80x100 - closed book, center of board)
│   ├── book_open.png         (160x100 - open book during card resolution)
│   ├── pentagram_left.png    (120x120 - left pentagram decoration)
│   └── pentagram_right.png   (120x120 - right pentagram decoration)
├── cards/
│   ├── card_back.png         (120x170 - face-down card)
│   ├── pnakotic_manuscripts.png
│   ├── mi_go_surgery.png
│   ├── discreet_doctor.png
│   ├── ... (one image per card, 120x170 each)
│   └── city_of_rlyeh.png
├── monsters/
│   ├── byakhee.png           (80x100)
│   ├── dimensional_shambler.png
│   ├── shoggoth.png
│   ├── elder_thing.png
│   └── black_goat.png
├── symbols/
│   ├── taint.png             (20x20 - yellow taint symbol)
│   ├── arcane.png            (20x20 - red arcane symbol)
│   └── elder.png             (20x20 - green elder defense symbol)
├── fonts/
│   └── custom.ttf            (your custom font file)
└── ui/
    ├── menu_bg.png           (860x540 - main menu background)
    └── end_screen_bg.png     (860x540 - end screen background)
```

### Image Dimensions Reference
| Asset | Size | Notes |
|-------|------|-------|
| Board background | 860x540 | Main game board |
| Card (face-down back) | 120x170 | Shown in hand area |
| Card (face-up, hand view) | 120x170 | Ephemeral hand display |
| Card (board, top player) | 58x80 | Face-down on board |
| Card (board, bottom player) | 100x86 | Face-down on board |
| Card (play area) | 90x120 | Shown during resolution |
| Monster | 80x100 | On-field display |
| Stat symbol | 20x20 | Taint/Arcane/Elder |
| Book closed | 80x100 | Center of board |
| Book open | 160x100 | During card resolution |
| Avatar | 36x36 | Player avatars |
| Menu background | 860x540 | Main menu |
| End screen | 860x540 | Score screen |

## Project Structure
```
necronomicon/
├── bot.py                 # Discord bot, slash commands, button UI
├── game_engine.py         # Turn management, combat, end-of-turn
├── models.py              # Player, Monster, GameState classes
├── cards.py               # All 31 card definitions and effects
├── ai.py                  # Bot AI (3 difficulty tiers)
├── campaign.py            # Campaign enemy definitions
├── image_compositor.py    # Board/menu/endscreen rendering
├── persistence.py         # JSON player data save/load
├── config.py              # Constants and configuration
├── generate_placeholders.py  # Asset placeholder generator
├── requirements.txt
├── .env.example
└── data/players/          # Player save files (auto-created)
```

## Phases Remaining
- **Phase 2**: XP/Rank progression tuning, campaign balancing, smarter AI tiers
- **Phase 3**: Audio system (voice channel music + SFX)
- **Phase 4**: Challenge mode, How to Play content, final art drop-in

"""Necronomicon Card Game - Configuration Constants"""

# === Player Defaults ===
BASE_LIFE = 40
LIFE_PER_RANK = 5
MAX_LIFE_CAP = 100
STARTING_SANITY = 30
DEFAULT_HAND_SIZE = 5
AGORAPHOBIA_HAND_SIZE = 2

# === Stat Floors ===
MIN_TAINT = 0
MIN_ARCANE = 0
MIN_ELDER_DEFENSE = 0

# === Rank System ===
MAX_RANK = 20
RANK_NAMES = {
    1: "Thug",
    2: "Hoodlum",
    3: "Occultist",
    4: "Acolyte",
    5: "Conjurer",
    6: "Warlock",
    7: "Sorcerer",
    8: "Necromancer",
    9: "Diabolist",
    10: "Shadow Weaver",
    11: "Void Caller",
    12: "Eldritch Sage",
    13: "Abyssal Lord",
    14: "Herald of Madness",
    15: "Outer God's Servant",
    16: "Dreamer in the Deep",
    17: "Keeper of the Gate",
    18: "Star Spawn",
    19: "Great Old One",
    20: "Elder God",
}

# === XP Thresholds (cumulative XP needed to reach each rank) ===
RANK_XP_THRESHOLDS = {
    1: 0,
    2: 50,
    3: 120,
    4: 210,
    5: 320,
    6: 460,
    7: 630,
    8: 840,
    9: 1100,
    10: 1400,
    11: 1750,
    12: 2150,
    13: 2600,
    14: 3100,
    15: 3700,
    16: 4400,
    17: 5200,
    18: 6100,
    19: 7100,
    20: 8200,
}

# === Madness Types ===
MADNESS_TYPES = ["Xenophobia", "Agoraphobia", "Megalomania", "Schizophrenia"]

# === Asset Paths ===
ASSETS_DIR = "assets"
BOARD_BG_PATH = f"{ASSETS_DIR}/board/board_bg.png"
CARD_BACK_PATH = f"{ASSETS_DIR}/cards/card_back.png"
BOOK_CLOSED_PATH = f"{ASSETS_DIR}/board/book_closed.png"
BOOK_OPEN_PATH = f"{ASSETS_DIR}/board/book_open.png"
TAINT_SYMBOL_PATH = f"{ASSETS_DIR}/symbols/taint.png"
ARCANE_SYMBOL_PATH = f"{ASSETS_DIR}/symbols/arcane.png"
ELDER_SYMBOL_PATH = f"{ASSETS_DIR}/symbols/elder.png"
FONT_PATH = f"{ASSETS_DIR}/fonts/custom.ttf"
MENU_BG_PATH = f"{ASSETS_DIR}/ui/menu_bg.png"
END_SCREEN_BG_PATH = f"{ASSETS_DIR}/ui/end_screen_bg.png"
HAND_BG_PATH = f"{ASSETS_DIR}/ui/hand_bg.png"

CARD_IMAGE_PATH_TEMPLATE = f"{ASSETS_DIR}/cards/{{card_id}}.png"
MONSTER_IMAGE_PATH_TEMPLATE = f"{ASSETS_DIR}/monsters/{{monster_id}}.png"

PLAYER_DATA_DIR = "data/players"

# === Card Resolution Display Time (seconds) ===
CARD_DISPLAY_TIME = 3

# =====================================================================
# BOARD LAYOUT — Reference resolution 1536 x 1024
# The compositor auto-detects the actual board_bg.png size and scales
# every coordinate proportionally.  Tweak ONLY these values when
# adjusting element placement; the code never hard-codes pixel coords.
#
# Convention: (x, y, w, h) for boxes, (x, y) for text anchors.
# =====================================================================
BOARD_REF_W = 1536
BOARD_REF_H = 1024

# --- TOP PLAYER (p2 — challenger / bot) ---------------------------

# 5 face-down card slots across the top row
TOP_CARD_SLOTS = [
    (97,  22, 172, 192),   # slot 1
    (291, 22, 172, 192),   # slot 2
    (486, 22, 172, 192),   # slot 3
    (680, 22, 172, 192),   # slot 4
    (875, 22, 172, 192),   # slot 5
]

# Life / Sanity value boxes (text goes centred inside these)
TOP_LIFE_BOX   = (1075, 62,  140, 38)
TOP_SANITY_BOX = (1075, 152, 140, 38)

# Avatar square (top-right, gold-bordered)
TOP_AVATAR_BOX = (1265, 15, 210, 195)

# Display name (below / beside avatar)
TOP_NAME_POS = (1270, 212)

# Rank text — right side of the UPPER stat bar
TOP_RANK_POS = (780, 268)

# --- UPPER STAT BAR (p2 stats) — numbers only, symbols baked in ---
# Each position is the anchor for the NUMBER just to the right of
# its baked-in symbol icon.
TOP_TAINT_NUM_POS  = (415, 268)
TOP_ARCANE_NUM_POS = (540, 268)
TOP_ELDER_NUM_POS  = (660, 268)
TOP_INVULN_POS     = (720, 268)
TOP_MADNESS_POS    = (330, 268)

# --- CENTRE AREA --------------------------------------------------

# Book (closed) sits in the right half of the centre raised box
BOOK_CLOSED_POS  = (830, 420)
BOOK_CLOSED_SIZE = (80, 130)

# Book (open) is centred in the raised box during card resolution
BOOK_OPEN_POS  = (680, 400)
BOOK_OPEN_SIZE = (180, 160)

# Enlarged card shown during resolution phase:
#   LEFT  = for top player (bot / challenger)
#   RIGHT = for bottom player (main player)
CARD_DISPLAY_LEFT_POS   = (70,   350)
CARD_DISPLAY_LEFT_SIZE  = (180,  250)
CARD_DISPLAY_RIGHT_POS  = (1150, 350)
CARD_DISPLAY_RIGHT_SIZE = (180,  250)

# Summoned-monster overlays (drawn on the pentagram / elder-sign)
BOTTOM_MONSTER_POS  = (100,  390)
BOTTOM_MONSTER_SIZE = (120,  160)
TOP_MONSTER_POS     = (1180, 390)
TOP_MONSTER_SIZE    = (120,  160)

# --- LOWER STAT BAR (p1 stats) ------------------------------------

# Rank text — left side of the LOWER stat bar
BOTTOM_RANK_POS = (330, 662)

BOTTOM_TAINT_NUM_POS  = (415, 662)
BOTTOM_ARCANE_NUM_POS = (540, 662)
BOTTOM_ELDER_NUM_POS  = (660, 662)
BOTTOM_INVULN_POS     = (720, 662)
BOTTOM_MADNESS_POS    = (330, 690)

# --- BOTTOM PLAYER (p1 — initiator / main) ------------------------

# Avatar square (bottom-left, gold-bordered)
BOTTOM_AVATAR_BOX = (22, 770, 178, 178)

# Life / Sanity value boxes (to the right of the avatar)
BOTTOM_LIFE_BOX   = (280, 795, 115, 38)
BOTTOM_SANITY_BOX = (280, 905, 115, 38)

# Display name (above the avatar or in a small bar)
BOTTOM_NAME_POS = (30, 952)

# 5 face-down card slots across the bottom row
BOTTOM_CARD_SLOTS = [
    (418,  762, 186, 230),   # slot 1
    (614,  762, 186, 230),   # slot 2
    (810,  762, 186, 230),   # slot 3
    (1006, 762, 186, 230),   # slot 4
    (1202, 762, 186, 230),   # slot 5
]

# === Font Sizes (at reference 1536x1024; auto-scaled with board) ===
FONT_SIZE_STAT_VALUE   = 26
FONT_SIZE_RANK         = 18
FONT_SIZE_NAME         = 16
FONT_SIZE_MONSTER_POWER = 22
FONT_SIZE_MADNESS      = 14
FONT_SIZE_HAND_NUMBER  = 18

# === Audio Paths ===
AUDIO_DIR = f"{ASSETS_DIR}/audio"
AUDIO_MENU_START     = f"{AUDIO_DIR}/menu_start.mp3"
AUDIO_MONSTER_ATTACK = f"{AUDIO_DIR}/monster_attack.mp3"
AUDIO_PHYSICAL_ATTACK = f"{AUDIO_DIR}/physical_attack.mp3"
AUDIO_MAGICAL_ATTACK = f"{AUDIO_DIR}/magical_attack.mp3"
AUDIO_NON_ATTACK     = f"{AUDIO_DIR}/non_attack.mp3"
AUDIO_BATTLE_START   = f"{AUDIO_DIR}/battle_start.mp3"
AUDIO_BATTLE_END     = f"{AUDIO_DIR}/battle_end.mp3"
AUDIO_INSANITY       = f"{AUDIO_DIR}/insanity.mp3"

PHYSICAL_ATTACK_CARDS = {
    "blast_em", "tommy_gun", "raid", "sacrificial_lamb",
}
MAGICAL_ATTACK_CARDS = {
    "dark_ritual", "dark_young_charge", "mind_burn", "from_beyond",
    "hound_of_tindalos", "rise_of_the_deep_ones", "black_goat_of_the_woods",
    "yog_sothoth", "city_of_rlyeh", "betrayed", "mad_experiment",
}
SUMMON_CARDS = {
    "byakhee", "dimensional_shambler", "shoggoth", "elder_thing",
    "black_goat_of_the_woods",
}
NON_ATTACK_CARDS = {
    "pnakotic_manuscripts", "mi_go_surgery", "discreet_doctor",
    "essence_of_the_soul", "elder_sign", "arkham_asylum",
    "powder_of_ibn_ghazi", "dispel", "unaussprechlichen_kulten",
    "blackmail", "curse_of_cthulhu", "king_in_yellow",
    "blessing_of_hastur", "miskatonic_university", "doppelganger",
    "dawn_of_a_new_day", "professor_armitage", "elder_thing",
}

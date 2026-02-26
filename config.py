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
PENTAGRAM_LEFT_PATH = f"{ASSETS_DIR}/board/pentagram_left.png"
PENTAGRAM_RIGHT_PATH = f"{ASSETS_DIR}/board/pentagram_right.png"

# Card image path template - card images named by card_id
CARD_IMAGE_PATH_TEMPLATE = f"{ASSETS_DIR}/cards/{{card_id}}.png"
MONSTER_IMAGE_PATH_TEMPLATE = f"{ASSETS_DIR}/monsters/{{monster_id}}.png"

# === Board Layout Constants (pixel positions, will be calibrated to actual assets) ===
BOARD_WIDTH = 860
BOARD_HEIGHT = 540

# Player data directory
PLAYER_DATA_DIR = "data/players"

# === Card Resolution Display Time (seconds) ===
CARD_DISPLAY_TIME = 3

# === Audio Paths ===
AUDIO_DIR = f"{ASSETS_DIR}/audio"
AUDIO_MENU_START = f"{AUDIO_DIR}/menu_start.mp3"
AUDIO_MONSTER_ATTACK = f"{AUDIO_DIR}/monster_attack.mp3"
AUDIO_PHYSICAL_ATTACK = f"{AUDIO_DIR}/physical_attack.mp3"
AUDIO_MAGICAL_ATTACK = f"{AUDIO_DIR}/magical_attack.mp3"
AUDIO_NON_ATTACK = f"{AUDIO_DIR}/non_attack.mp3"
AUDIO_BATTLE_START = f"{AUDIO_DIR}/battle_start.mp3"
AUDIO_BATTLE_END = f"{AUDIO_DIR}/battle_end.mp3"
AUDIO_INSANITY = f"{AUDIO_DIR}/insanity.mp3"

# Cards classified as "physical" attacks (no arcane involvement)
PHYSICAL_ATTACK_CARDS = {
    "blast_em", "tommy_gun", "raid", "sacrificial_lamb",
}

# Cards classified as "magical" attacks (involve arcane)
MAGICAL_ATTACK_CARDS = {
    "dark_ritual", "dark_young_charge", "mind_burn", "from_beyond",
    "hound_of_tindalos", "rise_of_the_deep_ones", "black_goat_of_the_woods",
    "yog_sothoth", "city_of_rlyeh", "betrayed", "mad_experiment",
}

# Cards that summon monsters
SUMMON_CARDS = {
    "byakhee", "dimensional_shambler", "shoggoth", "elder_thing",
    "black_goat_of_the_woods",
}

# Non-attack cards (everything else)
NON_ATTACK_CARDS = {
    "pnakotic_manuscripts", "mi_go_surgery", "discreet_doctor",
    "essence_of_the_soul", "elder_sign", "arkham_asylum",
    "powder_of_ibn_ghazi", "dispel", "unaussprechlichen_kulten",
    "blackmail", "curse_of_cthulhu", "king_in_yellow",
    "blessing_of_hastur", "miskatonic_university", "doppelganger",
    "dawn_of_a_new_day", "professor_armitage", "elder_thing",
}

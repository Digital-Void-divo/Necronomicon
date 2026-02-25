"""Generate placeholder assets for testing.

Run this once to create all required placeholder images.
Replace these with real assets when ready.
"""

import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = "assets"

# === Directory Structure ===
dirs = [
    f"{ASSETS_DIR}/board",
    f"{ASSETS_DIR}/cards",
    f"{ASSETS_DIR}/monsters",
    f"{ASSETS_DIR}/symbols",
    f"{ASSETS_DIR}/fonts",
    f"{ASSETS_DIR}/ui",
]

for d in dirs:
    os.makedirs(d, exist_ok=True)


def get_font(size=12):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()


def make_rect(w, h, color, text="", text_color=(200, 200, 200), border_color=None):
    img = Image.new("RGBA", (w, h), color)
    draw = ImageDraw.Draw(img)
    if border_color:
        draw.rectangle([(0, 0), (w-1, h-1)], outline=border_color, width=2)
    if text:
        font = get_font(max(8, min(14, w // max(len(text), 1))))
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w-tw)//2, (h-th)//2), text, fill=text_color, font=font)
    return img


print("Generating placeholder assets...")

# === Board Background ===
board = Image.new("RGBA", (860, 540), (60, 30, 20, 255))
draw = ImageDraw.Draw(board)
# Add some texture-like noise
import random
for _ in range(5000):
    x, y = random.randint(0, 859), random.randint(0, 539)
    r = random.randint(40, 80)
    draw.point((x, y), fill=(r, r//2, r//3, 255))
# Draw play areas
draw.rectangle([(250, 130), (360, 270)], outline=(100, 60, 40, 150), width=2)  # Top card play
draw.rectangle([(250, 290), (360, 430)], outline=(100, 60, 40, 150), width=2)  # Bottom card play
# Draw hand areas
draw.rectangle([(145, 15), (540, 100)], outline=(80, 50, 30, 100), width=1)  # Top hand
draw.rectangle([(145, 425), (640, 520)], outline=(80, 50, 30, 100), width=1)  # Bottom hand
board.save(f"{ASSETS_DIR}/board/board_bg.png")
print("  ✓ board_bg.png")

# === Card Back ===
card_back = make_rect(120, 170, (70, 40, 25, 230), "🂠", border_color=(100, 70, 40))
card_back.save(f"{ASSETS_DIR}/cards/card_back.png")
print("  ✓ card_back.png")

# === Book Images ===
book_closed = make_rect(80, 100, (100, 80, 40, 220), "📕", border_color=(120, 90, 50))
book_closed.save(f"{ASSETS_DIR}/board/book_closed.png")
book_open = make_rect(160, 100, (120, 100, 50, 220), "📖 OPEN", border_color=(120, 90, 50))
book_open.save(f"{ASSETS_DIR}/board/book_open.png")
print("  ✓ book_closed.png, book_open.png")

# === Symbols ===
symbols = {
    "taint": (200, 180, 0, 255),
    "arcane": (200, 50, 50, 255),
    "elder": (0, 180, 0, 255),
}
for name, color in symbols.items():
    sym = Image.new("RGBA", (20, 20), color)
    draw = ImageDraw.Draw(sym)
    draw.ellipse([(2, 2), (17, 17)], fill=color, outline=(255, 255, 255, 100))
    sym.save(f"{ASSETS_DIR}/symbols/{name}.png")
print("  ✓ Symbol images")

# === Pentagram placeholders ===
for side in ["left", "right"]:
    pent = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pent)
    draw.ellipse([(5, 5), (115, 115)], outline=(150, 50, 30, 150), width=2)
    pent.save(f"{ASSETS_DIR}/board/pentagram_{side}.png")
print("  ✓ Pentagram images")

# === Card Images ===
card_ids = [
    "pnakotic_manuscripts", "mi_go_surgery", "discreet_doctor", "essence_of_the_soul",
    "blast_em", "dark_ritual", "byakhee", "sacrificial_lamb", "dark_young_charge",
    "dimensional_shambler", "tommy_gun", "curse_of_cthulhu", "king_in_yellow",
    "blessing_of_hastur", "shoggoth", "from_beyond", "elder_sign", "arkham_asylum",
    "powder_of_ibn_ghazi", "dispel", "unaussprechlichen_kulten", "blackmail",
    "mind_burn", "raid", "betrayed", "elder_thing", "miskatonic_university",
    "doppelganger", "hound_of_tindalos", "rise_of_the_deep_ones", "mad_experiment",
    "dawn_of_a_new_day", "black_goat_of_the_woods", "professor_armitage",
    "yog_sothoth", "city_of_rlyeh",
]

card_colors = {
    # Damage cards - red tint
    "blast_em": (120, 30, 30), "dark_ritual": (100, 20, 40), "dark_young_charge": (130, 20, 20),
    "tommy_gun": (110, 40, 30), "mind_burn": (100, 30, 50), "raid": (120, 40, 20),
    "from_beyond": (80, 20, 60), "hound_of_tindalos": (90, 30, 50),
    "rise_of_the_deep_ones": (40, 40, 80), "black_goat_of_the_woods": (50, 30, 20),
    "yog_sothoth": (60, 20, 80), "city_of_rlyeh": (30, 50, 60), "betrayed": (80, 40, 30),
    # Healing - green tint
    "discreet_doctor": (30, 80, 40), "essence_of_the_soul": (40, 90, 50),
    "mi_go_surgery": (30, 70, 60), "sacrificial_lamb": (50, 70, 40),
    "arkham_asylum": (40, 60, 80),
    # Monster summons - purple tint
    "byakhee": (60, 30, 80), "dimensional_shambler": (70, 20, 90),
    "shoggoth": (50, 20, 70), "elder_thing": (30, 60, 50),
    # Utility - blue/brown tint
    "elder_sign": (30, 50, 90), "dispel": (50, 50, 80), "blackmail": (60, 50, 40),
    "powder_of_ibn_ghazi": (70, 60, 30), "doppelganger": (50, 50, 60),
    "dawn_of_a_new_day": (80, 70, 40), "professor_armitage": (50, 60, 50),
    "miskatonic_university": (40, 50, 60), "mad_experiment": (70, 40, 70),
    # Taint/Sanity - yellow/dark tint
    "curse_of_cthulhu": (80, 70, 20), "king_in_yellow": (90, 80, 10),
    "blessing_of_hastur": (70, 60, 20),
    # Arcane - red/orange tint
    "pnakotic_manuscripts": (80, 50, 30), "unaussprechlichen_kulten": (90, 40, 30),
}

for card_id in card_ids:
    color = card_colors.get(card_id, (60, 40, 50))
    # Readable name
    name = card_id.replace("_", " ").title()
    if len(name) > 18:
        name = name[:16] + ".."
    card = make_rect(120, 170, (*color, 230), name, border_color=(140, 110, 70))
    card.save(f"{ASSETS_DIR}/cards/{card_id}.png")

print(f"  ✓ {len(card_ids)} card images")

# === Monster Images ===
monsters = {
    "byakhee": ((80, 40, 120), "Byakhee"),
    "dimensional_shambler": ((90, 50, 100), "Shambler"),
    "shoggoth": ((60, 80, 60), "Shoggoth"),
    "elder_thing": ((40, 80, 80), "Elder\nThing"),
    "black_goat": ((50, 30, 20), "Black\nGoat"),
}

for monster_id, (color, label) in monsters.items():
    m = make_rect(80, 100, (*color, 200), label, border_color=(150, 100, 80))
    m.save(f"{ASSETS_DIR}/monsters/{monster_id}.png")

print(f"  ✓ {len(monsters)} monster images")

# === Menu Background ===
menu = Image.new("RGBA", (860, 540), (40, 20, 15, 255))
draw = ImageDraw.Draw(menu)
font_title = get_font(36)
font_opt = get_font(22)
draw.text((220, 30), "NECRONOMICON", fill=(180, 150, 100), font=font_title)
options = ["📖  Campaign", "⚔️  Challenge Mode", "👥  Multiplayer", "❓  How to Play"]
for i, opt in enumerate(options):
    draw.text((320, 140 + i * 80), opt, fill=(200, 180, 130), font=font_opt)
menu.save(f"{ASSETS_DIR}/ui/menu_bg.png")
print("  ✓ menu_bg.png")

# === End Screen Background ===
end = Image.new("RGBA", (860, 540), (40, 25, 15, 255))
draw = ImageDraw.Draw(end)
# Decorative border
draw.rectangle([(40, 60), (820, 480)], outline=(100, 80, 50), width=2)
end.save(f"{ASSETS_DIR}/ui/end_screen_bg.png")
print("  ✓ end_screen_bg.png")

print("\n✅ All placeholder assets generated!")
print(f"Total files: {len(card_ids) + len(monsters) + 10}")
print("\nReplace files in assets/ with your real art when ready.")
print("Keep the same filenames and directory structure.")

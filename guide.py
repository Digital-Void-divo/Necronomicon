"""Necronomicon Card Game - Guide System

Provides a multi-page, image-illustrated Discord embed guide navigable with
Previous / Next buttons.  Works from both the in-game Guide button and the
/guide slash command.

Pages
─────
 0  Welcome & Objective
 1  Your Stats Explained
 2  Sanity & Madness
 3  Monsters & Combat
 4  Taking Your Turn
 5  Cards: Damage
 6  Cards: Healing
 7  Cards: Summoning
 8  Cards: Arcane & Defense
 9  Cards: Disruption & Utility
10  Cards: Rare & High-Rank
11  Game Modes
12  Ranks & Progression
"""

import os
import io
import discord
from typing import Optional

from config import ASSETS_DIR, RANK_NAMES, RANK_XP_THRESHOLDS


# ── Page definitions ──────────────────────────────────────────────────────────
# Each page is a dict:
#   title   : embed title string
#   colour  : discord.Colour
#   sections: list of (field_name, field_value, inline) tuples
#   image   : path to an asset image shown at the bottom of the embed (or None)
#   footer  : optional footer override (default shows page counter)

DARK_RED    = discord.Colour.from_rgb(160, 30, 30)
DARK_PURPLE = discord.Colour.from_rgb(100, 20, 120)
BLOOD_RED   = discord.Colour.from_rgb(180, 10, 10)
DEEP_TEAL   = discord.Colour.from_rgb(20, 100, 100)
GOLD        = discord.Colour.from_rgb(210, 170, 30)
DARK_BLUE   = discord.Colour.from_rgb(20, 40, 120)
GREY        = discord.Colour.from_rgb(80, 80, 80)
GREEN       = discord.Colour.from_rgb(30, 130, 50)


def _c(path: str) -> str:
    """Full path to a card image."""
    return os.path.join(ASSETS_DIR, "cards", path)

def _m(path: str) -> str:
    """Full path to a monster image."""
    return os.path.join(ASSETS_DIR, "monsters", path)

def _b(path: str) -> str:
    """Full path to a board/UI image."""
    return os.path.join(ASSETS_DIR, "board", path)

def _u(path: str) -> str:
    """Full path to a UI image."""
    return os.path.join(ASSETS_DIR, "ui", path)


PAGES = [
    # ── 0. Welcome & Objective ───────────────────────────────────────────────
    {
        "title": "📖 Welcome to the Necronomicon",
        "colour": DARK_RED,
        "image": _b("board_bg.png"),
        "sections": [
            ("Objective", (
                "Reduce your opponent's **Life** to 0 before they do the same to you.\n\n"
                "Each player starts with **Life** based on their rank, **30 Sanity**, "
                "a shuffled deck of cards, and draws a hand of 5."
            ), False),
            ("Win Conditions", (
                "🏆 Reduce opponent's **Life** to 0\n"
                "💀 Opponent's **Life** reaches 0 from Taint, Monsters, or cards\n"
                "⏳ In Challenge Mode — survive a **turn limit** to win\n"
                "🤝 Both players die simultaneously = **Draw**"
            ), False),
            ("Quick Flow", (
                "**Your turn:** Play a card **or** Discard a card for Sanity\n"
                "**End of turn:** Your monster attacks, Taint deals damage, Madness triggers\n"
                "**Then:** Your opponent takes their turn"
            ), False),
        ],
    },

    # ── 1. Stats ─────────────────────────────────────────────────────────────
    {
        "title": "📊 Your Stats Explained",
        "colour": DARK_PURPLE,
        "image": None,
        "sections": [
            ("❤️  Life", (
                "Your hit points. Starts at **40 + (5 × rank)**. "
                "When it hits 0, you lose. Life can be healed above your starting value."
            ), False),
            ("🧠  Sanity", (
                "Starts at **30**. Playing cards costs Sanity. "
                "If Sanity hits **0 or below**, you gain a **Madness**. "
                "Sanity can go negative — you just become progressively unhinged. "
                "Discard a card on your turn to **regain Sanity equal to its cost**."
            ), False),
            ("🔮  Arcane Power", (
                "A multiplier for many powerful spells. Cards like Dark Ritual deal "
                "**10 + Arcane** damage. Build it up with Pnakotic Manuscripts, "
                "Unaussprechlichen Kulten, etc. Some cards reset it to 0 — watch out."
            ), False),
            ("🛡️  Elder Defense", (
                "Reduces incoming damage from most spells and monsters. "
                "Damage dealt = **card damage − Elder Defense** (minimum 0). "
                "Physical cards (Blast'em, Tommy Gun, Raid) **ignore** Elder Defense entirely."
            ), False),
            ("🩸  Taint", (
                "A persistent damage tick. At the **end of every turn** you take "
                "**Taint damage equal to your Taint value**. Taint is hard to remove — "
                "manage it before it stacks too high."
            ), False),
            ("🛡️  Invulnerability", (
                "Absorbs the **next single hit** dealt to you. "
                "Consumed on use. Physical cards and Dispel bypass or remove it."
            ), False),
        ],
    },

    # ── 2. Sanity & Madness ───────────────────────────────────────────────────
    {
        "title": "🤯 Sanity & Madness",
        "colour": BLOOD_RED,
        "image": _c("arkham_asylum.png"),
        "sections": [
            ("Losing Sanity", (
                "Playing a card reduces your Sanity by its **Sanity Cost**. "
                "Sanity can also be drained by opponent cards like **King in Yellow** and "
                "**From Beyond**. When Sanity drops to **0 or below**, you gain a Madness."
            ), False),
            ("Gaining Sanity Back", (
                "• **Discard** a card on your turn → gain Sanity equal to its cost\n"
                "• **Arkham Asylum** → +15 Sanity\n"
                "• **Miskatonic University** → +5 Sanity, clears Taint\n"
                "• **Dawn of a New Day** → +5 Sanity (minimum Sanity of 5)\n\n"
                "If Sanity returns **above 0**, your Madness is cured."
            ), False),
            ("🧩 Xenophobia", (
                "Any monster you summon is **immediately destroyed**. "
                "You cannot keep a creature on the field while insane this way."
            ), True),
            ("🚪 Agoraphobia", (
                "Your hand size is reduced to **2 cards**. Excess cards are randomly discarded "
                "each turn. You draw back up to 2 at end of turn."
            ), True),
            ("👑 Megalomania", (
                "At the **end of each of your turns**, gain **+2 Arcane** but also "
                "gain **+4 Taint**. Power comes at a price."
            ), True),
            ("🌀 Schizophrenia", (
                "At the **end of each of your turns**, your **Arcane and Elder Defense "
                "are both reset to 0**. Nothing you build stays built."
            ), True),
        ],
    },

    # ── 3. Monsters & Combat ─────────────────────────────────────────────────
    {
        "title": "🐙 Monsters & Combat",
        "colour": DARK_PURPLE,
        "image": _m("shoggoth.png"),
        "sections": [
            ("How Monsters Work", (
                "Summoning a monster places it on your side of the board. "
                "At the **end of your turn**, your monster attacks the opponent. "
                "You can only have **one monster** at a time — summoning a new one replaces the old."
            ), False),
            ("Monster Combat", (
                "If your opponent **also has a monster**, the two creatures clash:\n"
                "• Higher Power wins — the loser's monster is **destroyed**\n"
                "• Equal Power — **both monsters** are destroyed\n\n"
                "If the opponent has **no monster**, your creature deals its **Power** "
                "as direct damage (reduced by Elder Defense, unless Piercing)."
            ), False),
            ("🦅 Byakhee — Power 3", (
                "Can only be **blocked by another Byakhee**. All other monsters let it "
                "deal direct damage. Fast and persistent."
            ), True),
            ("👻 Dimensional Shambler — Power 4", (
                "**Piercing** — ignores Elder Defense when dealing direct damage."
            ), True),
            ("🟢 Shoggoth — Power 6", (
                "**Destroys the opponent's monster on summon**, then attacks normally. "
                "Excellent board clear."
            ), True),
            ("🔵 Elder Thing — Power 2", (
                "Weakest fighter, but summoning it also grants **+3 Elder Defense** "
                "and clears your Taint. A defensive pick."
            ), True),
            ("🐐 Black Goat of the Woods — Power 10", (
                "The strongest creature. Also deals **8 + Arcane** damage on arrival. "
                "Requires Rank 15."
            ), True),
        ],
    },

    # ── 4. Taking Your Turn ───────────────────────────────────────────────────
    {
        "title": "⚡ Taking Your Turn",
        "colour": DEEP_TEAL,
        "image": _c("card_back.png"),
        "sections": [
            ("On Your Turn", (
                "You take **one action** (unless a Challenge grants more):\n\n"
                "▶️ **Play a card** — pay its Sanity cost and trigger its effect\n"
                "📖 **Discard a card** — regain Sanity equal to its cost, draw a new card\n\n"
                "After your action resolves, end-of-turn effects fire."
            ), False),
            ("End of Turn (in order)", (
                "1. 🐙 Your monster attacks\n"
                "2. 🩸 You take Taint damage equal to your Taint value\n"
                "3. 🤯 Madness end-of-turn effects trigger (Megalomania, Schizophrenia)\n"
                "4. 🚪 Agoraphobia: draw up to hand size 2\n"
                "5. ☠️ Game-over check — if anyone is at 0 Life, the game ends"
            ), False),
            ("Can't Afford a Card?", (
                "You can always **discard** instead of play — Sanity cost cards are "
                "never unplayable, only unaffordable. Even 0-cost cards can be discarded "
                "(though they give no Sanity back)."
            ), False),
            ("Multi-Action Turns (Challenge Mode)", (
                "Some Challenge scenarios grant **2 or 3 actions per turn**. "
                "Each play/discard uses one action. End-of-turn effects only fire "
                "after all actions are spent."
            ), False),
        ],
    },

    # ── 5. Cards: Damage ─────────────────────────────────────────────────────
    {
        "title": "💥 Cards: Damage",
        "colour": BLOOD_RED,
        "image": _c("dark_young_charge.png"),
        "sections": [
            ("Physical — Ignore Elder Defense & Invulnerability", (
                "These bypass all defences. Ideal against heavily fortified opponents.\n\n"
                "🔫 **Blast'em** (Cost 0) — 3 damage\n"
                "🔫 **Tommy Gun** (Cost 0) — 5 damage\n"
                "🔫 **Raid** (Cost 0) — 7 damage"
            ), False),
            ("Arcane — Scaled by Your Arcane Power", (
                "Damage = base + your current Arcane. Reduced by Elder Defense.\n\n"
                "🔮 **Mind Burn** (Cost 1) — 7 + Arcane\n"
                "🔮 **Dark Ritual** (Cost 2) — 10 + Arcane, also heals you 3 Life\n"
                "🔮 **Dark Young Charge** (Cost 4) — 14 + Arcane\n"
                "🔮 **From Beyond** (Cost 3) — 8 + Arcane + drains 6 Sanity\n"
                "🔮 **Hound of Tindalos** (Cost 4, Rank 7) — 12 + Arcane, **ignores Elder Defense**\n"
                "🔮 **Rise of the Deep Ones** (Cost 4, Rank 9) — 10 + Arcane, +2 Arcane & Elder\n"
                "🔮 **Black Goat of the Woods** (Cost 8, Rank 15) — Summon + 8 + Arcane on arrival"
            ), False),
            ("Conditional Damage", (
                "⚡ **Betrayed** (Cost 0) — opponent's monster power + your Arcane. "
                "No effect if they have no monster.\n\n"
                "☠️ **Yog-Sothoth** (Cost 0, Rank 19) — damage equal to opponent's Sanity, "
                "then both players' Sanity → 0.\n\n"
                "🌊 **City of R'lyeh** (Cost 6, Rank 20) — sets opponent Sanity to 0 + Madness. "
                "If they're already insane: **20 + Arcane** damage."
            ), False),
        ],
    },

    # ── 6. Cards: Healing ────────────────────────────────────────────────────
    {
        "title": "💚 Cards: Healing",
        "colour": GREEN,
        "image": _c("essence_of_the_soul.png"),
        "sections": [
            ("Life Recovery", (
                "Life can be healed **above your starting value** — there is no cap.\n\n"
                "💊 **Discreet Doctor** (Cost 0) — +4 Life\n"
                "💉 **Mi-Go Surgery** (Cost 1) — +7 Life, **−2 Arcane** (trade-off!)\n"
                "✨ **Essence of the Soul** (Cost 3) — +9 Life\n"
                "🐑 **Sacrificial Lamb** (Cost 2) — +5 Life, also banishes opponent's monster\n"
                "🔮 **Dark Ritual** (Cost 2) — +3 Life plus 10 + Arcane damage"
            ), False),
            ("Sanity Recovery", (
                "🏥 **Arkham Asylum** (Cost 0) — +15 Sanity\n"
                "🎓 **Miskatonic University** (Cost 0, Rank 3) — +5 Sanity, clear Taint, +2 Arcane\n"
                "🌅 **Dawn of a New Day** (Cost 0, Rank 13) — board wipe + Sanity min 5\n\n"
                "Discarding any card also returns Sanity equal to its cost."
            ), False),
            ("Taint Removal", (
                "🙏 **Blessing of Hastur** (Cost 3) — your Taint → 0, opponent gains 2 Taint\n"
                "🔵 **Elder Thing** (Cost 1) — clears your Taint, summons creature, +3 Elder\n"
                "🎓 **Miskatonic University** (Cost 0, Rank 3) — clears Taint, heals Sanity\n"
                "🌟 **Professor Armitage** (Cost 0, Rank 17) — clears Taint, +2 Arcane, +4 Elder\n"
                "🌅 **Dawn of a New Day** (Cost 0, Rank 13) — clears Taint for **both** players"
            ), False),
        ],
    },

    # ── 7. Cards: Summoning ───────────────────────────────────────────────────
    {
        "title": "🐙 Cards: Summoning",
        "colour": DARK_PURPLE,
        "image": _m("byakhee.png"),
        "sections": [
            ("Summon Cards", (
                "Creatures persist on the board and attack at end of each of your turns. "
                "Summoning a new creature **replaces** your existing one."
            ), False),
            ("🦅 Byakhee (Cost 2)", (
                "Power 3. Only blocked by another Byakhee — passes through everything else for "
                "direct damage. Great for bypassing enemy monsters."
            ), True),
            ("👻 Dimensional Shambler (Cost 3)", (
                "Power 4. **Piercing** — deals direct damage ignoring Elder Defense."
            ), True),
            ("🟢 Shoggoth (Cost 4)", (
                "Power 6. **Destroys opponent's creature on summon** before entering. "
                "The top-tier non-rare summon."
            ), True),
            ("🔵 Elder Thing (Cost 1)", (
                "Power 2. Also grants **+3 Elder Defense** and clears your **Taint**. "
                "More of a defensive utility card than an attacker."
            ), True),
            ("🐐 Black Goat of the Woods (Cost 8, Rank 15)", (
                "Power 10. Also deals **8 + Arcane** damage on arrival. "
                "The most powerful persistent threat in the game."
            ), True),
            ("Counter-Summon Cards", (
                "🐑 **Sacrificial Lamb** — banishes opponent's creature and heals you\n"
                "💀 **Powder of Ibn-Ghazi** — banishes opponent's creature AND resets their Arcane\n"
                "🌀 **Betrayed** — turns their monster's power against them (deals power + Arcane)"
            ), False),
        ],
    },

    # ── 8. Cards: Arcane & Defense ────────────────────────────────────────────
    {
        "title": "🛡️ Cards: Arcane & Defense",
        "colour": DARK_BLUE,
        "image": _c("elder_sign.png"),
        "sections": [
            ("Building Arcane", (
                "Arcane is your damage multiplier. Stack it early for lethal turns later.\n\n"
                "📜 **Pnakotic Manuscripts** (Cost 2) — +3 Arcane\n"
                "📕 **Unaussprechlichen Kulten** (Cost 3) — +5 Arcane\n"
                "🎓 **Miskatonic University** (Cost 0, Rank 3) — +2 Arcane, +5 Sanity, clear Taint\n"
                "🌊 **Rise of the Deep Ones** (Cost 4, Rank 9) — deals damage AND gains +2 Arcane\n"
                "🌟 **Professor Armitage** (Cost 0, Rank 17) — +2 Arcane, +4 Elder, clear Taint"
            ), False),
            ("Building Elder Defense", (
                "🔯 **Elder Sign** (Cost 0) — **Invulnerable** + 2 Elder Defense\n"
                "🔵 **Elder Thing** (Cost 1) — summon + 3 Elder Defense + clear Taint\n"
                "🌊 **Rise of the Deep Ones** (Cost 4, Rank 9) — +2 Elder Defense\n"
                "🌟 **Professor Armitage** (Cost 0, Rank 17) — +4 Elder Defense"
            ), False),
            ("🪞 Doppelganger (Cost 1, Rank 5)", (
                "Sets **your** Arcane, Elder Defense, and Taint equal to your **opponent's** values. "
                "Use when they're ahead in stats — punishing to ignore."
            ), False),
            ("Counter-Defense Cards", (
                "⚡ **Dispel** (Cost 1) — removes opponent's Elder Defense AND Invulnerability\n"
                "💀 **Powder of Ibn-Ghazi** (Cost 1) — banishes their monster AND resets their Arcane\n"
                "🌅 **Dawn of a New Day** (Cost 0, Rank 13) — resets **everyone's** stats to 0"
            ), False),
        ],
    },

    # ── 9. Cards: Disruption & Utility ───────────────────────────────────────
    {
        "title": "🎭 Cards: Disruption & Utility",
        "colour": GOLD,
        "image": _c("king_in_yellow.png"),
        "sections": [
            ("Taint Application", (
                "Stack Taint on your opponent for constant end-of-turn life drain.\n\n"
                "☠️ **Curse of Cthulhu** (Cost 1) — opponent +1 Taint\n"
                "👑 **King in Yellow** (Cost 2) — opponent −5 Sanity AND +2 Taint\n"
                "🙏 **Blessing of Hastur** (Cost 3) — your Taint → 0, opponent +2 Taint"
            ), False),
            ("Sanity Pressure", (
                "Drive your opponent insane to unlock Madness penalties.\n\n"
                "👑 **King in Yellow** (Cost 2) — −5 Sanity + 2 Taint\n"
                "🌀 **From Beyond** (Cost 3) — −6 Sanity + 8 + Arcane damage\n"
                "🌊 **City of R'lyeh** (Cost 6, Rank 20) — Sanity → 0; if already insane: "
                "20 + Arcane damage\n"
                "⚡ **Yog-Sothoth** (Cost 0, Rank 19) — damage = their Sanity; both Sanities → 0"
            ), False),
            ("Hand Disruption", (
                "💬 **Blackmail** (Cost 0) — opponent chooses a card to discard and draws fresh. "
                "Great for breaking their hand plan."
            ), False),
            ("Dual-Purpose Utility", (
                "🌅 **Dawn of a New Day** (Cost 0, Rank 13) — resets ALL stats and creatures for "
                "both players, guarantees Sanity ≥ 5. Nuclear reset button.\n\n"
                "🎲 **Mad Experiment** (Cost 3, Rank 11) — randomly does one of:\n"
                "  1. Summon Shoggoth (destroys theirs)\n"
                "  2. Deal 15 + Arcane damage\n"
                "  3. Gain +5 Arcane and +5 Elder Defense\n"
                "  4. Your own Sanity → 0 (risk!)"
            ), False),
        ],
    },

    # ── 10. Cards: Rare & High-Rank ───────────────────────────────────────────
    {
        "title": "⭐ Cards: Rare & High-Rank Unlocks",
        "colour": GOLD,
        "image": _c("city_of_rlyeh.png"),
        "sections": [
            ("Rank 3", "🎓 **Miskatonic University** (Cost 0) — Taint → 0, +5 Sanity, +2 Arcane. No downside. Strong at any stage.", False),
            ("Rank 5", "🪞 **Doppelganger** (Cost 1) — Mirror opponent's Arcane, Elder, and Taint. Devastating when they're ahead.", False),
            ("Rank 7", "🐕 **Hound of Tindalos** (Cost 4) — 12 + Arcane damage, ignores Elder Defense. Punishes tanky builds.", False),
            ("Rank 9", "🌊 **Rise of the Deep Ones** (Cost 4) — 10 + Arcane damage AND gains +2 Arcane + 2 Elder. Snowballs.", False),
            ("Rank 11", "🎲 **Mad Experiment** (Cost 3) — High-variance wildcard. Four possible outcomes. Can hurt you.", False),
            ("Rank 13", "🌅 **Dawn of a New Day** (Cost 0) — Full board reset. Guarantees your Sanity ≥ 5. Use to escape losing positions.", False),
            ("Rank 15", "🐐 **Black Goat of the Woods** (Cost 8) — Power 10 creature + 8 + Arcane burst on summon. High cost, massive swing.", False),
            ("Rank 17", "🌟 **Professor Armitage** (Cost 0) — Taint → 0, +2 Arcane, +4 Elder Defense. Zero cost for all that. Exceptional.", False),
            ("Rank 19", "⚡ **Yog-Sothoth** (Cost 0) — Damage equal to their Sanity, both Sanities → 0. Free and devastating mid-game.", False),
            ("Rank 20", "🌊 **City of R'lyeh** (Cost 6) — Sanity nuke. If already insane: 20 + Arcane. Two-card Insanity + R'lyeh combo wins games.", False),
        ],
    },

    # ── 11. Game Modes ────────────────────────────────────────────────────────
    {
        "title": "🎮 Game Modes",
        "colour": DEEP_TEAL,
        "image": _u("menu_bg.png"),
        "sections": [
            ("📖 Campaign", (
                "Fight through **20 increasingly powerful AI enemies**, "
                "from street-level thugs to Azathoth himself. "
                "Each win advances your stage. Enemies have fixed decks and stats "
                "tailored to their lore. Win XP to rank up between battles."
            ), False),
            ("👥 Multiplayer", (
                "Click **Multiplayer** in the main menu to post an open lobby. "
                "Anyone in the server can click **Join Game** to face you. "
                "Both players use their own ranked decks — higher rank means more "
                "Life and access to stronger cards."
            ), False),
            ("⚔️ Challenge Mode", (
                "Curated asymmetric scenarios with special rules. Examples:\n\n"
                "• **Glass Cannon** — both players start with only 10 Life but massive Arcane\n"
                "• **Blitz** — two actions per turn, chaos ensues\n"
                "• **Madness Run** — start insane, survive 8 rounds\n"
                "• **Against the Horde** — you get 3 actions vs. a 150-Life behemoth\n\n"
                "Completed challenges are marked ✅. Future updates will add rewards."
            ), False),
            ("💬 Direct Challenge", (
                "Use `/challenge @player` to send a direct duel invite. "
                "The target can accept or decline. Both players use their own ranked decks."
            ), False),
        ],
    },

    # ── 12. Ranks & Progression ───────────────────────────────────────────────
    {
        "title": "🏆 Ranks & Progression",
        "colour": GOLD,
        "image": None,
        "sections": [
            ("Earning XP", (
                "XP is earned by **winning** games. Your XP reward is calculated from:\n\n"
                "• Remaining Life\n"
                "• Remaining Sanity (can be negative)\n"
                "• Total damage dealt\n"
                "• Your single best hit\n"
                "• **Minus** damage received\n\n"
                "Losses earn 0 XP."
            ), False),
            ("Rank Thresholds", (
                "\n".join(
                    f"**Rank {r} — {RANK_NAMES[r]}:** {RANK_XP_THRESHOLDS[r]} XP"
                    for r in sorted(RANK_XP_THRESHOLDS)
                )
            ), False),
            ("What Rank Affects", (
                "📈 **Starting Life** — 40 + (5 × rank), up to 100\n"
                "🃏 **Card Unlocks** — most cards are Rank 1; rarer ones need Ranks 3–20\n"
                "👾 **Campaign Enemies** — matched to stage, not your rank\n"
                "⚔️ **Challenge Access** — some challenges require a minimum rank\n"
                "🎭 **Discord Role** — you are automatically assigned your rank role on wins"
            ), False),
            ("Discord Rank Roles", (
                "The bot assigns your current rank as a Discord role after every win. "
                "If your role ever looks wrong, use `/sync_role` to fix it.\n\n"
                "Admins can run `/setup_roles` to create all roles, "
                "or `/sync_all_roles` to bulk-correct the entire server."
            ), False),
        ],
    },
]

TOTAL_PAGES = len(PAGES)


# ── Embed builder ─────────────────────────────────────────────────────────────

def build_page(page_index: int) -> tuple[discord.Embed, Optional[discord.File]]:
    """
    Build a discord.Embed and optional discord.File for the given page index.
    Returns (embed, file_or_None).
    """
    page = PAGES[page_index]

    embed = discord.Embed(
        title=page["title"],
        colour=page["colour"],
    )
    embed.set_footer(text=f"Page {page_index + 1} of {TOTAL_PAGES}  •  Necronomicon Card Game")

    for name, value, inline in page["sections"]:
        # Truncate values to Discord's 1024-char field limit
        embed.add_field(name=name, value=value[:1024], inline=inline)

    # Image
    img_path = page.get("image")
    if img_path and os.path.exists(img_path):
        filename = os.path.basename(img_path)
        file = discord.File(img_path, filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        return embed, file

    return embed, None


# ── Navigation View ───────────────────────────────────────────────────────────

class GuideView(discord.ui.View):
    """Persistent previous/next navigation for the guide."""

    def __init__(self, page: int = 0, owner_id: Optional[int] = None):
        super().__init__(timeout=300)
        self.page = page
        self.owner_id = owner_id  # If set, only this user can navigate
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.clear_items()

        prev = discord.ui.Button(
            label="◀ Previous",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0),
            custom_id="guide_prev",
        )
        prev.callback = self._prev_callback
        self.add_item(prev)

        # Page indicator (non-interactive)
        indicator = discord.ui.Button(
            label=f"{self.page + 1} / {TOTAL_PAGES}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id="guide_indicator",
        )
        self.add_item(indicator)

        nxt = discord.ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == TOTAL_PAGES - 1),
            custom_id="guide_next",
        )
        nxt.callback = self._next_callback
        self.add_item(nxt)

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if self.owner_id and interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Open your own guide with `/guide`.", ephemeral=True)
            return False
        return True

    async def _navigate(self, interaction: discord.Interaction, delta: int):
        if not await self._check_owner(interaction):
            return
        self.page = max(0, min(TOTAL_PAGES - 1, self.page + delta))
        self._refresh_buttons()
        embed, file = build_page(self.page)
        if file:
            await interaction.response.edit_message(
                embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(
                embed=embed, attachments=[], view=self)

    async def _prev_callback(self, interaction: discord.Interaction):
        await self._navigate(interaction, -1)

    async def _next_callback(self, interaction: discord.Interaction):
        await self._navigate(interaction, +1)


# ── Public entry point ────────────────────────────────────────────────────────

async def send_guide(interaction: discord.Interaction,
                     page: int = 0,
                     ephemeral: bool = True):
    """
    Send (or defer-send) the guide to an interaction.
    Call this from any Guide button or /guide command.
    """
    embed, file = build_page(page)
    view = GuideView(page=page, owner_id=interaction.user.id)

    kwargs: dict = {"embed": embed, "view": view, "ephemeral": ephemeral}
    if file:
        kwargs["file"] = file

    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)

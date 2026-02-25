"""Necronomicon Card Game - Card Definitions and Effects"""

import random
from models import Card, Monster, Player


# === Card Effect Functions ===
# Each returns a list of log messages describing what happened.
# Signature: effect(player: Player, opponent: Player) -> list[str]


def effect_pnakotic_manuscripts(player: Player, opponent: Player) -> list[str]:
    player.modify_arcane(3)
    return [f"{player.display_name} gains 3 Arcane Power. (Arcane: {player.arcane})"]


def effect_mi_go_surgery(player: Player, opponent: Player) -> list[str]:
    player.gain_life(7)
    player.modify_arcane(-2)
    return [
        f"{player.display_name} gains 7 Life. (Life: {player.life})",
        f"{player.display_name} loses 2 Arcane. (Arcane: {player.arcane})"
    ]


def effect_discreet_doctor(player: Player, opponent: Player) -> list[str]:
    player.gain_life(4)
    return [f"{player.display_name} gains 4 Life. (Life: {player.life})"]


def effect_essence_of_the_soul(player: Player, opponent: Player) -> list[str]:
    player.gain_life(9)
    return [f"{player.display_name} gains 9 Life. (Life: {player.life})"]


def effect_blast_em(player: Player, opponent: Player) -> list[str]:
    dmg = player.deal_damage_to(opponent, 3, ignore_elder=True, ignore_invulnerable=True)
    return [f"{player.display_name} blasts {opponent.display_name} for {dmg} damage! (Ignores Elder Defense & Invulnerability)"]


def effect_dark_ritual(player: Player, opponent: Player) -> list[str]:
    total_dmg = 10 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    player.gain_life(3)
    return [
        f"{player.display_name} performs a Dark Ritual for {dmg} damage! (10 + {player.arcane} Arcane)",
        f"{player.display_name} gains 3 Life. (Life: {player.life})"
    ]


def effect_byakhee(player: Player, opponent: Player) -> list[str]:
    monster = Monster(
        name="Byakhee",
        monster_id="byakhee",
        power=3,
        traits=["byakhee_only"]
    )
    return player.summon_monster(monster)


def effect_sacrificial_lamb(player: Player, opponent: Player) -> list[str]:
    msgs = [f"{player.display_name} gains 5 Life. (Life: {player.life + 5})"]
    player.gain_life(5)
    if opponent.monster:
        name = opponent.monster.name
        opponent.remove_monster()
        msgs.append(f"{opponent.display_name}'s {name} is banished!")
    else:
        msgs.append(f"{opponent.display_name} has no creature to banish.")
    return msgs


def effect_dark_young_charge(player: Player, opponent: Player) -> list[str]:
    total_dmg = 14 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    return [f"{player.display_name} unleashes Dark Young Charge for {dmg} damage! (14 + {player.arcane} Arcane)"]


def effect_dimensional_shambler(player: Player, opponent: Player) -> list[str]:
    monster = Monster(
        name="Dimensional Shambler",
        monster_id="dimensional_shambler",
        power=4,
        traits=["piercing"]
    )
    return player.summon_monster(monster)


def effect_tommy_gun(player: Player, opponent: Player) -> list[str]:
    dmg = player.deal_damage_to(opponent, 5, ignore_elder=True, ignore_invulnerable=True)
    return [f"{player.display_name} fires a Tommy Gun for {dmg} damage! (Ignores Elder Defense & Invulnerability)"]


def effect_curse_of_cthulhu(player: Player, opponent: Player) -> list[str]:
    opponent.modify_taint(1)
    return [f"{opponent.display_name} gains 1 Taint. (Taint: {opponent.taint})"]


def effect_king_in_yellow(player: Player, opponent: Player) -> list[str]:
    opponent.modify_sanity(-5)
    opponent.modify_taint(2)
    return [
        f"{opponent.display_name} loses 5 Sanity. (Sanity: {opponent.sanity})",
        f"{opponent.display_name} gains 2 Taint. (Taint: {opponent.taint})"
    ]


def effect_blessing_of_hastur(player: Player, opponent: Player) -> list[str]:
    player.set_taint(0)
    opponent.modify_taint(2)
    return [
        f"{player.display_name}'s Taint is reset to 0.",
        f"{opponent.display_name} gains 2 Taint. (Taint: {opponent.taint})"
    ]


def effect_shoggoth(player: Player, opponent: Player) -> list[str]:
    msgs = []
    # Destroy opponent's creature on summon
    if opponent.monster:
        name = opponent.monster.name
        opponent.remove_monster()
        msgs.append(f"Shoggoth destroys {opponent.display_name}'s {name}!")
    monster = Monster(
        name="Shoggoth",
        monster_id="shoggoth",
        power=6,
        traits=["destroy_on_summon"]
    )
    msgs.extend(player.summon_monster(monster))
    return msgs


def effect_from_beyond(player: Player, opponent: Player) -> list[str]:
    opponent.modify_sanity(-6)
    total_dmg = 8 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    return [
        f"{opponent.display_name} loses 6 Sanity. (Sanity: {opponent.sanity})",
        f"{player.display_name} deals {dmg} damage from beyond! (8 + {player.arcane} Arcane)"
    ]


def effect_elder_sign(player: Player, opponent: Player) -> list[str]:
    player.invulnerable = True
    player.modify_elder_defense(2)
    return [
        f"{player.display_name} becomes Invulnerable!",
        f"{player.display_name} gains 2 Elder Defense. (Elder: {player.elder_defense})"
    ]


def effect_arkham_asylum(player: Player, opponent: Player) -> list[str]:
    player.modify_sanity(15)
    return [f"{player.display_name} gains 15 Sanity. (Sanity: {player.sanity})"]


def effect_powder_of_ibn_ghazi(player: Player, opponent: Player) -> list[str]:
    msgs = []
    if opponent.monster:
        name = opponent.monster.name
        opponent.remove_monster()
        msgs.append(f"{opponent.display_name}'s {name} is banished!")
    else:
        msgs.append(f"{opponent.display_name} has no creature to banish.")
    opponent.set_arcane(0)
    msgs.append(f"{opponent.display_name}'s Arcane is reset to 0.")
    return msgs


def effect_dispel(player: Player, opponent: Player) -> list[str]:
    opponent.set_elder_defense(0)
    opponent.invulnerable = False
    return [
        f"{opponent.display_name}'s Elder Defense is removed.",
        f"{opponent.display_name}'s Invulnerability is removed."
    ]


def effect_unaussprechlichen_kulten(player: Player, opponent: Player) -> list[str]:
    player.modify_arcane(5)
    return [f"{player.display_name} gains 5 Arcane Power. (Arcane: {player.arcane})"]


def effect_blackmail(player: Player, opponent: Player) -> list[str]:
    if opponent.hand:
        if opponent.is_bot:
            # Bot discards the least valuable card (lowest sanity cost)
            idx = min(range(len(opponent.hand)), key=lambda i: opponent.hand[i].sanity_cost)
            card = opponent.hand[idx]
            opponent.replace_card(idx)
            return [f"{opponent.display_name} is forced to discard {card.name} and draws a new card."]
        else:
            # For human opponents, this will be handled by the Discord UI
            # returning a flag message that the engine will intercept
            return ["BLACKMAIL_CHOICE"]
    return [f"{opponent.display_name} has no cards to discard."]


def effect_mind_burn(player: Player, opponent: Player) -> list[str]:
    total_dmg = 7 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    return [f"{player.display_name} burns {opponent.display_name}'s mind for {dmg} damage! (7 + {player.arcane} Arcane)"]


def effect_raid(player: Player, opponent: Player) -> list[str]:
    dmg = player.deal_damage_to(opponent, 7, ignore_elder=True, ignore_invulnerable=True)
    return [f"{player.display_name} raids for {dmg} damage! (Ignores Elder Defense & Invulnerability)"]


def effect_betrayed(player: Player, opponent: Player) -> list[str]:
    if opponent.monster:
        total_dmg = opponent.monster.power + player.arcane
        dmg = player.deal_damage_to(opponent, total_dmg)
        return [f"{player.display_name} turns {opponent.display_name}'s {opponent.monster.name} against them for {dmg} damage! ({opponent.monster.power} + {player.arcane} Arcane)"]
    else:
        return [f"{opponent.display_name} has no monster to betray. No damage dealt."]


def effect_elder_thing(player: Player, opponent: Player) -> list[str]:
    monster = Monster(
        name="Elder Thing",
        monster_id="elder_thing",
        power=2,
        traits=[]
    )
    msgs = player.summon_monster(monster)
    player.modify_elder_defense(3)
    player.set_taint(0)
    msgs.append(f"{player.display_name} gains 3 Elder Defense. (Elder: {player.elder_defense})")
    msgs.append(f"{player.display_name}'s Taint is removed.")
    return msgs


def effect_miskatonic_university(player: Player, opponent: Player) -> list[str]:
    player.set_taint(0)
    player.modify_sanity(5)
    player.modify_arcane(2)
    return [
        f"{player.display_name}'s Taint is removed.",
        f"{player.display_name} gains 5 Sanity. (Sanity: {player.sanity})",
        f"{player.display_name} gains 2 Arcane. (Arcane: {player.arcane})"
    ]


def effect_doppelganger(player: Player, opponent: Player) -> list[str]:
    player.set_arcane(opponent.arcane)
    player.set_elder_defense(opponent.elder_defense)
    player.set_taint(opponent.taint)
    return [
        f"{player.display_name} mirrors {opponent.display_name}!",
        f"Arcane: {player.arcane}, Elder: {player.elder_defense}, Taint: {player.taint}"
    ]


def effect_hound_of_tindalos(player: Player, opponent: Player) -> list[str]:
    total_dmg = 12 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg, ignore_elder=True)
    return [f"{player.display_name} summons a Hound of Tindalos for {dmg} damage! (12 + {player.arcane} Arcane, ignores Elder Defense)"]


def effect_rise_of_the_deep_ones(player: Player, opponent: Player) -> list[str]:
    total_dmg = 10 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    player.modify_arcane(2)
    player.modify_elder_defense(2)
    return [
        f"{player.display_name} calls the Deep Ones for {dmg} damage! (10 + {player.arcane - 2} Arcane)",
        f"{player.display_name} gains 2 Arcane. (Arcane: {player.arcane})",
        f"{player.display_name} gains 2 Elder Defense. (Elder: {player.elder_defense})"
    ]


def effect_mad_experiment(player: Player, opponent: Player) -> list[str]:
    outcome = random.randint(1, 4)
    msgs = [f"🎲 Mad Experiment outcome {outcome}/4:"]

    if outcome == 1:
        # Summon Shoggoth with its effects
        if opponent.monster:
            name = opponent.monster.name
            opponent.remove_monster()
            msgs.append(f"Shoggoth destroys {opponent.display_name}'s {name}!")
        monster = Monster(name="Shoggoth", monster_id="shoggoth", power=6,
                          traits=["destroy_on_summon"])
        msgs.extend(player.summon_monster(monster))

    elif outcome == 2:
        total_dmg = 15 + player.arcane
        dmg = player.deal_damage_to(opponent, total_dmg)
        msgs.append(f"Deals {dmg} damage! (15 + {player.arcane} Arcane)")

    elif outcome == 3:
        player.modify_arcane(5)
        player.modify_elder_defense(5)
        msgs.append(f"Gains 5 Arcane and 5 Elder Defense! (Arcane: {player.arcane}, Elder: {player.elder_defense})")

    elif outcome == 4:
        if player.sanity > 0:
            player.set_sanity(0)
        if player.madness is None:
            player.madness = random.choice(MADNESS_TYPES)
            msgs.append(f"Sanity set to 0! Gained Madness: {player.madness}")
        else:
            msgs.append(f"Sanity set to 0! Already has Madness: {player.madness}")

    return msgs


def effect_dawn_of_a_new_day(player: Player, opponent: Player) -> list[str]:
    msgs = []
    # Dispel everything in play
    player.invulnerable = False
    player.set_elder_defense(0)
    player.set_taint(0)
    player.set_arcane(0)
    opponent.invulnerable = False
    opponent.set_elder_defense(0)
    opponent.set_taint(0)
    opponent.set_arcane(0)
    if player.monster:
        player.remove_monster()
    if opponent.monster:
        opponent.remove_monster()
    msgs.append("Everything in play is dispelled!")

    # Gain 5 sanity with minimum of 5
    player.modify_sanity(5)
    if player.sanity < 5:
        player.set_sanity(5)
    msgs.append(f"{player.display_name} gains Sanity. (Sanity: {player.sanity})")
    return msgs


def effect_black_goat_of_the_woods(player: Player, opponent: Player) -> list[str]:
    monster = Monster(
        name="Black Goat of the Woods",
        monster_id="black_goat",
        power=10,
        traits=[]
    )
    msgs = player.summon_monster(monster)
    total_dmg = 8 + player.arcane
    dmg = player.deal_damage_to(opponent, total_dmg)
    msgs.append(f"Black Goat deals {dmg} damage on arrival! (8 + {player.arcane} Arcane)")
    return msgs


def effect_professor_armitage(player: Player, opponent: Player) -> list[str]:
    player.set_taint(0)
    player.modify_arcane(2)
    player.modify_elder_defense(4)
    return [
        f"{player.display_name}'s Taint is removed.",
        f"{player.display_name} gains 2 Arcane. (Arcane: {player.arcane})",
        f"{player.display_name} gains 4 Elder Defense. (Elder: {player.elder_defense})"
    ]


def effect_yog_sothoth(player: Player, opponent: Player) -> list[str]:
    msgs = []
    # Damage equal to opponent's sanity
    if opponent.sanity > 0:
        dmg = player.deal_damage_to(opponent, opponent.sanity)
        msgs.append(f"{opponent.display_name} takes {dmg} damage equal to their Sanity!")

    # Set both to 0 unless already at or below
    if player.sanity > 0:
        player.set_sanity(0)
    if player.madness is None:
        player.madness = random.choice(MADNESS_TYPES)
    msgs.append(f"{player.display_name}'s Sanity set to 0. Madness: {player.madness}")

    if opponent.sanity > 0:
        opponent.set_sanity(0)
    if opponent.madness is None:
        opponent.madness = random.choice(MADNESS_TYPES)
    msgs.append(f"{opponent.display_name}'s Sanity set to 0. Madness: {opponent.madness}")

    return msgs


def effect_city_of_rlyeh(player: Player, opponent: Player) -> list[str]:
    msgs = []
    if opponent.is_insane:
        # Already insane — deal 20 + Arcane damage
        total_dmg = 20 + player.arcane
        dmg = player.deal_damage_to(opponent, total_dmg)
        msgs.append(f"{opponent.display_name} is already insane! Takes {dmg} damage! (20 + {player.arcane} Arcane)")
    else:
        # Set sanity to 0 and gain madness
        opponent.set_sanity(0)
        if opponent.madness is None:
            opponent.madness = random.choice(MADNESS_TYPES)
        msgs.append(f"{opponent.display_name}'s Sanity set to 0. Madness: {opponent.madness}")
    return msgs


# === Card Registry ===

# Map card_id -> effect function
CARD_EFFECTS = {
    "pnakotic_manuscripts": effect_pnakotic_manuscripts,
    "mi_go_surgery": effect_mi_go_surgery,
    "discreet_doctor": effect_discreet_doctor,
    "essence_of_the_soul": effect_essence_of_the_soul,
    "blast_em": effect_blast_em,
    "dark_ritual": effect_dark_ritual,
    "byakhee": effect_byakhee,
    "sacrificial_lamb": effect_sacrificial_lamb,
    "dark_young_charge": effect_dark_young_charge,
    "dimensional_shambler": effect_dimensional_shambler,
    "tommy_gun": effect_tommy_gun,
    "curse_of_cthulhu": effect_curse_of_cthulhu,
    "king_in_yellow": effect_king_in_yellow,
    "blessing_of_hastur": effect_blessing_of_hastur,
    "shoggoth": effect_shoggoth,
    "from_beyond": effect_from_beyond,
    "elder_sign": effect_elder_sign,
    "arkham_asylum": effect_arkham_asylum,
    "powder_of_ibn_ghazi": effect_powder_of_ibn_ghazi,
    "dispel": effect_dispel,
    "unaussprechlichen_kulten": effect_unaussprechlichen_kulten,
    "blackmail": effect_blackmail,
    "mind_burn": effect_mind_burn,
    "raid": effect_raid,
    "betrayed": effect_betrayed,
    "elder_thing": effect_elder_thing,
    "miskatonic_university": effect_miskatonic_university,
    "doppelganger": effect_doppelganger,
    "hound_of_tindalos": effect_hound_of_tindalos,
    "rise_of_the_deep_ones": effect_rise_of_the_deep_ones,
    "mad_experiment": effect_mad_experiment,
    "dawn_of_a_new_day": effect_dawn_of_a_new_day,
    "black_goat_of_the_woods": effect_black_goat_of_the_woods,
    "professor_armitage": effect_professor_armitage,
    "yog_sothoth": effect_yog_sothoth,
    "city_of_rlyeh": effect_city_of_rlyeh,
}

# All card definitions
ALL_CARDS: list[Card] = [
    Card("Pnakotic Manuscripts", "pnakotic_manuscripts", 1, sanity_cost=2,
         description="Arcane +3"),
    Card("Mi-Go Surgery", "mi_go_surgery", 1, sanity_cost=1,
         description="Gain 7 Life, Arcane -2"),
    Card("Discreet Doctor", "discreet_doctor", 1, sanity_cost=0,
         description="Gain 4 Life"),
    Card("Essence of the Soul", "essence_of_the_soul", 1, sanity_cost=3,
         description="Gain 9 Life"),
    Card("Blast'em", "blast_em", 1, sanity_cost=0,
         description="Damage 3, ignores Elder Defense and Invulnerability"),
    Card("Dark Ritual", "dark_ritual", 1, sanity_cost=2,
         description="Damage 10 + Arcane, Gain 3 Life"),
    Card("Byakhee", "byakhee", 1, sanity_cost=2,
         description="Summon Byakhee (Power 3, only blocked by Byakhee)"),
    Card("Sacrificial Lamb", "sacrificial_lamb", 1, sanity_cost=2,
         description="Gain 5 Life, Banish opponent's creature"),
    Card("Dark Young Charge", "dark_young_charge", 1, sanity_cost=4,
         description="Damage 14 + Arcane"),
    Card("Dimensional Shambler", "dimensional_shambler", 1, sanity_cost=3,
         description="Summon Dimensional Shambler (Power 4, ignores Elder Defense)"),
    Card("Tommy Gun", "tommy_gun", 1, sanity_cost=0,
         description="Damage 5, ignores Elder Defense and Invulnerability"),
    Card("Curse of Cthulhu", "curse_of_cthulhu", 1, sanity_cost=1,
         description="Opponent gains 1 Taint"),
    Card("The King in Yellow", "king_in_yellow", 1, sanity_cost=2,
         description="Opponent loses 5 Sanity, gains 2 Taint"),
    Card("Blessing of Hastur", "blessing_of_hastur", 1, sanity_cost=3,
         description="Reset your Taint to 0, opponent gains 2 Taint"),
    Card("Shoggoth", "shoggoth", 1, sanity_cost=4,
         description="Summon Shoggoth (Power 6, destroys opponent's creature on summon)"),
    Card("From Beyond", "from_beyond", 1, sanity_cost=3,
         description="Opponent loses 6 Sanity, damaged for 8 + Arcane"),
    Card("Elder Sign", "elder_sign", 1, sanity_cost=0,
         description="Gain Invulnerable and 2 Elder Defense"),
    Card("Arkham Asylum", "arkham_asylum", 1, sanity_cost=0,
         description="Gain 15 Sanity"),
    Card("Powder of Ibn-Ghazi", "powder_of_ibn_ghazi", 1, sanity_cost=1,
         description="Banish opponent's creature, reset their Arcane to 0"),
    Card("Dispel", "dispel", 1, sanity_cost=1,
         description="Remove opponent's Elder Defense and Invulnerability"),
    Card("Unaussprechlichen Kulten", "unaussprechlichen_kulten", 1, sanity_cost=3,
         description="Gain 5 Arcane"),
    Card("Blackmail", "blackmail", 1, sanity_cost=0,
         description="Opponent discards a card of their choice and draws a new one"),
    Card("Mind Burn", "mind_burn", 1, sanity_cost=1,
         description="Damage 7 + Arcane"),
    Card("Raid", "raid", 1, sanity_cost=0,
         description="Damage 7, ignores Elder Defense and Invulnerability"),
    Card("Betrayed", "betrayed", 1, sanity_cost=0,
         description="If opponent has a monster, deal damage equal to its power + Arcane"),
    Card("Elder Thing", "elder_thing", 1, sanity_cost=1,
         description="Summon Elder Thing (Power 2), gain 3 Elder Defense, remove Taint"),
    Card("Miskatonic University", "miskatonic_university", 3, sanity_cost=0,
         description="Remove Taint, gain 5 Sanity, gain 2 Arcane"),
    Card("Doppelganger", "doppelganger", 5, sanity_cost=1,
         description="Set your Arcane, Elder, and Taint equal to opponent's"),
    Card("Hound of Tindalos", "hound_of_tindalos", 7, sanity_cost=4,
         description="Damage 12 + Arcane, ignores Elder Defense"),
    Card("Rise of the Deep Ones", "rise_of_the_deep_ones", 9, sanity_cost=4,
         description="Damage 10 + Arcane, gain 2 Arcane and 2 Elder Defense"),
    Card("Mad Experiment", "mad_experiment", 11, sanity_cost=3,
         description="Random: Summon Shoggoth / Damage 15+Arcane / Gain 5 Arcane+Elder / Sanity to 0+Madness"),
    Card("Dawn of a New Day", "dawn_of_a_new_day", 13, sanity_cost=0,
         description="Dispel everything in play, gain 5 Sanity (min 5)"),
    Card("Black Goat of the Woods", "black_goat_of_the_woods", 15, sanity_cost=8,
         description="Summon Black Goat (Power 10), deals 8 + Arcane damage"),
    Card("Professor Armitage", "professor_armitage", 17, sanity_cost=0,
         description="Remove Taint, gain 2 Arcane, gain 4 Elder Defense"),
    Card("Yog-Sothoth", "yog_sothoth", 19, sanity_cost=0,
         description="Damage opponent equal to their Sanity, both Sanity set to 0 + Madness"),
    Card("City of R'lyeh", "city_of_rlyeh", 20, sanity_cost=6,
         description="Opponent Sanity to 0 + Madness, or if already insane: 20 + Arcane damage"),
]

# Quick lookup by card_id
CARDS_BY_ID = {card.card_id: card for card in ALL_CARDS}


def get_cards_for_rank(rank: int) -> list[Card]:
    """Get all cards available at a given rank."""
    return [c for c in ALL_CARDS if c.rank_required <= rank]


def execute_card(card: Card, player: Player, opponent: Player) -> list[str]:
    """Execute a card's effect and return log messages."""
    effect_fn = CARD_EFFECTS.get(card.card_id)
    if effect_fn is None:
        return [f"ERROR: No effect defined for card {card.card_id}"]
    return effect_fn(player, opponent)

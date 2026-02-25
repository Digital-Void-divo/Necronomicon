"""Necronomicon Card Game - Campaign System"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CampaignEnemy:
    """Definition of a campaign opponent."""
    name: str
    rank: int
    life: int
    sanity: int = 30
    taint: int = 0
    arcane: int = 0
    elder_defense: int = 0
    avatar_id: str = ""  # Reference to enemy portrait
    card_ids: list = field(default_factory=list)  # Specific card IDs, empty = use rank default


# Campaign enemies in order - 20 opponents scaling in difficulty
CAMPAIGN_ENEMIES = [
    # Tier 1: Street Level (Ranks 1-3)
    CampaignEnemy(
        name="Street Thug",
        rank=1, life=30, sanity=25,
        card_ids=["blast_em", "tommy_gun", "raid", "discreet_doctor",
                  "mi_go_surgery", "byakhee", "curse_of_cthulhu",
                  "blackmail", "elder_sign", "arkham_asylum"]
    ),
    CampaignEnemy(
        name="Cultist Initiate",
        rank=1, life=35, sanity=30,
        card_ids=["pnakotic_manuscripts", "dark_ritual", "curse_of_cthulhu",
                  "king_in_yellow", "byakhee", "blast_em", "discreet_doctor",
                  "elder_thing", "arkham_asylum", "dispel"]
    ),
    CampaignEnemy(
        name="Corrupt Priest",
        rank=2, life=38, sanity=30, arcane=1,
        card_ids=["dark_ritual", "essence_of_the_soul", "blessing_of_hastur",
                  "curse_of_cthulhu", "king_in_yellow", "elder_sign",
                  "shoggoth", "from_beyond", "arkham_asylum", "sacrificial_lamb"]
    ),

    # Tier 2: Occult Underworld (Ranks 3-6)
    CampaignEnemy(
        name="Mad Scholar",
        rank=3, life=40, sanity=20, arcane=2,
        card_ids=["pnakotic_manuscripts", "unaussprechlichen_kulten", "mind_burn",
                  "from_beyond", "dark_young_charge", "arkham_asylum",
                  "dimensional_shambler", "dispel", "miskatonic_university",
                  "dark_ritual"]
    ),
    CampaignEnemy(
        name="Witch of Arkham",
        rank=4, life=42, sanity=30, taint=1, arcane=2,
        card_ids=["blessing_of_hastur", "king_in_yellow", "curse_of_cthulhu",
                  "shoggoth", "dark_ritual", "elder_thing", "sacrificial_lamb",
                  "essence_of_the_soul", "from_beyond", "powder_of_ibn_ghazi",
                  "miskatonic_university"]
    ),
    CampaignEnemy(
        name="Deep One Hybrid",
        rank=5, life=45, sanity=30, elder_defense=2,
        card_ids=["dimensional_shambler", "shoggoth", "dark_young_charge",
                  "elder_sign", "sacrificial_lamb", "blast_em", "tommy_gun",
                  "mi_go_surgery", "essence_of_the_soul", "doppelganger",
                  "miskatonic_university", "betrayed"]
    ),

    # Tier 3: Inner Circle (Ranks 6-9)
    CampaignEnemy(
        name="Silver Twilight Magus",
        rank=6, life=48, sanity=30, arcane=3,
        card_ids=["unaussprechlichen_kulten", "pnakotic_manuscripts", "dark_ritual",
                  "mind_burn", "from_beyond", "elder_sign", "dispel",
                  "shoggoth", "arkham_asylum", "doppelganger",
                  "miskatonic_university", "dark_young_charge"]
    ),
    CampaignEnemy(
        name="Mi-Go Surgeon",
        rank=7, life=50, sanity=25, arcane=2, elder_defense=2,
        card_ids=["mi_go_surgery", "dimensional_shambler", "powder_of_ibn_ghazi",
                  "tommy_gun", "blast_em", "hound_of_tindalos", "elder_sign",
                  "blackmail", "raid", "dispel", "miskatonic_university",
                  "betrayed", "doppelganger"]
    ),
    CampaignEnemy(
        name="Keeper of the Yellow Sign",
        rank=8, life=52, sanity=30, taint=0, arcane=3,
        card_ids=["king_in_yellow", "curse_of_cthulhu", "blessing_of_hastur",
                  "from_beyond", "dark_ritual", "shoggoth", "hound_of_tindalos",
                  "elder_sign", "arkham_asylum", "dispel",
                  "miskatonic_university", "doppelganger", "dark_young_charge"]
    ),

    # Tier 4: Outer Dark (Ranks 9-12)
    CampaignEnemy(
        name="Spawn of Dagon",
        rank=9, life=55, sanity=30, arcane=3, elder_defense=3,
        card_ids=["dark_young_charge", "from_beyond", "shoggoth",
                  "dimensional_shambler", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "elder_sign", "essence_of_the_soul", "sacrificial_lamb",
                  "dispel", "miskatonic_university", "doppelganger",
                  "betrayed", "powder_of_ibn_ghazi"]
    ),
    CampaignEnemy(
        name="Dream Witch",
        rank=10, life=55, sanity=15, arcane=5,
        card_ids=["mind_burn", "from_beyond", "dark_young_charge",
                  "king_in_yellow", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "mad_experiment", "arkham_asylum", "elder_sign",
                  "unaussprechlichen_kulten", "doppelganger", "miskatonic_university",
                  "dark_ritual", "pnakotic_manuscripts"]
    ),
    CampaignEnemy(
        name="Starspawn",
        rank=11, life=60, sanity=30, arcane=4, elder_defense=2,
        card_ids=["shoggoth", "from_beyond", "dark_young_charge",
                  "hound_of_tindalos", "rise_of_the_deep_ones", "mad_experiment",
                  "elder_sign", "dispel", "sacrificial_lamb", "powder_of_ibn_ghazi",
                  "essence_of_the_soul", "doppelganger", "miskatonic_university",
                  "blessing_of_hastur"]
    ),

    # Tier 5: Elder Terrors (Ranks 13-16)
    CampaignEnemy(
        name="Avatar of Hastur",
        rank=13, life=65, sanity=30, arcane=5, taint=0,
        card_ids=["king_in_yellow", "blessing_of_hastur", "curse_of_cthulhu",
                  "from_beyond", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "mad_experiment", "dawn_of_a_new_day", "shoggoth",
                  "dark_young_charge", "elder_sign", "doppelganger",
                  "miskatonic_university", "unaussprechlichen_kulten", "dispel"]
    ),
    CampaignEnemy(
        name="The Haunter in the Dark",
        rank=14, life=68, sanity=25, arcane=5, elder_defense=4,
        card_ids=["from_beyond", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "mad_experiment", "dawn_of_a_new_day", "shoggoth",
                  "dark_young_charge", "elder_sign", "dispel", "doppelganger",
                  "powder_of_ibn_ghazi", "professor_armitage", "miskatonic_university",
                  "essence_of_the_soul", "mind_burn", "dark_ritual"]
    ),
    CampaignEnemy(
        name="Shub-Niggurath's Chosen",
        rank=15, life=72, sanity=30, arcane=5, elder_defense=3,
        card_ids=["black_goat_of_the_woods", "shoggoth", "from_beyond",
                  "hound_of_tindalos", "rise_of_the_deep_ones", "mad_experiment",
                  "dawn_of_a_new_day", "elder_sign", "professor_armitage",
                  "doppelganger", "miskatonic_university", "dark_young_charge",
                  "sacrificial_lamb", "blessing_of_hastur", "dispel"]
    ),

    # Tier 6: The Great Old Ones (Ranks 17-20)
    CampaignEnemy(
        name="High Priest of Cthulhu",
        rank=17, life=78, sanity=30, arcane=6, elder_defense=4,
        card_ids=["from_beyond", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "mad_experiment", "dawn_of_a_new_day", "black_goat_of_the_woods",
                  "shoggoth", "elder_sign", "professor_armitage", "doppelganger",
                  "miskatonic_university", "dark_young_charge", "dispel",
                  "blessing_of_hastur", "yog_sothoth", "essence_of_the_soul"]
    ),
    CampaignEnemy(
        name="The Dunwich Horror",
        rank=18, life=82, sanity=20, arcane=7, elder_defense=3,
        card_ids=["mad_experiment", "from_beyond", "hound_of_tindalos",
                  "rise_of_the_deep_ones", "dawn_of_a_new_day",
                  "black_goat_of_the_woods", "shoggoth", "elder_sign",
                  "professor_armitage", "yog_sothoth", "doppelganger",
                  "miskatonic_university", "dark_young_charge", "dispel",
                  "mind_burn", "dark_ritual", "unaussprechlichen_kulten"]
    ),
    CampaignEnemy(
        name="Nyarlathotep",
        rank=19, life=88, sanity=30, arcane=8, elder_defense=5,
        card_ids=["yog_sothoth", "mad_experiment", "from_beyond",
                  "hound_of_tindalos", "rise_of_the_deep_ones",
                  "dawn_of_a_new_day", "black_goat_of_the_woods", "shoggoth",
                  "elder_sign", "professor_armitage", "doppelganger",
                  "miskatonic_university", "dark_young_charge", "dispel",
                  "blessing_of_hastur", "king_in_yellow", "city_of_rlyeh"]
    ),

    # FINAL BOSS (repeatable)
    CampaignEnemy(
        name="Azathoth, the Blind Idiot God",
        rank=20, life=100, sanity=30, arcane=10, elder_defense=5,
        card_ids=["city_of_rlyeh", "yog_sothoth", "mad_experiment",
                  "from_beyond", "hound_of_tindalos", "rise_of_the_deep_ones",
                  "dawn_of_a_new_day", "black_goat_of_the_woods", "shoggoth",
                  "elder_sign", "professor_armitage", "doppelganger",
                  "miskatonic_university", "dark_young_charge", "dispel",
                  "blessing_of_hastur", "king_in_yellow",
                  "unaussprechlichen_kulten", "dark_ritual"]
    ),
]


def get_campaign_enemy(stage: int) -> CampaignEnemy:
    """Get the campaign enemy for a given stage (0-indexed).
    After the last enemy, repeats the final boss."""
    if stage < 0:
        stage = 0
    if stage >= len(CAMPAIGN_ENEMIES):
        return CAMPAIGN_ENEMIES[-1]  # Final boss repeats
    return CAMPAIGN_ENEMIES[stage]


def get_total_campaign_stages() -> int:
    return len(CAMPAIGN_ENEMIES)

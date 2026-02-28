"""Necronomicon Card Game - Challenge Manager

Loads challenge definitions from challenges.json and provides helpers
to build players and track per-user completion.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from config import MADNESS_TYPES


CHALLENGES_PATH = os.path.join(os.path.dirname(__file__), "challenges.json")


@dataclass
class ChallengePlayerConfig:
    life: int = 40
    sanity: int = 30
    taint: int = 0
    arcane: int = 0
    elder_defense: int = 0
    hand_size: int = 5
    madness: Optional[str] = None          # Force a specific starting madness
    deck: Optional[list[str]] = None       # Specific card IDs; None = use rank default
    actions_per_turn: int = 1
    turn_limit: Optional[int] = None       # Max rounds before instant-loss


@dataclass
class ChallengeBotConfig(ChallengePlayerConfig):
    name: str = "Unknown"
    rank: int = 5


@dataclass
class ChallengeDefinition:
    id: str
    name: str
    description: str
    min_rank: int
    player: ChallengePlayerConfig
    bot: ChallengeBotConfig


# ── Loader ────────────────────────────────────────────────────────────────────

def _parse_player_config(data: dict) -> ChallengePlayerConfig:
    madness = data.get("madness")
    if madness and madness not in MADNESS_TYPES:
        madness = None  # Silently ignore invalid madness values

    return ChallengePlayerConfig(
        life=data.get("life", 40),
        sanity=data.get("sanity", 30),
        taint=data.get("taint", 0),
        arcane=data.get("arcane", 0),
        elder_defense=data.get("elder_defense", 0),
        hand_size=data.get("hand_size", 5),
        madness=madness,
        deck=data.get("deck"),
        actions_per_turn=max(1, data.get("actions_per_turn", 1)),
        turn_limit=data.get("turn_limit"),
    )


def _parse_bot_config(data: dict) -> ChallengeBotConfig:
    base = _parse_player_config(data)
    return ChallengeBotConfig(
        **{k: getattr(base, k) for k in base.__dataclass_fields__},
        name=data.get("name", "Unknown"),
        rank=data.get("rank", 5),
    )


def load_challenges() -> list[ChallengeDefinition]:
    """Load all challenges from challenges.json. Returns empty list on error."""
    if not os.path.exists(CHALLENGES_PATH):
        print(f"[ChallengeManager] challenges.json not found at {CHALLENGES_PATH}")
        return []

    try:
        with open(CHALLENGES_PATH, "r") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ChallengeManager] Failed to load challenges.json: {e}")
        return []

    challenges = []
    for entry in raw:
        try:
            challenges.append(ChallengeDefinition(
                id=entry["id"],
                name=entry["name"],
                description=entry.get("description", ""),
                min_rank=entry.get("min_rank", 1),
                player=_parse_player_config(entry.get("player", {})),
                bot=_parse_bot_config(entry.get("bot", {})),
            ))
        except (KeyError, TypeError) as e:
            print(f"[ChallengeManager] Skipping malformed challenge entry: {e}")

    return challenges


# Global cache — reloaded each bot startup
_CHALLENGES: list[ChallengeDefinition] = []


def get_all_challenges() -> list[ChallengeDefinition]:
    global _CHALLENGES
    if not _CHALLENGES:
        _CHALLENGES = load_challenges()
    return _CHALLENGES


def get_challenge_by_id(challenge_id: str) -> Optional[ChallengeDefinition]:
    return next((c for c in get_all_challenges() if c.id == challenge_id), None)


def get_available_challenges(player_rank: int) -> list[ChallengeDefinition]:
    """Return challenges the player's rank qualifies for."""
    return [c for c in get_all_challenges() if player_rank >= c.min_rank]


# ── Player / Bot builder helpers ──────────────────────────────────────────────

def apply_challenge_config_to_player(player, cfg: ChallengePlayerConfig,
                                     available_cards, cards_by_id):
    """Apply a ChallengePlayerConfig onto an already-constructed Player object."""
    from cards import get_cards_for_rank

    player.override_starting_stats(
        life=cfg.life,
        sanity=cfg.sanity,
        taint=cfg.taint,
        arcane=cfg.arcane,
        elder_defense=cfg.elder_defense,
    )
    player.hand_size = cfg.hand_size
    player.actions_per_turn = cfg.actions_per_turn
    player.actions_remaining = cfg.actions_per_turn

    # Force starting madness
    if cfg.madness:
        player.madness = cfg.madness

    # Build deck
    if cfg.deck:
        deck_cards = [cards_by_id[cid] for cid in cfg.deck if cid in cards_by_id]
        player.build_deck_from_list(deck_cards)
    else:
        player.build_deck(available_cards)

    player.draw_initial_hand()


def build_challenge_bot(challenge: ChallengeDefinition, cards_by_id: dict):
    """Construct a bot Player fully configured for a challenge."""
    from models import Player
    from cards import get_cards_for_rank

    cfg = challenge.bot
    p = Player(
        user_id=f"bot_challenge_{challenge.id}",
        display_name=cfg.name,
        rank=cfg.rank,
        is_bot=True,
    )
    apply_challenge_config_to_player(
        p, cfg,
        available_cards=get_cards_for_rank(cfg.rank),
        cards_by_id=cards_by_id,
    )
    return p

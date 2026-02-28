"""Necronomicon Card Game - Player Data Persistence"""

import json
import os
from config import PLAYER_DATA_DIR, RANK_XP_THRESHOLDS, RANK_NAMES, MAX_RANK


def _ensure_data_dir():
    os.makedirs(PLAYER_DATA_DIR, exist_ok=True)


def _player_path(user_id: str) -> str:
    return os.path.join(PLAYER_DATA_DIR, f"{user_id}.json")


def get_default_player_data() -> dict:
    return {
        "rank": 1,
        "xp": 0,
        "campaign_stage": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "challenges_completed": [],
        "multiplayer_wins": 0,
        "multiplayer_losses": 0,
    }


def load_player_data(user_id: str) -> dict:
    """Load player data from JSON file, or create default."""
    _ensure_data_dir()
    path = _player_path(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        # Ensure all keys exist (migration)
        default = get_default_player_data()
        for key, value in default.items():
            if key not in data:
                data[key] = value
        return data
    return get_default_player_data()


def save_player_data(user_id: str, data: dict):
    """Save player data to JSON file."""
    _ensure_data_dir()
    path = _player_path(user_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def add_xp(user_id: str, xp_amount: int) -> dict:
    """Add XP to a player and check for rank up. Returns updated data with rank_up info."""
    data = load_player_data(user_id)
    old_rank = data["rank"]
    data["xp"] += xp_amount

    # Check for rank ups
    new_rank = old_rank
    for rank in range(old_rank + 1, MAX_RANK + 1):
        threshold = RANK_XP_THRESHOLDS.get(rank, float("inf"))
        if data["xp"] >= threshold:
            new_rank = rank
        else:
            break

    data["rank"] = new_rank
    save_player_data(user_id, data)

    return {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "ranked_up": new_rank > old_rank,
        "old_rank_name": RANK_NAMES.get(old_rank, f"Rank {old_rank}"),
        "new_rank_name": RANK_NAMES.get(new_rank, f"Rank {new_rank}"),
        "total_xp": data["xp"],
        "xp_gained": xp_amount,
    }


def advance_campaign(user_id: str):
    """Advance campaign stage by 1."""
    data = load_player_data(user_id)
    data["campaign_stage"] += 1
    save_player_data(user_id, data)


def record_win(user_id: str):
    data = load_player_data(user_id)
    data["wins"] += 1
    save_player_data(user_id, data)


def record_loss(user_id: str):
    data = load_player_data(user_id)
    data["losses"] += 1
    save_player_data(user_id, data)


def record_draw(user_id: str):
    data = load_player_data(user_id)
    data["draws"] += 1
    save_player_data(user_id, data)


def mark_challenge_completed(user_id: str, challenge_id: str):
    """Mark a challenge as completed for the player (idempotent)."""
    data = load_player_data(user_id)
    if challenge_id not in data["challenges_completed"]:
        data["challenges_completed"].append(challenge_id)
        save_player_data(user_id, data)


def get_completed_challenges(user_id: str) -> list[str]:
    """Return list of challenge IDs the player has completed."""
    return load_player_data(user_id).get("challenges_completed", [])


def is_challenge_completed(user_id: str, challenge_id: str) -> bool:
    return challenge_id in get_completed_challenges(user_id)

"""Necronomicon Card Game - Role Manager

Handles automatic Discord role assignment based on a player's in-game rank.

HOW IT WORKS
────────────
• Each rank maps to exactly one Discord role by name.
• RANK_ROLE_NAMES below is the single place to edit names / add or remove ranks.
  - To rename a role: change the string value.
  - To skip a rank having a role: set its value to None.
  - To add more ranks: extend both RANK_NAMES in config.py and RANK_ROLE_NAMES here.
• On rank-up, the bot strips every other Necronomicon rank role from the member
  and assigns the new one.  This means roles are always mutually exclusive.
• /setup_roles  — admin command, creates any missing roles in the guild.
• /sync_role    — fixes the calling user's role if it ever drifts out of sync.
• /sync_all_roles — admin command, walks all guild members and corrects roles.

PERMISSIONS NEEDED
──────────────────
The bot role must sit ABOVE all Necronomicon rank roles in the role hierarchy,
and must have the Manage Roles permission.
"""

import discord
from typing import Optional

from config import RANK_NAMES

# ── Role name map ─────────────────────────────────────────────────────────────
# Keys  = rank integer (must match RANK_NAMES in config.py)
# Values = exact Discord role name string, or None to give that rank no role.
# Edit freely — the rest of the system reads from here.

RANK_ROLE_NAMES: dict[int, Optional[str]] = {
    1:  "📖 Thug",
    2:  "📖 Hoodlum",
    3:  "📖 Occultist",
    4:  "📖 Acolyte",
    5:  "📖 Conjurer",
    6:  "📖 Warlock",
    7:  "📖 Sorcerer",
    8:  "📖 Necromancer",
    9:  "📖 Diabolist",
    10: "📖 Shadow Weaver",
    11: "📖 Void Caller",
    12: "📖 Eldritch Sage",
    13: "📖 Abyssal Lord",
    14: "📖 Herald of Madness",
    15: "📖 Outer God's Servant",
    16: "📖 Dreamer in the Deep",
    17: "📖 Keeper of the Gate",
    18: "📖 Star Spawn",
    19: "📖 Great Old One",
    20: "📖 Elder God",
}

# Role colours per rank (R, G, B) — swap these out as desired.
# Ranks progress from muted grey → deep crimson → eldritch gold.
RANK_ROLE_COLOURS: dict[int, discord.Colour] = {
    1:  discord.Colour.from_rgb(120, 120, 120),
    2:  discord.Colour.from_rgb(140, 110, 90),
    3:  discord.Colour.from_rgb(150, 100, 60),
    4:  discord.Colour.from_rgb(160, 90,  50),
    5:  discord.Colour.from_rgb(170, 80,  40),
    6:  discord.Colour.from_rgb(180, 70,  30),
    7:  discord.Colour.from_rgb(190, 60,  20),
    8:  discord.Colour.from_rgb(160, 50,  80),
    9:  discord.Colour.from_rgb(140, 40,  100),
    10: discord.Colour.from_rgb(120, 30,  120),
    11: discord.Colour.from_rgb(100, 20,  140),
    12: discord.Colour.from_rgb(80,  10,  160),
    13: discord.Colour.from_rgb(60,  0,   180),
    14: discord.Colour.from_rgb(180, 40,  40),
    15: discord.Colour.from_rgb(200, 50,  30),
    16: discord.Colour.from_rgb(210, 60,  20),
    17: discord.Colour.from_rgb(220, 140, 20),
    18: discord.Colour.from_rgb(230, 160, 10),
    19: discord.Colour.from_rgb(240, 180, 0),
    20: discord.Colour.from_rgb(255, 215, 0),   # Gold for Elder God
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def all_rank_role_names() -> set[str]:
    """Return the set of all non-None role name values defined above."""
    return {name for name in RANK_ROLE_NAMES.values() if name is not None}


def role_name_for_rank(rank: int) -> Optional[str]:
    return RANK_ROLE_NAMES.get(rank)


def get_rank_role(guild: discord.Guild, rank: int) -> Optional[discord.Role]:
    """Find the Discord Role object for a given rank in a guild, or None."""
    name = role_name_for_rank(rank)
    if name is None:
        return None
    return discord.utils.get(guild.roles, name=name)


def get_all_rank_roles(guild: discord.Guild) -> list[discord.Role]:
    """Return all existing Necronomicon rank roles currently in the guild."""
    names = all_rank_role_names()
    return [r for r in guild.roles if r.name in names]


# ── Core assignment ───────────────────────────────────────────────────────────

async def assign_rank_role(member: discord.Member, new_rank: int) -> tuple[bool, str]:
    """
    Strip all Necronomicon rank roles from *member* and assign the role for
    *new_rank*.  Returns (success: bool, message: str).
    """
    guild = member.guild

    # Collect every rank role the member currently holds
    current_rank_roles = [r for r in member.roles if r.name in all_rank_role_names()]

    # Resolve the target role
    target_role = get_rank_role(guild, new_rank)
    if target_role is None:
        role_name = role_name_for_rank(new_rank)
        if role_name is None:
            # This rank intentionally has no role — just remove old ones
            if current_rank_roles:
                try:
                    await member.remove_roles(*current_rank_roles, reason="Necronomicon rank update")
                except discord.Forbidden:
                    return False, "Missing Manage Roles permission."
                except discord.HTTPException as e:
                    return False, f"HTTP error removing roles: {e}"
            return True, f"Rank {new_rank} has no associated role; old rank roles removed."
        else:
            return False, (
                f"Role **{role_name}** not found in this server. "
                f"Run `/setup_roles` to create it."
            )

    # Already correct — nothing to do
    if target_role in member.roles and len(current_rank_roles) == 1:
        return True, "Role already correct."

    try:
        roles_to_remove = [r for r in current_rank_roles if r != target_role]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Necronomicon rank update")
        if target_role not in member.roles:
            await member.add_roles(target_role, reason=f"Necronomicon rank {new_rank}")
    except discord.Forbidden:
        return False, (
            "I don't have permission to manage roles. Make sure my role is above "
            "all Necronomicon rank roles and I have Manage Roles permission."
        )
    except discord.HTTPException as e:
        return False, f"Failed to update role: {e}"

    return True, f"Assigned **{target_role.name}**."


# ── Guild setup ───────────────────────────────────────────────────────────────

async def setup_rank_roles(guild: discord.Guild) -> tuple[list[str], list[str]]:
    """
    Create any missing rank roles in *guild*.
    Returns (created_names, skipped_names) where skipped = already existed.
    """
    created, skipped = [], []
    existing_names = {r.name for r in guild.roles}

    for rank in sorted(RANK_ROLE_NAMES):
        name = RANK_ROLE_NAMES[rank]
        if name is None:
            continue
        if name in existing_names:
            skipped.append(name)
            continue
        colour = RANK_ROLE_COLOURS.get(rank, discord.Colour.default())
        try:
            await guild.create_role(
                name=name,
                colour=colour,
                mentionable=False,
                hoist=False,           # Set True to display them separately in member list
                reason="Necronomicon rank role setup",
            )
            created.append(name)
        except discord.Forbidden:
            skipped.append(f"{name} (no permission)")
        except discord.HTTPException as e:
            skipped.append(f"{name} (error: {e})")

    return created, skipped


async def delete_rank_roles(guild: discord.Guild) -> tuple[list[str], list[str]]:
    """
    Delete all Necronomicon rank roles from *guild*.
    Returns (deleted_names, failed_names).  Useful for a clean re-setup.
    """
    deleted, failed = [], []
    for role in get_all_rank_roles(guild):
        try:
            await role.delete(reason="Necronomicon rank role cleanup")
            deleted.append(role.name)
        except (discord.Forbidden, discord.HTTPException) as e:
            failed.append(f"{role.name} ({e})")
    return deleted, failed


# ── Bulk sync ─────────────────────────────────────────────────────────────────

async def sync_all_members(guild: discord.Guild, player_data_loader) -> dict:
    """
    Walk every non-bot guild member and correct their rank role.
    *player_data_loader* is a callable: user_id_str -> dict with key "rank".
    Returns a result summary dict.
    """
    updated, already_correct, failed, no_data = 0, 0, 0, 0

    for member in guild.members:
        if member.bot:
            continue
        data = player_data_loader(str(member.id))
        rank = data.get("rank", 0)
        if rank < 1:
            no_data += 1
            continue

        success, msg = await assign_rank_role(member, rank)
        if not success:
            failed += 1
        elif msg == "Role already correct.":
            already_correct += 1
        else:
            updated += 1

    return {
        "updated": updated,
        "already_correct": already_correct,
        "failed": failed,
        "no_data": no_data,
        "total": updated + already_correct + failed + no_data,
    }

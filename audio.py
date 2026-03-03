"""Necronomicon Card Game - Audio System

Handles voice channel connection and audio playback.
Drop MP3 files into assets/audio/ with these names:
  - menu_start.mp3
  - monster_attack.mp3
  - physical_attack.mp3
  - magical_attack.mp3
  - non_attack.mp3
  - battle_start.mp3
  - battle_end.mp3
  - insanity.mp3
"""

import os
import shutil
import asyncio
from typing import Optional

import discord

from config import (
    AUDIO_MENU_START, AUDIO_MONSTER_ATTACK, AUDIO_PHYSICAL_ATTACK,
    AUDIO_MAGICAL_ATTACK, AUDIO_NON_ATTACK, AUDIO_BATTLE_START,
    AUDIO_BATTLE_END, AUDIO_INSANITY,
    PHYSICAL_ATTACK_CARDS, MAGICAL_ATTACK_CARDS, NON_ATTACK_CARDS,
    SUMMON_CARDS,
)


# ── Dependency checks ─────────────────────────────────────────────────────────
# discord.py voice requires PyNaCl and libopus.  Both fail SILENTLY if missing:
#   - Without PyNaCl, VoiceClient.connect() raises RuntimeError (caught by our
#     try/except and logged, but easy to miss in Railway).
#   - Without opus, audio encoding fails — the bot connects (green outline) but
#     sends silence.  We load it explicitly here so the failure is loud.

_PYNACL_AVAILABLE = False
try:
    import nacl  # noqa: F401
    _PYNACL_AVAILABLE = True
    print("[Audio] ✓ PyNaCl is installed — voice connection supported.")
except ImportError:
    print(
        "[Audio] ✗ ERROR: PyNaCl is NOT installed — voice will NOT work!\n"
        "  Fix: add 'PyNaCl>=1.5.0' to requirements.txt and redeploy."
    )

_OPUS_LOADED = False
if not discord.opus.is_loaded():
    # Try common paths
    _opus_paths = [
        "libopus.so.0",          # Linux default
        "libopus.so",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/libopus.so.0",
        "/nix/store",            # nixpacks — resolved below
        "opus",                  # macOS / Windows
    ]
    for path in _opus_paths:
        try:
            discord.opus.load_opus(path)
            if discord.opus.is_loaded():
                _OPUS_LOADED = True
                print(f"[Audio] ✓ Opus loaded from: {path}")
                break
        except Exception:
            continue

    if not _OPUS_LOADED:
        # One more attempt — search /nix/store for libopus
        nix_store = "/nix/store"
        if os.path.isdir(nix_store):
            for entry in os.listdir(nix_store):
                candidate = os.path.join(nix_store, entry, "lib", "libopus.so.0")
                if os.path.exists(candidate):
                    try:
                        discord.opus.load_opus(candidate)
                        if discord.opus.is_loaded():
                            _OPUS_LOADED = True
                            print(f"[Audio] ✓ Opus loaded from nix store: {candidate}")
                            break
                    except Exception:
                        continue

    if not discord.opus.is_loaded():
        print(
            "[Audio] ✗ WARNING: libopus not loaded — audio encoding will fail.\n"
            "  • On Railway: add 'libopus-dev' to nixpacks.toml aptPkgs.\n"
            "  • On Ubuntu: sudo apt install libopus-dev\n"
            "  • On macOS: brew install opus"
        )
    else:
        _OPUS_LOADED = True
else:
    _OPUS_LOADED = True
    print("[Audio] ✓ Opus was already loaded.")


# ── FFmpeg detection ──────────────────────────────────────────────────────────
# Railway / nixpacks installs ffmpeg via apt but it may not be on PATH at import
# time.  We search common locations so audio works without manual PATH edits.

_FFMPEG_SEARCH_PATHS = [
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/nix/store",        # nixpacks sometimes puts binaries here (resolved below)
    "/app/.apt/usr/bin/ffmpeg",   # Heroku-style buildpack path
]

def _find_ffmpeg() -> Optional[str]:
    """Return the absolute path to ffmpeg, or None if not found."""
    # 1. Already on PATH?
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 2. Known fixed locations
    for path in _FFMPEG_SEARCH_PATHS:
        if path == "/nix/store" and os.path.isdir(path):
            # Search nix store for ffmpeg binary
            for entry in os.listdir(path):
                candidate = os.path.join(path, entry, "bin", "ffmpeg")
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate
        elif os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None

FFMPEG_PATH: Optional[str] = _find_ffmpeg()

if FFMPEG_PATH:
    print(f"[Audio] ✓ ffmpeg found: {FFMPEG_PATH}")
else:
    print(
        "[Audio] ✗ WARNING: ffmpeg not found. Voice audio will be silently disabled.\n"
        "  • On Railway: ensure nixpacks.toml contains aptPkgs = [\"ffmpeg\"] and redeploy.\n"
        "  • On Heroku: add the FFmpeg buildpack before the Python buildpack.\n"
        "  • Locally: install ffmpeg and ensure it is on your PATH."
    )


def voice_ready() -> bool:
    """Return True if all voice dependencies are available."""
    return _PYNACL_AVAILABLE and _OPUS_LOADED and FFMPEG_PATH is not None


# Print a summary at startup
if voice_ready():
    print("[Audio] ✓ All voice dependencies OK — audio system is READY.")
else:
    missing = []
    if not _PYNACL_AVAILABLE:
        missing.append("PyNaCl")
    if not _OPUS_LOADED:
        missing.append("libopus")
    if not FFMPEG_PATH:
        missing.append("ffmpeg")
    print(f"[Audio] ✗ Voice system DISABLED — missing: {', '.join(missing)}")


class AudioManager:
    """Manages voice channel connections and audio playback per game session."""

    def __init__(self):
        # guild_id -> voice_client
        self.voice_clients: dict[int, discord.VoiceClient] = {}
        # guild_id -> bool (audio enabled)
        self.audio_enabled: dict[int, bool] = {}

    async def try_join_voice(self, member: discord.Member) -> Optional[discord.VoiceClient]:
        """Join the voice channel the member is in. Returns VoiceClient or None."""
        # ── Pre-flight checks with logging ──
        if not _PYNACL_AVAILABLE:
            print(f"[Audio] Skipping voice join — PyNaCl not installed.")
            return None

        if not member.voice or not member.voice.channel:
            print(f"[Audio] {member.display_name} is not in a voice channel "
                  f"(member.voice={member.voice}).")
            return None

        guild_id = member.guild.id
        voice_channel = member.voice.channel
        print(f"[Audio] Attempting to join '{voice_channel.name}' "
              f"(guild={member.guild.name}, id={guild_id})...")

        # Already connected to this channel
        if guild_id in self.voice_clients:
            vc = self.voice_clients[guild_id]
            if vc.is_connected():
                if vc.channel.id == voice_channel.id:
                    print(f"[Audio] Already connected to '{voice_channel.name}'.")
                    return vc
                else:
                    print(f"[Audio] Moving from '{vc.channel.name}' to '{voice_channel.name}'.")
                    await vc.move_to(voice_channel)
                    return vc
            else:
                # Stale connection, clean up
                print(f"[Audio] Cleaning up stale connection for guild {guild_id}.")
                self.voice_clients.pop(guild_id, None)

        # Check bot permissions in the voice channel
        bot_member = member.guild.me
        perms = voice_channel.permissions_for(bot_member)
        if not perms.connect:
            print(f"[Audio] ✗ Bot lacks CONNECT permission in '{voice_channel.name}'!")
            return None
        if not perms.speak:
            print(f"[Audio] ✗ Bot lacks SPEAK permission in '{voice_channel.name}'!")
            return None

        try:
            vc = await voice_channel.connect()
            self.voice_clients[guild_id] = vc
            self.audio_enabled[guild_id] = True
            print(f"[Audio] ✓ Connected to '{voice_channel.name}' successfully!")
            return vc
        except Exception as e:
            print(f"[Audio] ✗ Failed to join voice channel '{voice_channel.name}': {type(e).__name__}: {e}")
            return None

    async def disconnect(self, guild_id: int):
        """Disconnect from voice in a guild."""
        vc = self.voice_clients.pop(guild_id, None)
        self.audio_enabled.pop(guild_id, None)
        if vc and vc.is_connected():
            await vc.disconnect()
            print(f"[Audio] Disconnected from voice in guild {guild_id}.")

    def set_audio_enabled(self, guild_id: int, enabled: bool):
        """Toggle audio on/off for a guild."""
        self.audio_enabled[guild_id] = enabled

    def is_audio_enabled(self, guild_id: int) -> bool:
        return self.audio_enabled.get(guild_id, True)

    async def play_sound(self, guild_id: int, audio_path: str):
        """Play an audio file in the voice channel."""
        if not self.is_audio_enabled(guild_id):
            return

        if not FFMPEG_PATH:
            return  # ffmpeg not available — silent no-op

        vc = self.voice_clients.get(guild_id)
        if not vc or not vc.is_connected():
            return

        if not os.path.exists(audio_path):
            print(f"[Audio] Sound file not found: {audio_path}")
            return

        # Stop currently playing audio
        if vc.is_playing():
            vc.stop()

        try:
            source = discord.FFmpegPCMAudio(audio_path, executable=FFMPEG_PATH)
            vc.play(source)
        except Exception as e:
            print(f"[Audio] Error playing {audio_path}: {e}")

    async def play_menu_start(self, guild_id: int):
        await self.play_sound(guild_id, AUDIO_MENU_START)

    async def play_battle_start(self, guild_id: int):
        await self.play_sound(guild_id, AUDIO_BATTLE_START)

    async def play_battle_end(self, guild_id: int):
        await self.play_sound(guild_id, AUDIO_BATTLE_END)

    async def play_monster_attack(self, guild_id: int):
        await self.play_sound(guild_id, AUDIO_MONSTER_ATTACK)

    async def play_insanity(self, guild_id: int):
        await self.play_sound(guild_id, AUDIO_INSANITY)

    async def play_card_sound(self, guild_id: int, card_id: str):
        """Play the appropriate sound for a card being played."""
        if card_id in PHYSICAL_ATTACK_CARDS:
            await self.play_sound(guild_id, AUDIO_PHYSICAL_ATTACK)
        elif card_id in MAGICAL_ATTACK_CARDS:
            await self.play_sound(guild_id, AUDIO_MAGICAL_ATTACK)
        else:
            await self.play_sound(guild_id, AUDIO_NON_ATTACK)


# Global instance
audio_manager = AudioManager()

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


class AudioManager:
    """Manages voice channel connections and audio playback per game session."""

    def __init__(self):
        # guild_id -> voice_client
        self.voice_clients: dict[int, discord.VoiceClient] = {}
        # guild_id -> bool (audio enabled)
        self.audio_enabled: dict[int, bool] = {}

    async def try_join_voice(self, member: discord.Member) -> Optional[discord.VoiceClient]:
        """Join the voice channel the member is in. Returns VoiceClient or None."""
        if not member.voice or not member.voice.channel:
            return None

        guild_id = member.guild.id
        voice_channel = member.voice.channel

        # Already connected to this channel
        if guild_id in self.voice_clients:
            vc = self.voice_clients[guild_id]
            if vc.is_connected():
                if vc.channel.id == voice_channel.id:
                    return vc
                else:
                    await vc.move_to(voice_channel)
                    return vc
            else:
                # Stale connection, clean up
                self.voice_clients.pop(guild_id, None)

        try:
            vc = await voice_channel.connect()
            self.voice_clients[guild_id] = vc
            self.audio_enabled[guild_id] = True
            return vc
        except Exception as e:
            print(f"Failed to join voice channel: {e}")
            return None

    async def disconnect(self, guild_id: int):
        """Disconnect from voice in a guild."""
        vc = self.voice_clients.pop(guild_id, None)
        self.audio_enabled.pop(guild_id, None)
        if vc and vc.is_connected():
            await vc.disconnect()

    def set_audio_enabled(self, guild_id: int, enabled: bool):
        """Toggle audio on/off for a guild."""
        self.audio_enabled[guild_id] = enabled

    def is_audio_enabled(self, guild_id: int) -> bool:
        return self.audio_enabled.get(guild_id, True)

    async def play_sound(self, guild_id: int, audio_path: str):
        """Play an audio file in the voice channel."""
        if not self.is_audio_enabled(guild_id):
            return

        vc = self.voice_clients.get(guild_id)
        if not vc or not vc.is_connected():
            return

        full_path = audio_path
        if not os.path.exists(full_path):
            return

        # Wait for any currently playing audio to finish
        if vc.is_playing():
            vc.stop()

        try:
            source = discord.FFmpegPCMAudio(full_path)
            vc.play(source)
        except Exception as e:
            print(f"Error playing audio {full_path}: {e}")

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

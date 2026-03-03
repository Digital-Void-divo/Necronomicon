"""Necronomicon Card Game - Discord Bot

Games tracked per-user. Each game is one message edited in place.
One active game per player. Audio plays in voice if user is in VC.
"""

import os
import asyncio
import time
import uuid
import io
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from models import Player, GameState
from cards import ALL_CARDS, get_cards_for_rank, CARDS_BY_ID, execute_card
from game_engine import GameEngine, TurnResult
from ai import BotAI
from image_compositor import ImageCompositor
from campaign import get_campaign_enemy, get_total_campaign_stages, CampaignEnemy
from challenge_manager import (
    get_all_challenges, get_available_challenges, get_challenge_by_id,
    apply_challenge_config_to_player, build_challenge_bot, ChallengeDefinition,
)
from persistence import (
    load_player_data, save_player_data, add_xp,
    advance_campaign, record_win, record_loss, record_draw,
    mark_challenge_completed, is_challenge_completed, get_all_player_data,
)
from config import CARD_DISPLAY_TIME, RANK_NAMES, ANNOUNCEMENT_CHANNEL_ID
from audio import audio_manager
from role_manager import assign_rank_role, setup_rank_roles, delete_rank_roles, sync_all_members
from guide import send_guide


# === Bot Setup ===

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True   # Explicit — required to see member.voice

bot = commands.Bot(command_prefix="!", intents=intents)
compositor = ImageCompositor()

# Active games: user_id (str) -> GameSession
active_games: dict[str, "GameSession"] = {}
active_lobbies: dict[int, "LobbyInfo"] = {}


class LobbyInfo:
    def __init__(self, host_id: int, host_name: str, channel_id: int):
        self.host_id = host_id
        self.host_name = host_name
        self.channel_id = channel_id


class GameSession:
    def __init__(self, game_state: GameState, engine: GameEngine,
                 channel_id: int, guild_id: int = None,
                 bot_ai: BotAI = None,
                 is_campaign: bool = False, is_multiplayer: bool = False,
                 is_challenge: bool = False, challenge_id: str = None):
        self.game_state = game_state
        self.engine = engine
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.bot_ai = bot_ai
        self.is_campaign = is_campaign
        self.is_multiplayer = is_multiplayer
        self.is_challenge = is_challenge
        self.challenge_id = challenge_id
        self.message: Optional[discord.Message] = None
        self.p1_avatar_bytes: bytes = None
        self.p2_avatar_bytes: bytes = None
        self.awaiting_blackmail: bool = False
        self.blackmail_target_id: str = None
        self.lock = asyncio.Lock()
        self.audio_active: bool = False
        # Turn timer
        self.turn_start_time: float = 0.0
        self.turn_timer_task: Optional[asyncio.Task] = None
        # Rematch metadata (populated at game start)
        self.rematch_p1_id: Optional[str] = None   # discord user id str
        self.rematch_p2_id: Optional[str] = None   # None for bot games

    @property
    def player_ids(self) -> list[str]:
        ids = []
        if not self.game_state.player1.is_bot:
            ids.append(self.game_state.player1.user_id)
        if not self.game_state.player2.is_bot:
            ids.append(self.game_state.player2.user_id)
        return ids


# === Helpers ===

def get_session_for_user(user_id: str) -> Optional[GameSession]:
    return active_games.get(user_id)

def user_in_game(user_id: str) -> bool:
    return user_id in active_games

def register_session(session: GameSession):
    for uid in session.player_ids:
        active_games[uid] = session

def unregister_session(session: GameSession):
    for uid in session.player_ids:
        active_games.pop(uid, None)


async def get_avatar_bytes(user: discord.User) -> Optional[bytes]:
    try:
        if user.avatar:
            return await user.avatar.read()
    except Exception:
        pass
    return None


async def get_bot_avatar_bytes() -> Optional[bytes]:
    """Get the bot's own avatar for use as campaign enemy portrait."""
    try:
        if bot.user and bot.user.avatar:
            return await bot.user.avatar.read()
    except Exception:
        pass
    return None


def build_player_from_user(user: discord.User, player_data: dict) -> Player:
    return Player(
        user_id=str(user.id),
        display_name=user.display_name,
        avatar_url=str(user.avatar.url) if user.avatar else "",
        rank=player_data["rank"],
        is_bot=False
    )


def build_bot_player(enemy: CampaignEnemy) -> Player:
    p = Player(
        user_id=f"bot_{enemy.name}",
        display_name=enemy.name,
        rank=enemy.rank,
        is_bot=True
    )
    p.override_starting_stats(
        life=enemy.life, sanity=enemy.sanity,
        taint=enemy.taint, arcane=enemy.arcane,
        elder_defense=enemy.elder_defense
    )
    if enemy.card_ids:
        cards = [CARDS_BY_ID[cid] for cid in enemy.card_ids if cid in CARDS_BY_ID]
        p.build_deck_from_list(cards)
    else:
        p.build_deck(get_cards_for_rank(enemy.rank))
    p.draw_initial_hand()
    return p


def render_board_file(session: GameSession, resolving_card_id: str = None,
                      resolving_player_is_bottom: bool = True,
                      book_open: bool = False) -> discord.File:
    img_bytes = compositor.render_board(
        session.game_state,
        resolving_card_id=resolving_card_id,
        resolving_player_is_bottom=resolving_player_is_bottom,
        book_open=book_open,
        p1_avatar_bytes=session.p1_avatar_bytes,
        p2_avatar_bytes=session.p2_avatar_bytes
    )
    return discord.File(io.BytesIO(img_bytes), filename="board.png")


async def update_game_message(session: GameSession, content: str,
                              file: discord.File = None,
                              view: discord.ui.View = None):
    """Edit the game message in place."""
    try:
        if session.message:
            if file:
                await session.message.edit(content=content, attachments=[file], view=view)
            else:
                await session.message.edit(content=content, view=view)
        else:
            channel = bot.get_channel(session.channel_id)
            if channel:
                kwargs = {"content": content, "view": view}
                if file:
                    kwargs["file"] = file
                session.message = await channel.send(**kwargs)
    except discord.NotFound:
        channel = bot.get_channel(session.channel_id)
        if channel:
            kwargs = {"content": content, "view": view}
            if file:
                kwargs["file"] = file
            session.message = await channel.send(**kwargs)
    except discord.HTTPException as e:
        print(f"Error updating game message: {e}")


async def try_play_audio(session: GameSession, coro):
    """Play audio if the session has an active voice connection.

    Pass a coroutine (already created by calling the async method).
    If audio is inactive the coroutine is closed immediately to suppress
    the 'coroutine was never awaited' RuntimeWarning.
    """
    import inspect
    if session.audio_active and session.guild_id:
        try:
            await coro
        except Exception as e:
            print(f"Audio error: {e}")
    else:
        # Coroutine was created by the caller but won't be awaited — close it cleanly
        if inspect.iscoroutine(coro):
            coro.close()



TURN_TIMER_SECONDS = 180  # 3 minutes


def start_turn_timer(session: "GameSession"):
    """Cancel any running timer and start a fresh one for the current player's turn."""
    cancel_turn_timer(session)
    session.turn_start_time = time.time()
    session.turn_timer_task = asyncio.create_task(_turn_timeout(session))


def cancel_turn_timer(session: "GameSession"):
    """Cancel the running timer task without forfeiting."""
    if session.turn_timer_task and not session.turn_timer_task.done():
        session.turn_timer_task.cancel()
    session.turn_timer_task = None


async def _turn_timeout(session: "GameSession"):
    """Auto-forfeit the current player after TURN_TIMER_SECONDS."""
    try:
        await asyncio.sleep(TURN_TIMER_SECONDS)
    except asyncio.CancelledError:
        return

    gs = session.game_state
    if gs.game_over:
        return

    timed_out = gs.current_player
    gs.winner = gs.get_opponent(timed_out)
    gs.game_over = True

    result = TurnResult()
    result.game_over = True
    result.messages.append(f"⏰ **{timed_out.display_name}** ran out of time (3 min limit)!")
    result.game_over_messages.append(f"🏆 **{gs.winner.display_name}** wins by timeout!")
    result.messages.extend(result.game_over_messages)

    await handle_game_over(session, result)


async def post_announcement(content: str):
    """Post a message to the configured announcement channel (fire-and-forget)."""
    if not ANNOUNCEMENT_CHANNEL_ID:
        return
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel:
        try:
            await channel.send(content)
        except Exception as e:
            print(f"[Announce] Could not post: {e}")


# === Taunt Strings ===

_TAUNTS = [
    "Is that all you've got? My grandmother summons stronger Shoggoths.",
    "The stars are right... and they're laughing at you.",
    "Ph'nglui mglw'nafh... in your face.",
    "Your Elder Defense couldn't stop a nervous cultist.",
    "Ia! Ia! Your strategy is adorable.",
    "I've seen scarier things in Dunwich, and that's saying something.",
    "You play cards like someone who's never read the Necronomicon.",
]

_CONGRATULATES = [
    "Hm. That was actually a decent move. Don't let it go to your head.",
    "Lucky draw. Enjoy it while it lasts.",
    "I'll admit, I didn't see that coming. Annoying.",
    "Not bad... for someone who still has their sanity.",
    "The Old Ones smiled on you that turn. Suspicious.",
    "Fine. You earned that one.",
    "Begrudging respect. Don't push it.",
]

_BEGS = [
    "O—okay, let's not be hasty here...",
    "I have a family! ...of cultists. But still.",
    "Please. I'll tell you where the Elder Sign is!",
    "Wait wait wait — mercy? Mercy is a thing, right?",
    "The Necronomicon says something about mercy... probably.",
    "I yield! Temporarily! For strategic reasons!",
    "You wouldn't strike down someone this close to a breakdown, would you?",
]

_GOOD_GAMES = [
    "Good game. The stars aligned for one of us today.",
    "Well played. May your sanity recover... eventually.",
    "A worthy clash. The Old Ones are satisfied.",
    "You've earned your Taint. Wear it proudly.",
    "Respects from the abyss. Good game.",
    "That was a proper summoning contest. GG.",
    "The Ancient Ones observed this battle with mild interest. GG.",
]

_INSANE_GIBBERISH = [
    "Ghlk— the COLORS they SPIRAL they SPIRAL—",
    "Ia! Ia! Fnord fhtagn blblblbl!!",
    "The walls are breathing and so am I and you ARE the wall—",
    "Ph'nglui— wait who am I— WHO ARE YOU—",
    "YyyyYYYYYYAAAAA the geometry— it's ALL WRONG—",
    "Tekeli-li tekeli-li TEKELI-LI!!",
    "I can see the strings. You're all STRINGS. Everything is STRINGS.",
    "The card! It SPOKE to me! It said things about YOU!",
]


# === Discord UI Views ===


class MainMenuView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=120)
        self.owner_id = owner_id

    async def _owner_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Open your own menu with `/play`.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Campaign", style=discord.ButtonStyle.danger, emoji="📖", row=0)
    async def campaign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_check(interaction):
            return
        # FIX: pass the menu message so the game board replaces it in-place
        await start_campaign(interaction, replace_message=interaction.message)

    @discord.ui.button(label="Challenges", style=discord.ButtonStyle.secondary, emoji="⚔️", row=0)
    async def challenge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_check(interaction):
            return
        # Challenge uses an ephemeral dropdown — delete the menu, then show selector
        menu_msg = interaction.message
        await show_challenge_select(interaction)
        try:
            await menu_msg.delete()
        except Exception:
            pass

    @discord.ui.button(label="Multiplayer", style=discord.ButtonStyle.primary, emoji="👥", row=0)
    async def multiplayer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_check(interaction):
            return
        # FIX: replace the menu message with the lobby message
        await create_multiplayer_lobby(interaction, replace_message=interaction.message)

    @discord.ui.button(label="Guide", style=discord.ButtonStyle.secondary, emoji="❓", row=0)
    async def guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_guide(interaction)  # Anyone may open the guide

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.secondary, emoji="✖️", row=0)
    async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_check(interaction):
            return
        await interaction.message.delete()
        self.stop()


class GameView(discord.ui.View):
    """Main in-game button layout.

    Row 0: Play card buttons (up to 5)
    Row 1: View Hand + Discard + Timer + Guide + Forfeit
    Row 2: Taunt buttons
    """

    def __init__(self, session: GameSession):
        super().__init__(timeout=600)
        self.session = session
        gs = session.game_state
        current = gs.current_player

        if current.is_bot:
            return

        hand_size = len(current.hand)

        # FIX: Row 0 — ALL Play card buttons together (up to 5)
        for i in range(hand_size):
            can_play, _ = current.can_play_card(i)
            self.add_item(PlayCardButton(session, i, can_play, row=0))

        # Row 1: View Hand + Discard + Timer + Guide + Forfeit
        self.add_item(ViewHandButton(session, row=1))
        self.add_item(DiscardSelectButton(session))
        self.add_item(CheckTimerButton(session))
        self.add_item(InGameGuideButton())
        self.add_item(ForfeitButton(session))

        # Row 2: Taunt buttons
        self.add_item(TauntButton(session, "taunt"))
        self.add_item(TauntButton(session, "congratulate"))
        self.add_item(TauntButton(session, "beg"))
        self.add_item(TauntButton(session, "gg"))


class ViewHandButton(discord.ui.Button):
    def __init__(self, session: GameSession, row: int = 1):
        super().__init__(label="View Hand", style=discord.ButtonStyle.secondary, emoji="👁️", row=row)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        user_id = str(interaction.user.id)

        if user_id == gs.player1.user_id:
            player = gs.player1
        elif user_id == gs.player2.user_id:
            player = gs.player2
        else:
            await interaction.response.send_message("You're not in this game!", ephemeral=True)
            return

        hand_bytes = compositor.render_hand(player)
        file = discord.File(io.BytesIO(hand_bytes), filename="hand.png")

        lines = []
        for i, card in enumerate(player.hand):
            cost_str = f"San: {card.sanity_cost}"
            if card.life_cost > 0:
                cost_str += f", Life: {card.life_cost}"
            lines.append(f"**[{i+1}]** {card.name} — {card.description} (Cost: {cost_str})")

        info = "\n".join(lines) if lines else "No cards in hand."
        info += f"\n\n**Stats:** Life: {player.life} | Sanity: {player.sanity} | Taint: {player.taint} | Arcane: {player.arcane} | Elder: {player.elder_defense}"
        if player.invulnerable:
            info += " | 🛡️ Invulnerable"
        if player.madness:
            info += f" | 🤯 {player.madness}"

        await interaction.response.send_message(info, file=file, ephemeral=True)


class PlayCardButton(discord.ui.Button):
    def __init__(self, session: GameSession, index: int, can_play: bool, row: int = 0):
        label = f"Play {index + 1}"
        style = discord.ButtonStyle.success if can_play else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, disabled=not can_play, row=row)
        self.session = session
        self.card_index = index

    async def callback(self, interaction: discord.Interaction):
        await handle_play_card(interaction, self.session, self.card_index)


class DiscardSelectButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="Discard a Card", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        user_id = str(interaction.user.id)
        if gs.current_player.user_id != user_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        view = DiscardChoiceView(self.session)
        await interaction.response.send_message("Select a card to discard:", view=view, ephemeral=True)


class InGameGuideButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Guide", style=discord.ButtonStyle.secondary, emoji="❓", row=1)

    async def callback(self, interaction: discord.Interaction):
        await send_guide(interaction)


class CheckTimerButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="⏱ Timer", style=discord.ButtonStyle.secondary, row=1)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        if self.session.turn_start_time == 0.0:
            await interaction.response.send_message("No timer running.", ephemeral=True)
            return
        elapsed = time.time() - self.session.turn_start_time
        remaining = max(0.0, TURN_TIMER_SECONDS - elapsed)
        mins, secs = divmod(int(remaining), 60)
        player_name = gs.current_player.display_name
        if remaining <= 0:
            msg = f"⏰ **{player_name}**'s time is up!"
        else:
            msg = f"⏱ **{player_name}** has **{mins}:{secs:02d}** remaining."
        await interaction.response.send_message(msg, ephemeral=True)


class ForfeitButton(discord.ui.Button):
    """In-game forfeit button with confirmation prompt."""

    def __init__(self, session: GameSession):
        super().__init__(label="Forfeit", style=discord.ButtonStyle.danger, emoji="🏳️", row=1)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        user_id = str(interaction.user.id)

        # Only players in this game may forfeit
        if user_id not in (gs.player1.user_id, gs.player2.user_id):
            await interaction.response.send_message(
                "You're not in this game!", ephemeral=True)
            return

        # Show confirmation prompt
        confirm_view = ForfeitConfirmView(self.session, interaction.user.id)
        await interaction.response.send_message(
            "⚠️ **Are you sure you want to forfeit?** This will count as a loss.",
            view=confirm_view, ephemeral=True)


class ForfeitConfirmView(discord.ui.View):
    """Ephemeral confirmation dialog for forfeit."""

    def __init__(self, session: GameSession, user_id: int):
        super().__init__(timeout=30)
        self.session = session
        self.user_id = user_id

    @discord.ui.button(label="Yes, Forfeit", style=discord.ButtonStyle.danger, emoji="🏳️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your prompt!", ephemeral=True)
            return

        session = self.session
        gs = session.game_state

        # Check if game is still active
        if gs.game_over:
            await interaction.response.send_message("This game is already over.", ephemeral=True)
            self.stop()
            return

        user_id = str(interaction.user.id)
        if user_id == gs.player1.user_id:
            gs.winner = gs.player2
        else:
            gs.winner = gs.player1
        gs.game_over = True

        forfeit_result = TurnResult()
        forfeit_result.game_over = True
        forfeit_result.messages.append(f"🏳️ **{interaction.user.display_name}** forfeits!")
        forfeit_result.game_over_messages.append(
            f"🏆 **{gs.winner.display_name}** wins by forfeit!")
        forfeit_result.messages.extend(forfeit_result.game_over_messages)

        # FIX: Acknowledge the interaction safely, then process game over
        self.disable_all_items()
        try:
            await interaction.response.edit_message(content="🏳️ Forfeiting...", view=self)
        except Exception:
            # If the ephemeral timed out, try sending a new ephemeral
            try:
                await interaction.response.send_message("🏳️ Forfeiting...", ephemeral=True)
            except Exception:
                pass  # Interaction is dead — proceed with cleanup anyway
        self.stop()

        # FIX: Always attempt game-over processing; handle_game_over has its
        # own try/finally that guarantees cleanup even on error.
        try:
            await handle_game_over(session, forfeit_result)
        except Exception as e:
            print(f"[Forfeit] Error in handle_game_over: {e}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your prompt!", ephemeral=True)
            return

        self.disable_all_items()
        await interaction.response.edit_message(content="Forfeit cancelled.", view=self)
        self.stop()


_TAUNT_CONFIG = {
    "taunt":       ("😈 Taunt",       discord.ButtonStyle.danger,     _TAUNTS),
    "congratulate":("👏 Congrats",    discord.ButtonStyle.success,    _CONGRATULATES),
    "beg":         ("🙏 Beg",         discord.ButtonStyle.secondary,  _BEGS),
    "gg":          ("🤝 Good Game",   discord.ButtonStyle.secondary,  _GOOD_GAMES),
}


class TauntButton(discord.ui.Button):
    def __init__(self, session: GameSession, taunt_type: str):
        label, style, _ = _TAUNT_CONFIG[taunt_type]
        super().__init__(label=label, style=style, row=2)
        self.session = session
        self.taunt_type = taunt_type

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        user_id = str(interaction.user.id)

        # Only players in this game may use taunts
        if user_id not in (gs.player1.user_id, gs.player2.user_id):
            await interaction.response.send_message(
                "You're not in this game!", ephemeral=True)
            return

        sender = gs.player1 if user_id == gs.player1.user_id else gs.player2
        _, _, lines = _TAUNT_CONFIG[self.taunt_type]

        if sender.is_insane:
            text = random.choice(_INSANE_GIBBERISH)
        else:
            text = random.choice(lines)

        await interaction.response.send_message(
            f"**{sender.display_name}:** *{text}*")


class DiscardChoiceView(discord.ui.View):
    def __init__(self, session: GameSession):
        super().__init__(timeout=60)
        player = session.game_state.current_player
        options = []
        for i, card in enumerate(player.hand):
            desc = f"Gain {card.sanity_cost} Sanity" if card.sanity_cost > 0 else "No Sanity gain"
            options.append(discord.SelectOption(
                label=f"[{i+1}] {card.name}", description=desc, value=str(i)))
        self.add_item(DiscardSelect(session, options))


class DiscardSelect(discord.ui.Select):
    def __init__(self, session: GameSession, options: list):
        super().__init__(placeholder="Choose a card to discard...", options=options)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        await handle_discard_card(interaction, self.session, idx)


class BlackmailChoiceView(discord.ui.View):
    def __init__(self, session: GameSession, target_player: Player):
        super().__init__(timeout=60)
        options = []
        for i, card in enumerate(target_player.hand):
            options.append(discord.SelectOption(
                label=f"[{i+1}] {card.name}", value=str(i)))
        self.add_item(BlackmailSelect(session, options))


class BlackmailSelect(discord.ui.Select):
    def __init__(self, session: GameSession, options: list):
        super().__init__(placeholder="Choose a card to discard (Blackmail)...", options=options)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        async with self.session.lock:
            idx = int(self.values[0])
            result = self.session.engine.resolve_blackmail_choice(idx)
            self.session.awaiting_blackmail = False
            self.session.blackmail_target_id = None
            await interaction.response.send_message("You discarded a card.", ephemeral=True)
            await post_turn_result(self.session, result)


class MultiplayerLobbyView(discord.ui.View):
    def __init__(self, host_id: int):
        super().__init__(timeout=300)
        self.host_id = host_id

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_id:
            await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
            return
        if user_in_game(str(interaction.user.id)):
            await interaction.response.send_message(
                "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
            return
        # FIX: pass lobby message so the game board replaces it
        await start_multiplayer_game(interaction, self.host_id,
                                     replace_message=interaction.message)


class ChallengeAcceptView(discord.ui.View):
    def __init__(self, challenger_id: int, target_id: int):
        super().__init__(timeout=120)
        self.challenger_id = challenger_id
        self.target_id = target_id

    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.success, emoji="⚔️")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        if user_in_game(str(interaction.user.id)):
            await interaction.response.send_message(
                "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
            return
        await start_multiplayer_game(interaction, self.challenger_id,
                                     replace_message=interaction.message)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**{interaction.user.display_name}** declined the challenge.")
        self.stop()



class RematchView(discord.ui.View):
    """Shown after a game ends — lets the player(s) immediately replay."""

    def __init__(self, session: GameSession):
        super().__init__(timeout=120)
        self.session = session

    @discord.ui.button(label="🔄 Rematch", style=discord.ButtonStyle.primary)
    async def rematch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        s = self.session

        # Only original participants may rematch
        valid_ids = [i for i in [s.rematch_p1_id, s.rematch_p2_id] if i]
        if uid not in valid_ids:
            await interaction.response.send_message(
                "You weren't in this game.", ephemeral=True)
            return

        if user_in_game(uid):
            await interaction.response.send_message(
                "You already have an active game!", ephemeral=True)
            return

        self.disable_all_items()
        await interaction.message.edit(view=self)

        # FIX: pass the current message so the new game overwrites it
        if s.is_campaign:
            await start_campaign(interaction, replace_message=interaction.message)
        elif s.is_challenge and s.challenge_id:
            await start_challenge(interaction, s.challenge_id,
                                  replace_message=interaction.message)
        elif s.is_multiplayer and s.rematch_p2_id:
            # For multiplayer the second human must also not be in a game
            other_id = s.rematch_p2_id if uid == s.rematch_p1_id else s.rematch_p1_id
            if user_in_game(other_id):
                await interaction.response.send_message(
                    "Your opponent is already in another game.", ephemeral=True)
                return
            # Post a rematch accept prompt — edit the current message
            view = ChallengeAcceptView(int(s.rematch_p1_id), int(s.rematch_p2_id))
            rematch_content = (
                f"🔄 **{interaction.user.display_name}** wants a rematch! "
                f"<@{other_id}> — accept?")
            try:
                await interaction.message.edit(
                    content=rematch_content, attachments=[], view=view)
            except Exception:
                if interaction.response.is_done():
                    await interaction.followup.send(rematch_content, view=view)
                else:
                    await interaction.response.send_message(
                        rematch_content, view=view)
        else:
            await start_campaign(interaction, replace_message=interaction.message)


# === Challenge Mode UI ===

class ChallengeSelectView(discord.ui.View):
    """Shows a dropdown of available challenges for the player's rank."""

    def __init__(self, player_rank: int, user_id: str):
        super().__init__(timeout=120)
        available = get_available_challenges(player_rank)
        completed = set()
        try:
            from persistence import get_completed_challenges
            completed = set(get_completed_challenges(user_id))
        except Exception:
            pass

        if not available:
            return

        options = []
        for ch in available:
            done = "✅ " if ch.id in completed else ""
            locked = ch.min_rank > player_rank
            label = f"{done}{ch.name}" + (f" [Rank {ch.min_rank}+]" if locked else "")
            options.append(discord.SelectOption(
                label=label[:100],
                description=ch.description[:100] if ch.description else "",
                value=ch.id,
            ))

        self.add_item(ChallengeSelectDropdown(options))


class ChallengeSelectDropdown(discord.ui.Select):
    def __init__(self, options: list):
        super().__init__(
            placeholder="Choose a challenge...",
            min_values=1, max_values=1,
            options=options if options else [
                discord.SelectOption(label="No challenges available", value="none")
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "No challenges available at your rank yet.", ephemeral=True)
            return
        await start_challenge(interaction, self.values[0])


# === Game Flow ===

# Set of user IDs who have explicitly disabled audio via /audio off
_audio_disabled_users: set[int] = set()


async def _resolve_member_voice(member: discord.Member) -> discord.Member:
    """Ensure the member object has up-to-date voice state.

    Button/interaction member objects can sometimes have stale or missing
    voice state if the gateway cache hasn't caught up.  Re-fetching from
    the guild guarantees we get the current voice info.
    """
    if member.voice is not None:
        return member
    # Voice state missing from cache — try a fresh fetch
    try:
        fresh = await member.guild.fetch_member(member.id)
        # fetch_member doesn't always include voice; fall back to cache lookup
        cached = member.guild.get_member(member.id)
        if cached and cached.voice:
            return cached
        return fresh
    except Exception:
        return member


async def setup_audio_for_session(session: GameSession, member: discord.Member):
    """If the member is in a voice channel and hasn't disabled audio, join and mark active."""
    if member.id in _audio_disabled_users:
        print(f"[Audio] {member.display_name} has audio disabled — skipping.")
        return

    # Make sure we have current voice state
    member = await _resolve_member_voice(member)

    if member.voice and member.voice.channel:
        vc = await audio_manager.try_join_voice(member)
        if vc:
            session.audio_active = True
            session.guild_id = member.guild.id
    else:
        print(f"[Audio] {member.display_name} is not in a voice channel — no audio for this game.")


# ─── Helper: send game board to a message (edit existing or send new) ─────────

async def _send_or_replace(interaction: discord.Interaction,
                           session: GameSession,
                           content: str,
                           replace_message: Optional[discord.Message] = None):
    """Either edit *replace_message* to show the board, or send a new followup.

    Guarantees that session.message is set to the resulting Message.
    """
    board_file = render_board_file(session)
    view = GameView(session)

    if replace_message:
        try:
            await replace_message.edit(
                content=content, attachments=[board_file], view=view)
            session.message = replace_message
            return
        except Exception as e:
            print(f"[_send_or_replace] Edit failed ({e}), falling back to new message")
            # File stream consumed — re-render
            board_file = render_board_file(session)

    msg = await interaction.followup.send(
        content=content, file=board_file, view=view, wait=True)
    session.message = msg


async def start_campaign(interaction: discord.Interaction,
                         replace_message: Optional[discord.Message] = None):
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "You already have an active game! Finish or `/forfeit` it first.",
                ephemeral=True)
        return

    user = interaction.user
    player_data = load_player_data(user_id)
    stage = player_data["campaign_stage"]
    enemy_def = get_campaign_enemy(stage)

    human = build_player_from_user(user, player_data)
    human.build_deck(get_cards_for_rank(player_data["rank"]))
    human.draw_initial_hand()

    bot_player = build_bot_player(enemy_def)

    game_state = GameState(human, bot_player)
    game_state.game_id = str(uuid.uuid4())
    engine = GameEngine(game_state)

    difficulty = BotAI.get_difficulty_for_rank(enemy_def.rank)
    bot_ai = BotAI(difficulty)

    guild_id = interaction.guild.id if interaction.guild else None
    session = GameSession(
        game_state=game_state, engine=engine,
        channel_id=interaction.channel_id, guild_id=guild_id,
        bot_ai=bot_ai, is_campaign=True
    )
    session.p1_avatar_bytes = await get_avatar_bytes(user)
    # Use the bot's own avatar for campaign enemies
    session.p2_avatar_bytes = await get_bot_avatar_bytes()
    session.rematch_p1_id = user_id
    register_session(session)

    # Try to join voice channel for audio
    if isinstance(user, discord.Member):
        await setup_audio_for_session(session, user)

    if not interaction.response.is_done():
        await interaction.response.defer()

    # Play battle start audio
    await try_play_audio(session, audio_manager.play_battle_start(guild_id))

    stage_text = f"**Campaign Stage {stage + 1}/{get_total_campaign_stages()}**"
    enemy_text = f"**VS {enemy_def.name}** (Rank {enemy_def.rank} - Life: {enemy_def.life})"
    content = f"📖 {stage_text}\n{enemy_text}"

    await _send_or_replace(interaction, session, content,
                           replace_message=replace_message)
    start_turn_timer(session)


async def show_challenge_select(interaction: discord.Interaction):
    """Show the challenge selection dropdown (ephemeral)."""
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
        return

    player_data = load_player_data(user_id)
    player_rank = player_data["rank"]
    available = get_available_challenges(player_rank)

    if not available:
        await interaction.response.send_message(
            "No challenges are available at your current rank. Keep playing to unlock them!",
            ephemeral=True)
        return

    view = ChallengeSelectView(player_rank, user_id)
    await interaction.response.send_message(
        "⚔️ **Challenge Mode** — Select a challenge to begin:", view=view, ephemeral=True)


async def start_challenge(interaction: discord.Interaction, challenge_id: str,
                          replace_message: Optional[discord.Message] = None):
    """Start a challenge game from a selection interaction."""
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "You already have an active game! Finish or `/forfeit` it first.",
                ephemeral=True)
        return

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        if not interaction.response.is_done():
            await interaction.response.send_message("Challenge not found!", ephemeral=True)
        return

    user = interaction.user
    player_data = load_player_data(user_id)

    # Build human player
    human = Player(
        user_id=user_id,
        display_name=user.display_name,
        avatar_url=str(user.avatar.url) if user.avatar else "",
        rank=player_data["rank"],
        is_bot=False,
    )
    apply_challenge_config_to_player(
        human,
        challenge.player,
        available_cards=get_cards_for_rank(player_data["rank"]),
        cards_by_id=CARDS_BY_ID,
    )

    # Build bot player
    bot_player = build_challenge_bot(challenge, CARDS_BY_ID)

    # Build game state
    game_state = GameState(human, bot_player)
    game_state.game_id = str(uuid.uuid4())
    game_state.turn_limit = challenge.player.turn_limit
    engine = GameEngine(game_state)

    difficulty = BotAI.get_difficulty_for_rank(challenge.bot.rank)
    bot_ai = BotAI(difficulty)

    guild_id = interaction.guild.id if interaction.guild else None
    session = GameSession(
        game_state=game_state, engine=engine,
        channel_id=interaction.channel_id, guild_id=guild_id,
        bot_ai=bot_ai,
        is_challenge=True, challenge_id=challenge_id,
    )
    session.p1_avatar_bytes = await get_avatar_bytes(user)
    session.p2_avatar_bytes = await get_bot_avatar_bytes()
    session.rematch_p1_id = user_id
    register_session(session)

    if isinstance(user, discord.Member):
        await setup_audio_for_session(session, user)

    if not interaction.response.is_done():
        await interaction.response.defer()

    await try_play_audio(session, audio_manager.play_battle_start(guild_id))

    turn_info = (f" | ⏳ Turn Limit: {challenge.player.turn_limit}" if challenge.player.turn_limit else "")
    actions_info = (f" | ⚡ {challenge.player.actions_per_turn} actions/turn"
                    if challenge.player.actions_per_turn > 1 else "")
    content = (f"⚔️ **Challenge: {challenge.name}**\n"
               f"*{challenge.description}*\n"
               f"VS **{challenge.bot.name}** (Rank {challenge.bot.rank})"
               f"{turn_info}{actions_info}")

    if replace_message:
        # Rematch path — overwrite the previous end-screen
        await _send_or_replace(interaction, session, content,
                               replace_message=replace_message)
    else:
        # Fresh challenge from dropdown — send to channel (not ephemeral)
        board_file = render_board_file(session)
        view = GameView(session)
        channel = bot.get_channel(interaction.channel_id)
        if channel:
            msg = await channel.send(content=content, file=board_file, view=view)
            session.message = msg

    start_turn_timer(session)


async def create_multiplayer_lobby(interaction: discord.Interaction,
                                   replace_message: Optional[discord.Message] = None):
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "You already have an active game! Finish or `/forfeit` it first.",
                ephemeral=True)
        return
    for lobby in active_lobbies.values():
        if lobby.host_id == interaction.user.id:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You already have an open lobby!", ephemeral=True)
            return

    lobby = LobbyInfo(interaction.user.id, interaction.user.display_name, interaction.channel_id)
    active_lobbies[interaction.user.id] = lobby
    view = MultiplayerLobbyView(interaction.user.id)
    lobby_content = (
        f"⚔️ **{interaction.user.display_name}** is looking for a challenger!\n"
        f"Click **Join Game** to accept.")

    if replace_message:
        # Edit the menu message to become the lobby
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
            await replace_message.edit(
                content=lobby_content, attachments=[], view=view)
        except Exception:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    lobby_content, view=view)
            else:
                await interaction.followup.send(lobby_content, view=view)
    else:
        await interaction.response.send_message(lobby_content, view=view)


async def start_multiplayer_game(interaction: discord.Interaction, host_id: int,
                                 replace_message: Optional[discord.Message] = None):
    active_lobbies.pop(host_id, None)

    host = await bot.fetch_user(host_id)
    challenger = interaction.user

    host_data = load_player_data(str(host.id))
    challenger_data = load_player_data(str(challenger.id))

    p1 = build_player_from_user(host, host_data)
    p1.build_deck(get_cards_for_rank(host_data["rank"]))
    p1.draw_initial_hand()

    p2 = build_player_from_user(challenger, challenger_data)
    p2.build_deck(get_cards_for_rank(challenger_data["rank"]))
    p2.draw_initial_hand()

    game_state = GameState(p1, p2)
    game_state.game_id = str(uuid.uuid4())
    engine = GameEngine(game_state)

    guild_id = interaction.guild.id if interaction.guild else None
    session = GameSession(
        game_state=game_state, engine=engine,
        channel_id=interaction.channel_id, guild_id=guild_id,
        is_multiplayer=True
    )
    session.p1_avatar_bytes = await get_avatar_bytes(host)
    session.p2_avatar_bytes = await get_avatar_bytes(challenger)
    session.rematch_p1_id = str(host.id)
    session.rematch_p2_id = str(challenger.id)
    register_session(session)

    # Try to join voice
    if isinstance(interaction.user, discord.Member):
        await setup_audio_for_session(session, interaction.user)

    if not interaction.response.is_done():
        await interaction.response.defer()

    await try_play_audio(session, audio_manager.play_battle_start(guild_id))

    content = f"⚔️ **{host.display_name}** vs **{challenger.display_name}**"
    await _send_or_replace(interaction, session, content,
                           replace_message=replace_message)
    start_turn_timer(session)


async def handle_play_card(interaction: discord.Interaction, session: GameSession, card_index: int):
    gs = session.game_state
    user_id = str(interaction.user.id)

    if gs.current_player.user_id != user_id:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return
    if session.awaiting_blackmail:
        await interaction.response.send_message("Waiting for opponent to resolve Blackmail!", ephemeral=True)
        return

    async with session.lock:
        if card_index >= len(gs.current_player.hand):
            await interaction.response.send_message("Invalid card!", ephemeral=True)
            return

        card = gs.current_player.hand[card_index]
        is_bottom = (gs.current_player == gs.player1)

        await interaction.response.defer()

        # Play card sound
        await try_play_audio(session,
            audio_manager.play_card_sound(session.guild_id, card.card_id))

        # Phase 1: Show card resolving
        resolving_file = render_board_file(
            session, resolving_card_id=card.card_id,
            resolving_player_is_bottom=is_bottom, book_open=True
        )
        await update_game_message(
            session,
            f"📜 **{gs.current_player.display_name}** plays **{card.name}**...",
            file=resolving_file, view=None
        )
        await asyncio.sleep(CARD_DISPLAY_TIME)

        # Phase 2: Execute
        result = session.engine.play_card(card_index)

        if not result.card_played and not result.messages:
            board_file = render_board_file(session)
            view = GameView(session)
            await update_game_message(session, "Invalid card!", file=board_file, view=view)
            return

        # Check if anyone went insane
        await _check_insanity_audio(session, result)

        # Check for monster combat audio
        if result.monster_combat_occurred:
            await try_play_audio(session,
                audio_manager.play_monster_attack(session.guild_id))

        # Handle blackmail
        if result.requires_blackmail_choice:
            session.awaiting_blackmail = True
            opponent = gs.get_opponent(gs.current_player)
            session.blackmail_target_id = opponent.user_id

            if opponent.is_bot:
                idx = session.bot_ai.choose_blackmail_discard(opponent)
                bm_result = session.engine.resolve_blackmail_choice(idx)
                session.awaiting_blackmail = False
                result.messages.extend(bm_result.messages)
                result.game_over = bm_result.game_over
                result.game_over_messages.extend(bm_result.game_over_messages)
            else:
                log_text = "\n".join(result.messages[-8:])
                board_file = render_board_file(session)
                await update_game_message(
                    session,
                    f"📜 {log_text}\n\n⏳ Waiting for {opponent.display_name} to discard...",
                    file=board_file, view=None
                )
                channel = bot.get_channel(session.channel_id)
                if channel:
                    bm_view = BlackmailChoiceView(session, opponent)
                    await channel.send(
                        f"<@{opponent.user_id}> — You've been Blackmailed! Choose a card to discard:",
                        view=bm_view)
                return

        await post_turn_result(session, result)


async def handle_discard_card(interaction: discord.Interaction, session: GameSession, card_index: int):
    gs = session.game_state
    user_id = str(interaction.user.id)
    if gs.current_player.user_id != user_id:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return

    async with session.lock:
        result = session.engine.discard_card(card_index)
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass
        await post_turn_result(session, result)


async def post_turn_result(session: GameSession, result: TurnResult):
    gs = session.game_state
    log_text = "\n".join(result.messages[-10:])

    if result.game_over:
        cancel_turn_timer(session)
        await handle_game_over(session, result)
        return

    if gs.current_player.is_bot and session.bot_ai:
        cancel_turn_timer(session)  # Bot turns don't need a timer
        board_file = render_board_file(session)
        await update_game_message(
            session,
            f"📜 {log_text}",
            file=board_file, view=None
        )
        await asyncio.sleep(2)
        await handle_bot_turn(session)
    else:
        start_turn_timer(session)  # Fresh 3-minute clock for the human
        board_file = render_board_file(session)
        view = GameView(session)
        await update_game_message(
            session,
            f"📜 {log_text}",
            file=board_file, view=view
        )


async def handle_bot_turn(session: GameSession):
    gs = session.game_state
    bot_player = gs.current_player
    bot_ai = session.bot_ai

    if not bot_player.is_bot or not bot_ai:
        return

    action, index = bot_ai.choose_action(gs)

    if action == "play" and index < len(bot_player.hand):
        card = bot_player.hand[index]
        is_bottom = (bot_player == gs.player1)

        # Play card sound
        await try_play_audio(session,
            audio_manager.play_card_sound(session.guild_id, card.card_id))

        # Phase 1: Show bot's card
        resolving_file = render_board_file(
            session, resolving_card_id=card.card_id,
            resolving_player_is_bottom=is_bottom, book_open=True
        )
        await update_game_message(
            session,
            f"🤖 **{bot_player.display_name}** plays **{card.name}**...",
            file=resolving_file, view=None
        )
        await asyncio.sleep(CARD_DISPLAY_TIME)

        # Phase 2: Execute
        result = session.engine.play_card(index)

        await _check_insanity_audio(session, result)

        if result.monster_combat_occurred:
            await try_play_audio(session,
                audio_manager.play_monster_attack(session.guild_id))

        # Handle blackmail targeting human
        if result.requires_blackmail_choice:
            opponent = gs.get_opponent(bot_player)
            if not opponent.is_bot:
                session.awaiting_blackmail = True
                session.blackmail_target_id = opponent.user_id
                log_text = "\n".join(result.messages[-8:])
                board_file = render_board_file(session)
                await update_game_message(
                    session,
                    f"📜 {log_text}\n\n⏳ Waiting for {opponent.display_name} to discard...",
                    file=board_file, view=None
                )
                channel = bot.get_channel(session.channel_id)
                if channel:
                    bm_view = BlackmailChoiceView(session, opponent)
                    await channel.send(
                        f"<@{opponent.user_id}> — You've been Blackmailed! Choose a card to discard:",
                        view=bm_view)
                return
    else:
        safe_index = min(index, len(bot_player.hand) - 1) if bot_player.hand else 0
        result = session.engine.discard_card(safe_index)

    await post_turn_result(session, result)


async def _check_insanity_audio(session: GameSession, result: TurnResult):
    """Play insanity sound if any message mentions madness onset."""
    for msg in result.messages:
        if "Madness:" in msg or "Xenophobia" in msg or "Agoraphobia" in msg or \
           "Megalomania" in msg or "Schizophrenia" in msg:
            await try_play_audio(session,
                audio_manager.play_insanity(session.guild_id))
            break


async def handle_game_over(session: GameSession, result: TurnResult):
    """Process end-of-game: show results, award XP, clean up.

    Uses try/finally to guarantee session cleanup and voice disconnect
    even if an error occurs during rendering or persistence.
    """
    gs = session.game_state
    log_text = "\n".join(result.messages)

    # Cancel the turn timer — game is over
    cancel_turn_timer(session)

    try:
        # Play battle end audio
        await try_play_audio(session,
            audio_manager.play_battle_end(session.guild_id))

        rematch_view = RematchView(session)

        if gs.is_draw:
            board_file = render_board_file(session)
            await update_game_message(
                session, f"📜 {log_text}\n\n🤝 **DRAW!**",
                file=board_file, view=rematch_view
            )
            for p in [gs.player1, gs.player2]:
                if not p.is_bot:
                    record_draw(p.user_id)
            return

        winner = gs.winner
        loser = gs.player1 if winner == gs.player2 else gs.player2

        if not winner.is_bot:
            xp_data = session.engine.calculate_xp(winner)
            rank_data = add_xp(winner.user_id, xp_data["total"])
            record_win(winner.user_id)

            if session.is_campaign:
                advance_campaign(winner.user_id)

            if session.is_challenge and session.challenge_id:
                mark_challenge_completed(winner.user_id, session.challenge_id)

            # Assign rank role
            if session.guild_id:
                guild = bot.get_guild(session.guild_id)
                if guild:
                    try:
                        member = await guild.fetch_member(int(winner.user_id))
                        await assign_rank_role(member, rank_data["new_rank"])
                    except Exception as e:
                        print(f"[RoleManager] Could not assign role to {winner.user_id}: {e}")

            end_bytes = compositor.render_end_screen(winner, xp_data, rank_data)
            end_file = discord.File(io.BytesIO(end_bytes), filename="results.png")

            content = f"📜 {log_text}\n\n🏆 **{winner.display_name}** is victorious!"
            if rank_data["ranked_up"]:
                new_rank_name = rank_data["new_rank_name"]
                new_rank_num  = rank_data["new_rank"]
                content += f"\n🎉 Ranked up to **Rank {new_rank_num} — {new_rank_name}**!"
                await post_announcement(
                    f"🎉 <@{winner.user_id}> has ranked up to **Rank {new_rank_num} — {new_rank_name}**!"
                )

            await update_game_message(session, content, file=end_file, view=rematch_view)

        else:
            # Winner is bot — human loser
            if not loser.is_bot:
                xp_data = session.engine.calculate_xp(loser)
                xp_data["total"] = 0
                loser_player_data = load_player_data(loser.user_id)
                rank_data = {
                    "old_rank": loser_player_data["rank"],
                    "new_rank": loser_player_data["rank"],
                    "ranked_up": False,
                    "old_rank_name": RANK_NAMES.get(loser_player_data["rank"], ""),
                    "new_rank_name": RANK_NAMES.get(loser_player_data["rank"], ""),
                    "total_xp": loser_player_data["xp"],
                }
                end_bytes = compositor.render_end_screen(loser, xp_data, rank_data, is_loss=True)
                end_file = discord.File(io.BytesIO(end_bytes), filename="results.png")
                await update_game_message(
                    session,
                    f"📜 {log_text}\n\n💀 **{winner.display_name}** wins! Better luck next time!",
                    file=end_file, view=rematch_view
                )
            else:
                board_file = render_board_file(session)
                await update_game_message(
                    session,
                    f"📜 {log_text}\n\n💀 **{winner.display_name}** wins!",
                    file=board_file, view=rematch_view
                )

        if not loser.is_bot:
            record_loss(loser.user_id)

    except Exception as e:
        print(f"[handle_game_over] Error during game-over processing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # FIX: ALWAYS clean up the session and disconnect voice, even on error
        unregister_session(session)
        if session.audio_active and session.guild_id:
            try:
                await asyncio.sleep(3)
                await audio_manager.disconnect(session.guild_id)
            except Exception as e:
                print(f"[handle_game_over] Error disconnecting audio: {e}")


# === Slash Commands ===

@bot.tree.command(name="play", description="Open the Necronomicon - start a game!")
async def play_command(interaction: discord.Interaction):
    if user_in_game(str(interaction.user.id)):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
        return

    # Play menu audio if in voice
    if interaction.guild and isinstance(interaction.user, discord.Member):
        member = await _resolve_member_voice(interaction.user)
        if member.voice and member.voice.channel:
            vc = await audio_manager.try_join_voice(member)
            if vc:
                await audio_manager.play_menu_start(interaction.guild.id)

    menu_bytes = compositor.render_menu()
    menu_file = discord.File(io.BytesIO(menu_bytes), filename="menu.png")
    view = MainMenuView(owner_id=interaction.user.id)
    await interaction.response.send_message(file=menu_file, view=view)


@bot.tree.command(name="campaign", description="Start your next campaign battle")
async def campaign_command(interaction: discord.Interaction):
    await start_campaign(interaction)


@bot.tree.command(name="challenges", description="Browse and start challenge mode scenarios")
async def challenges_command(interaction: discord.Interaction):
    await show_challenge_select(interaction)


@bot.tree.command(name="guide", description="Open the Necronomicon guide")
@app_commands.describe(page="Page to open (1–13, default 1)")
async def guide_command(interaction: discord.Interaction, page: int = 1):
    page_index = max(0, min(page - 1, 12))  # clamp to valid range
    await send_guide(interaction, page=page_index)


@bot.tree.command(name="challenge", description="Challenge another player")
@app_commands.describe(opponent="The player to challenge")
async def challenge_command(interaction: discord.Interaction, opponent: discord.Member):
    user_id = str(interaction.user.id)
    target_id = str(opponent.id)

    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("Use /campaign to fight bots!", ephemeral=True)
        return
    if user_in_game(user_id):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
        return
    if user_in_game(target_id):
        await interaction.response.send_message(
            f"{opponent.display_name} is already in a game!", ephemeral=True)
        return

    view = ChallengeAcceptView(interaction.user.id, opponent.id)
    await interaction.response.send_message(
        f"⚔️ **{interaction.user.display_name}** challenges **{opponent.display_name}**!",
        view=view)


@bot.tree.command(name="stats", description="View your player stats and rank")
async def stats_command(interaction: discord.Interaction):
    data = load_player_data(str(interaction.user.id))
    rank = data["rank"]
    rank_name = RANK_NAMES.get(rank, f"Rank {rank}")

    embed = discord.Embed(
        title=f"📊 {interaction.user.display_name}'s Stats",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="Rank", value=f"{rank} - {rank_name}", inline=True)
    embed.add_field(name="Total XP", value=str(data["xp"]), inline=True)
    embed.add_field(name="Campaign Stage", value=str(data["campaign_stage"] + 1), inline=True)
    embed.add_field(name="Wins", value=str(data["wins"]), inline=True)
    embed.add_field(name="Losses", value=str(data["losses"]), inline=True)
    embed.add_field(name="Draws", value=str(data["draws"]), inline=True)
    unlocked = len(get_cards_for_rank(rank))
    total = len(ALL_CARDS)
    embed.add_field(name="Cards Unlocked", value=f"{unlocked}/{total}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="forfeit", description="Forfeit the current game")
async def forfeit_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if not user_in_game(user_id):
        await interaction.response.send_message("You don't have an active game!", ephemeral=True)
        return

    session = get_session_for_user(user_id)

    # Show confirmation before forfeiting
    confirm_view = ForfeitConfirmView(session, interaction.user.id)
    await interaction.response.send_message(
        "⚠️ **Are you sure you want to forfeit?** This will count as a loss.",
        view=confirm_view, ephemeral=True)


@bot.tree.command(name="cardlist", description="View all available cards")
async def cardlist_command(interaction: discord.Interaction):
    data = load_player_data(str(interaction.user.id))
    rank = data["rank"]

    lines = []
    for card in ALL_CARDS:
        unlocked = "✅" if card.rank_required <= rank else f"🔒 Rank {card.rank_required}"
        cost = f"San: {card.sanity_cost}"
        lines.append(f"{unlocked} **{card.name}** — {card.description} ({cost})")

    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)

    await interaction.response.send_message(chunks[0], ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)


@bot.tree.command(name="leaderboard", description="View the top Necronomicon players by XP")
@app_commands.describe(top="How many entries to show (default 10, max 25)")
async def leaderboard_command(interaction: discord.Interaction, top: int = 10):
    top = max(1, min(top, 25))
    all_data = get_all_player_data()

    # Sort by XP descending
    ranked = sorted(all_data, key=lambda d: d["xp"], reverse=True)[:top]

    if not ranked:
        await interaction.response.send_message("No player data yet!", ephemeral=True)
        return

    embed = discord.Embed(
        title="📖 Necronomicon Leaderboard",
        colour=discord.Colour.from_rgb(160, 30, 30),
    )

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, data in enumerate(ranked, 1):
        medal = medals.get(i, f"**{i}.**")
        rank_name = RANK_NAMES.get(data["rank"], f"Rank {data['rank']}")
        lines.append(
            f"{medal} <@{data['user_id']}> — "
            f"Rank {data['rank']} ({rank_name}) · {data['xp']:,} XP · "
            f"{data['wins']}W/{data['losses']}L"
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Showing top {len(ranked)} players")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="audio", description="Toggle voice-channel audio on or off for your next game")
@app_commands.describe(setting="on or off")
@app_commands.choices(setting=[
    app_commands.Choice(name="on",  value="on"),
    app_commands.Choice(name="off", value="off"),
])
async def audio_command(interaction: discord.Interaction, setting: str):
    uid = interaction.user.id
    if setting == "off":
        _audio_disabled_users.add(uid)
        await interaction.response.send_message(
            "🔇 Audio disabled — your next game will be silent.", ephemeral=True)
    else:
        _audio_disabled_users.discard(uid)
        await interaction.response.send_message(
            "🔊 Audio enabled — the Old Ones will be heard.", ephemeral=True)



# === Role Management Commands ===

@bot.tree.command(name="setup_roles", description="[Admin] Create all Necronomicon rank roles in this server")
@app_commands.default_permissions(manage_roles=True)
async def setup_roles_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    created, skipped = await setup_rank_roles(interaction.guild)

    lines = []
    if created:
        lines.append(f"✅ **Created ({len(created)}):** " + ", ".join(created))
    if skipped:
        lines.append(f"⏭️ **Already existed / skipped ({len(skipped)}):** " + ", ".join(skipped))
    if not created and not skipped:
        lines.append("Nothing to do — no rank roles are defined.")

    lines.append(
        "\n**Next step:** In Server Settings → Roles, drag the bot's role **above** "
        "all the Necronomicon rank roles so it can assign them."
    )

    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="reset_roles", description="[Admin] Delete all Necronomicon rank roles and recreate them")
@app_commands.default_permissions(manage_roles=True)
async def reset_roles_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    deleted, failed_del = await delete_rank_roles(interaction.guild)
    created, skipped = await setup_rank_roles(interaction.guild)

    lines = [f"🗑️ Deleted {len(deleted)} old role(s)."]
    if failed_del:
        lines.append(f"⚠️ Could not delete: " + ", ".join(failed_del))
    lines.append(f"✅ Created {len(created)} role(s).")
    if skipped:
        lines.append(f"⏭️ Skipped: " + ", ".join(skipped))

    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="sync_role", description="Fix your Necronomicon rank role if it looks wrong")
async def sync_role_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    data = load_player_data(user_id)
    rank = data.get("rank", 1)

    await interaction.response.defer(ephemeral=True)
    try:
        member = await interaction.guild.fetch_member(interaction.user.id)
        success, msg = await assign_rank_role(member, rank)
        rank_name = RANK_NAMES.get(rank, f"Rank {rank}")
        if success:
            await interaction.followup.send(
                f"✅ Role synced — you are **Rank {rank}: {rank_name}**.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Could not sync role: {msg}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error syncing role: {e}", ephemeral=True)


@bot.tree.command(name="sync_all_roles", description="[Admin] Sync Necronomicon rank roles for every server member")
@app_commands.default_permissions(manage_roles=True)
async def sync_all_roles_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    result = await sync_all_members(interaction.guild, load_player_data)

    await interaction.followup.send(
        f"✅ Role sync complete for **{result['total']}** members:\n"
        f"  • Updated: **{result['updated']}**\n"
        f"  • Already correct: **{result['already_correct']}**\n"
        f"  • No game data: **{result['no_data']}**\n"
        f"  • Failed: **{result['failed']}**",
        ephemeral=True
    )


# === Bot Events ===

@bot.event
async def on_ready():
    print(f"🎮 Necronomicon bot is online as {bot.user}")
    print(f"[Bot] Intents: voice_states={bot.intents.voice_states}, "
          f"members={bot.intents.members}, "
          f"message_content={bot.intents.message_content}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# === Entry Point ===

def main():
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("DISCORD_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip('"\'').strip()
                        break

    if not token:
        print("ERROR: DISCORD_TOKEN not found!")
        print("Set it as an environment variable or create a .env file with:")
        print('DISCORD_TOKEN=your_token_here')
        return

    # Debug: show token info (remove after confirmed working)
    print(f"[DEBUG] Token length: {len(token)}")
    print(f"[DEBUG] Token starts with: {token[:5]}...")
    print(f"[DEBUG] Token ends with: ...{token[-5:]}")
    has_quotes = token.startswith('"') or token.startswith("'")
    print(f"[DEBUG] Token has quotes: {has_quotes}")
    print(f"[DEBUG] Source: {'env var' if os.environ.get('DISCORD_TOKEN') else '.env file'}")

    bot.run(token)


if __name__ == "__main__":
    main()

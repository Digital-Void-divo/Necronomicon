"""Necronomicon Card Game - Discord Bot

Games tracked per-user. Each game is one message edited in place.
One active game per player. Audio plays in voice if user is in VC.
"""

import os
import asyncio
import uuid
import io
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
from persistence import (
    load_player_data, save_player_data, add_xp,
    advance_campaign, record_win, record_loss, record_draw
)
from config import CARD_DISPLAY_TIME, RANK_NAMES
from audio import audio_manager


# === Bot Setup ===

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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
                 is_campaign: bool = False, is_multiplayer: bool = False):
        self.game_state = game_state
        self.engine = engine
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.bot_ai = bot_ai
        self.is_campaign = is_campaign
        self.is_multiplayer = is_multiplayer
        self.message: Optional[discord.Message] = None
        self.p1_avatar_bytes: bytes = None
        self.p2_avatar_bytes: bytes = None
        self.awaiting_blackmail: bool = False
        self.blackmail_target_id: str = None
        self.lock = asyncio.Lock()
        self.audio_active: bool = False  # True if bot joined VC for this session

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
    """Play audio if the session has an active voice connection."""
    if session.audio_active and session.guild_id:
        try:
            await coro
        except Exception as e:
            print(f"Audio error: {e}")


# === Discord UI Views ===

class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Campaign", style=discord.ButtonStyle.danger, emoji="📖", row=0)
    async def campaign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_campaign(interaction)

    @discord.ui.button(label="Challenge Mode", style=discord.ButtonStyle.secondary, emoji="⚔️", row=0)
    async def challenge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Challenge Mode coming soon!", ephemeral=True)

    @discord.ui.button(label="Multiplayer", style=discord.ButtonStyle.primary, emoji="👥", row=1)
    async def multiplayer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_multiplayer_lobby(interaction)

    @discord.ui.button(label="How to Play", style=discord.ButtonStyle.secondary, emoji="❓", row=1)
    async def howtoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**How to Play** instructions will be defined later.", ephemeral=True)


class GameView(discord.ui.View):
    def __init__(self, session: GameSession):
        super().__init__(timeout=600)
        self.session = session
        gs = session.game_state
        current = gs.current_player

        if current.is_bot:
            return

        self.add_item(ViewHandButton(session))

        for i in range(len(current.hand)):
            can_play, _ = current.can_play_card(i)
            self.add_item(PlayCardButton(session, i, can_play))

        self.add_item(DiscardSelectButton(session))


class ViewHandButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="View Hand", style=discord.ButtonStyle.secondary, emoji="👁️", row=0)
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
    def __init__(self, session: GameSession, index: int, can_play: bool):
        label = f"Play [{index + 1}]"
        style = discord.ButtonStyle.success if can_play else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, disabled=not can_play, row=1 + index // 5)
        self.session = session
        self.card_index = index

    async def callback(self, interaction: discord.Interaction):
        await handle_play_card(interaction, self.session, self.card_index)


class DiscardSelectButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="Discard a Card", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        user_id = str(interaction.user.id)
        if gs.current_player.user_id != user_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        view = DiscardChoiceView(self.session)
        await interaction.response.send_message("Select a card to discard:", view=view, ephemeral=True)


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
        await start_multiplayer_game(interaction, self.host_id)


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
        await start_multiplayer_game(interaction, self.challenger_id)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**{interaction.user.display_name}** declined the challenge.")
        self.stop()


# === Game Flow ===

async def setup_audio_for_session(session: GameSession, member: discord.Member):
    """If the member is in a voice channel, join it and mark audio as active."""
    if member.voice and member.voice.channel:
        vc = await audio_manager.try_join_voice(member)
        if vc:
            session.audio_active = True
            session.guild_id = member.guild.id


async def start_campaign(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
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
    register_session(session)

    # Try to join voice channel for audio
    if isinstance(user, discord.Member):
        await setup_audio_for_session(session, user)

    await interaction.response.defer()

    # Play battle start audio
    await try_play_audio(session, audio_manager.play_battle_start(guild_id))

    board_file = render_board_file(session)
    view = GameView(session)

    stage_text = f"**Campaign Stage {stage + 1}/{get_total_campaign_stages()}**"
    enemy_text = f"**VS {enemy_def.name}** (Rank {enemy_def.rank} - Life: {enemy_def.life})"
    content = f"📖 {stage_text}\n{enemy_text}"

    msg = await interaction.followup.send(content=content, file=board_file, view=view, wait=True)
    session.message = msg


async def create_multiplayer_lobby(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_in_game(user_id):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
        return
    for lobby in active_lobbies.values():
        if lobby.host_id == interaction.user.id:
            await interaction.response.send_message("You already have an open lobby!", ephemeral=True)
            return

    lobby = LobbyInfo(interaction.user.id, interaction.user.display_name, interaction.channel_id)
    active_lobbies[interaction.user.id] = lobby
    view = MultiplayerLobbyView(interaction.user.id)
    await interaction.response.send_message(
        f"⚔️ **{interaction.user.display_name}** is looking for a challenger!\nClick **Join Game** to accept.",
        view=view)


async def start_multiplayer_game(interaction: discord.Interaction, host_id: int):
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
    register_session(session)

    # Try to join voice
    if isinstance(interaction.user, discord.Member):
        await setup_audio_for_session(session, interaction.user)

    await interaction.response.defer()
    await try_play_audio(session, audio_manager.play_battle_start(guild_id))

    board_file = render_board_file(session)
    view = GameView(session)

    content = f"⚔️ **{host.display_name}** vs **{challenger.display_name}**"
    msg = await interaction.followup.send(content=content, file=board_file, view=view, wait=True)
    session.message = msg


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
        await handle_game_over(session, result)
        return

    if gs.current_player.is_bot and session.bot_ai:
        board_file = render_board_file(session)
        await update_game_message(
            session,
            f"📜 {log_text}",
            file=board_file, view=None
        )
        await asyncio.sleep(2)
        await handle_bot_turn(session)
    else:
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
    gs = session.game_state
    log_text = "\n".join(result.messages)

    # Play battle end audio
    await try_play_audio(session,
        audio_manager.play_battle_end(session.guild_id))

    if gs.is_draw:
        board_file = render_board_file(session)
        await update_game_message(
            session, f"📜 {log_text}\n\n🤝 **DRAW!**",
            file=board_file, view=None
        )
        for p in [gs.player1, gs.player2]:
            if not p.is_bot:
                record_draw(p.user_id)
        unregister_session(session)

        # Disconnect from voice after a delay
        if session.audio_active and session.guild_id:
            await asyncio.sleep(5)
            await audio_manager.disconnect(session.guild_id)
        return

    winner = gs.winner
    loser = gs.player1 if winner == gs.player2 else gs.player2

    if not winner.is_bot:
        xp_data = session.engine.calculate_xp(winner)
        rank_data = add_xp(winner.user_id, xp_data["total"])
        record_win(winner.user_id)

        if session.is_campaign:
            advance_campaign(winner.user_id)

        end_bytes = compositor.render_end_screen(winner, xp_data, rank_data)
        end_file = discord.File(io.BytesIO(end_bytes), filename="results.png")

        content = f"📜 {log_text}\n\n🏆 **{winner.display_name}** is victorious!"
        if rank_data["ranked_up"]:
            content += f"\n🎉 Ranked up to **{rank_data['new_rank']}- {rank_data['new_rank_name']}**!"

        await update_game_message(session, content, file=end_file, view=None)
    else:
        # Winner is bot — show loss end screen to human loser
        if not loser.is_bot:
            # Build a loss end screen with 0 XP
            xp_data = session.engine.calculate_xp(loser)
            xp_data["total"] = 0  # No XP for losing
            loser_player_data = load_player_data(loser.user_id)
            rank_data = {
                "old_rank": loser_player_data["rank"],
                "new_rank": loser_player_data["rank"],
                "ranked_up": False,
                "old_rank_name": RANK_NAMES.get(loser_player_data["rank"], ""),
                "new_rank_name": RANK_NAMES.get(loser_player_data["rank"], ""),
                "total_xp": loser_player_data["xp"],
            }
            end_bytes = compositor.render_end_screen(
                loser, xp_data, rank_data, is_loss=True)
            end_file = discord.File(io.BytesIO(end_bytes), filename="results.png")
            await update_game_message(
                session,
                f"📜 {log_text}\n\n💀 **{winner.display_name}** wins! Better luck next time!",
                file=end_file, view=None
            )
        else:
            board_file = render_board_file(session)
            await update_game_message(
                session,
                f"📜 {log_text}\n\n💀 **{winner.display_name}** wins!",
                file=board_file, view=None
            )

    if not loser.is_bot:
        record_loss(loser.user_id)

    unregister_session(session)

    # Disconnect from voice after a delay
    if session.audio_active and session.guild_id:
        await asyncio.sleep(5)
        await audio_manager.disconnect(session.guild_id)


# === Slash Commands ===

@bot.tree.command(name="play", description="Open the Necronomicon - start a game!")
async def play_command(interaction: discord.Interaction):
    if user_in_game(str(interaction.user.id)):
        await interaction.response.send_message(
            "You already have an active game! Finish or `/forfeit` it first.", ephemeral=True)
        return

    # Play menu audio if in voice
    if interaction.guild and isinstance(interaction.user, discord.Member):
        if interaction.user.voice and interaction.user.voice.channel:
            vc = await audio_manager.try_join_voice(interaction.user)
            if vc:
                await audio_manager.play_menu_start(interaction.guild.id)

    menu_bytes = compositor.render_menu()
    menu_file = discord.File(io.BytesIO(menu_bytes), filename="menu.png")
    view = MainMenuView()
    await interaction.response.send_message(file=menu_file, view=view)


@bot.tree.command(name="campaign", description="Start your next campaign battle")
async def campaign_command(interaction: discord.Interaction):
    await start_campaign(interaction)


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
    gs = session.game_state

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

    await interaction.response.defer()

    # Directly handle game over — skip post_turn_result to avoid "thinking" state
    await handle_game_over(session, forfeit_result)


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


# === Bot Events ===

@bot.event
async def on_ready():
    print(f"🎮 Necronomicon bot is online as {bot.user}")
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

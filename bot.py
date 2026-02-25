"""Necronomicon Card Game - Discord Bot

Main entry point. Handles slash commands, button interactions,
game session management, and ties everything together.
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


# === Bot Setup ===

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
compositor = ImageCompositor()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Active games: channel_id -> GameSession
active_games: dict[int, "GameSession"] = {}

# Multiplayer lobbies: channel_id -> LobbyInfo
active_lobbies: dict[int, "LobbyInfo"] = {}


class LobbyInfo:
    def __init__(self, host_id: int, host_name: str, channel_id: int, message: discord.Message = None):
        self.host_id = host_id
        self.host_name = host_name
        self.channel_id = channel_id
        self.message = message


class GameSession:
    """Tracks a game session in a Discord channel."""

    def __init__(self, game_state: GameState, engine: GameEngine,
                 channel_id: int, bot_ai: BotAI = None,
                 is_campaign: bool = False, is_multiplayer: bool = False):
        self.game_state = game_state
        self.engine = engine
        self.channel_id = channel_id
        self.bot_ai = bot_ai
        self.is_campaign = is_campaign
        self.is_multiplayer = is_multiplayer
        self.message: Optional[discord.Message] = None  # The board message we update
        self.p1_avatar_bytes: bytes = None
        self.p2_avatar_bytes: bytes = None
        self.awaiting_blackmail: bool = False
        self.blackmail_target_id: str = None


# === Helper Functions ===

async def get_avatar_bytes(user: discord.User) -> bytes:
    """Download a user's avatar as bytes."""
    try:
        if user.avatar:
            return await user.avatar.read()
    except Exception:
        pass
    return None


def build_player_from_user(user: discord.User, player_data: dict) -> Player:
    """Create a Player instance from a Discord user and saved data."""
    return Player(
        user_id=str(user.id),
        display_name=user.display_name,
        avatar_url=str(user.avatar.url) if user.avatar else "",
        rank=player_data["rank"],
        is_bot=False
    )


def build_bot_player(enemy: CampaignEnemy) -> Player:
    """Create a bot Player from a campaign enemy definition."""
    p = Player(
        user_id=f"bot_{enemy.name}",
        display_name=enemy.name,
        rank=enemy.rank,
        is_bot=True
    )
    p.override_starting_stats(
        life=enemy.life,
        sanity=enemy.sanity,
        taint=enemy.taint,
        arcane=enemy.arcane,
        elder_defense=enemy.elder_defense
    )
    # Build deck from specified cards
    if enemy.card_ids:
        cards = [CARDS_BY_ID[cid] for cid in enemy.card_ids if cid in CARDS_BY_ID]
        p.build_deck_from_list(cards)
    else:
        p.build_deck(get_cards_for_rank(enemy.rank))
    p.draw_initial_hand()
    return p


def render_board_image(session: GameSession, resolving_card_id: str = None,
                       resolving_player_is_bottom: bool = True,
                       book_open: bool = False) -> discord.File:
    """Render the board and return as a discord.File."""
    img_bytes = compositor.render_board(
        session.game_state,
        resolving_card_id=resolving_card_id,
        resolving_player_is_bottom=resolving_player_is_bottom,
        book_open=book_open,
        p1_avatar_bytes=session.p1_avatar_bytes,
        p2_avatar_bytes=session.p2_avatar_bytes
    )
    return discord.File(io.BytesIO(img_bytes), filename="board.png")


def build_game_buttons(session: GameSession) -> discord.ui.View:
    """Build the button UI for the current game state."""
    view = GameView(session)
    return view


# === Discord UI Views ===

class MainMenuView(discord.ui.View):
    """Main menu buttons."""

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
    """In-game action buttons."""

    def __init__(self, session: GameSession):
        super().__init__(timeout=300)
        self.session = session
        gs = session.game_state

        # Only show buttons for human player whose turn it is
        current = gs.current_player
        if current.is_bot:
            return

        # View Hand button (always available)
        self.add_item(ViewHandButton(session))

        # Card play/discard buttons
        for i in range(len(current.hand)):
            can_play, _ = current.can_play_card(i)
            card = current.hand[i]
            self.add_item(PlayCardButton(session, i, card.name, can_play))

        # Discard button
        self.add_item(DiscardSelectButton(session))


class ViewHandButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="View Hand", style=discord.ButtonStyle.secondary, emoji="👁️", row=0)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        gs = self.session.game_state
        # Determine which player is viewing
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

        # Build card info text
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
    def __init__(self, session: GameSession, index: int, card_name: str, can_play: bool):
        label = f"Play [{index + 1}]"
        style = discord.ButtonStyle.success if can_play else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, disabled=not can_play, row=1 + index // 5)
        self.session = session
        self.card_index = index

    async def callback(self, interaction: discord.Interaction):
        await handle_play_card(interaction, self.session, self.card_index)


class DiscardSelectButton(discord.ui.Button):
    def __init__(self, session: GameSession):
        super().__init__(label="Discard a Card", style=discord.ButtonStyle.danger, emoji="🗑️",
                         row=3)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        # Show a dropdown to select which card to discard
        view = DiscardChoiceView(self.session)
        await interaction.response.send_message("Select a card to discard:", view=view, ephemeral=True)


class DiscardChoiceView(discord.ui.View):
    def __init__(self, session: GameSession):
        super().__init__(timeout=60)
        self.session = session
        player = session.game_state.current_player
        options = []
        for i, card in enumerate(player.hand):
            options.append(discord.SelectOption(
                label=f"[{i+1}] {card.name}",
                description=f"Gain {card.sanity_cost} Sanity" if card.sanity_cost > 0 else "No Sanity gain",
                value=str(i)
            ))
        self.add_item(DiscardSelect(session, options))


class DiscardSelect(discord.ui.Select):
    def __init__(self, session: GameSession, options: list):
        super().__init__(placeholder="Choose a card to discard...", options=options)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        await handle_discard_card(interaction, self.session, idx)


class BlackmailChoiceView(discord.ui.View):
    """View for the opponent to choose which card to discard from Blackmail."""
    def __init__(self, session: GameSession, target_player: Player):
        super().__init__(timeout=60)
        self.session = session
        options = []
        for i, card in enumerate(target_player.hand):
            options.append(discord.SelectOption(
                label=f"[{i+1}] {card.name}",
                value=str(i)
            ))
        self.add_item(BlackmailSelect(session, options))


class BlackmailSelect(discord.ui.Select):
    def __init__(self, session: GameSession, options: list):
        super().__init__(placeholder="Choose a card to discard (Blackmail)...", options=options)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        result = self.session.engine.resolve_blackmail_choice(idx)
        self.session.awaiting_blackmail = False
        self.session.blackmail_target_id = None

        channel = interaction.channel
        await interaction.response.send_message(
            f"You discarded a card.", ephemeral=True)

        await post_turn_result(channel, self.session, result)


class MultiplayerLobbyView(discord.ui.View):
    """Lobby waiting for a challenger."""
    def __init__(self, host_id: int, channel_id: int):
        super().__init__(timeout=300)
        self.host_id = host_id
        self.channel_id = channel_id

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_id:
            await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
            return
        await start_multiplayer_game(interaction, self.channel_id)


# === Game Flow Functions ===

async def start_campaign(interaction: discord.Interaction):
    """Start a campaign game for the user."""
    channel_id = interaction.channel_id

    if channel_id in active_games:
        await interaction.response.send_message(
            "A game is already in progress in this channel!", ephemeral=True)
        return

    user = interaction.user
    player_data = load_player_data(str(user.id))
    stage = player_data["campaign_stage"]

    # Get campaign enemy
    enemy_def = get_campaign_enemy(stage)

    # Build players
    human = build_player_from_user(user, player_data)
    human.build_deck(get_cards_for_rank(player_data["rank"]))
    human.draw_initial_hand()

    bot_player = build_bot_player(enemy_def)

    # Create game state (human = bottom/player1, bot = top/player2)
    game_state = GameState(human, bot_player)
    game_state.game_id = str(uuid.uuid4())
    engine = GameEngine(game_state)

    # Bot AI
    difficulty = BotAI.get_difficulty_for_rank(enemy_def.rank)
    bot_ai = BotAI(difficulty)

    # Create session
    session = GameSession(
        game_state=game_state,
        engine=engine,
        channel_id=channel_id,
        bot_ai=bot_ai,
        is_campaign=True
    )

    # Get avatars
    session.p1_avatar_bytes = await get_avatar_bytes(user)

    active_games[channel_id] = session

    # Respond with initial board
    await interaction.response.defer()

    board_file = render_board_image(session)
    view = build_game_buttons(session)

    stage_text = f"**Campaign Stage {stage + 1}/{get_total_campaign_stages()}**"
    enemy_text = f"**VS {enemy_def.name}** (Rank {enemy_def.rank} - Life: {enemy_def.life})"

    msg = await interaction.followup.send(
        f"📖 {stage_text}\n{enemy_text}\n\n{user.display_name}'s turn!",
        file=board_file, view=view)
    session.message = msg


async def create_multiplayer_lobby(interaction: discord.Interaction):
    """Create a multiplayer lobby."""
    channel_id = interaction.channel_id

    if channel_id in active_games:
        await interaction.response.send_message(
            "A game is already in progress in this channel!", ephemeral=True)
        return

    if channel_id in active_lobbies:
        await interaction.response.send_message(
            "A lobby already exists in this channel!", ephemeral=True)
        return

    user = interaction.user
    lobby = LobbyInfo(user.id, user.display_name, channel_id)
    active_lobbies[channel_id] = lobby

    view = MultiplayerLobbyView(user.id, channel_id)
    await interaction.response.send_message(
        f"⚔️ **{user.display_name}** is looking for a challenger!\nClick **Join Game** to accept.",
        view=view)


async def start_multiplayer_game(interaction: discord.Interaction, channel_id: int):
    """Start a multiplayer game when someone joins the lobby."""
    if channel_id not in active_lobbies:
        await interaction.response.send_message("Lobby no longer exists!", ephemeral=True)
        return

    lobby = active_lobbies.pop(channel_id)
    host = await bot.fetch_user(lobby.host_id)
    challenger = interaction.user

    host_data = load_player_data(str(host.id))
    challenger_data = load_player_data(str(challenger.id))

    # Host = bottom (player1), Challenger = top (player2)
    p1 = build_player_from_user(host, host_data)
    p1.build_deck(get_cards_for_rank(host_data["rank"]))
    p1.draw_initial_hand()

    p2 = build_player_from_user(challenger, challenger_data)
    p2.build_deck(get_cards_for_rank(challenger_data["rank"]))
    p2.draw_initial_hand()

    game_state = GameState(p1, p2)
    game_state.game_id = str(uuid.uuid4())
    engine = GameEngine(game_state)

    session = GameSession(
        game_state=game_state,
        engine=engine,
        channel_id=channel_id,
        is_multiplayer=True
    )

    session.p1_avatar_bytes = await get_avatar_bytes(host)
    session.p2_avatar_bytes = await get_avatar_bytes(challenger)

    active_games[channel_id] = session

    await interaction.response.defer()

    board_file = render_board_image(session)
    view = build_game_buttons(session)

    msg = await interaction.followup.send(
        f"⚔️ **{host.display_name}** vs **{challenger.display_name}**\n\n{host.display_name}'s turn!",
        file=board_file, view=view)
    session.message = msg


async def handle_play_card(interaction: discord.Interaction, session: GameSession, card_index: int):
    """Handle a player playing a card."""
    gs = session.game_state
    user_id = str(interaction.user.id)

    # Verify it's this player's turn
    if gs.current_player.user_id != user_id:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return

    if session.awaiting_blackmail:
        await interaction.response.send_message("Waiting for opponent to resolve Blackmail!", ephemeral=True)
        return

    # Play the card
    card = gs.current_player.hand[card_index] if card_index < len(gs.current_player.hand) else None
    result = session.engine.play_card(card_index)

    if not result.card_played and not result.messages:
        await interaction.response.send_message("Invalid card!", ephemeral=True)
        return

    await interaction.response.defer()

    channel = interaction.channel

    # Show the card being played (with book open)
    if result.card_played:
        resolving_file = render_board_image(
            session,
            resolving_card_id=result.card_played.card_id,
            resolving_player_is_bottom=(gs.player1.user_id == user_id or
                                        (gs.current_player == gs.player1)),
            book_open=True
        )
        log_text = "\n".join(result.messages[:5])  # First few messages
        resolve_msg = await channel.send(f"📜 **Card Resolving...**\n{log_text}", file=resolving_file)

        await asyncio.sleep(CARD_DISPLAY_TIME)
        await resolve_msg.delete()

    # Handle blackmail
    if result.requires_blackmail_choice:
        session.awaiting_blackmail = True
        opponent = gs.get_opponent(gs.current_player)
        session.blackmail_target_id = opponent.user_id

        if opponent.is_bot:
            # Bot chooses automatically
            bot_ai = session.bot_ai
            idx = bot_ai.choose_blackmail_discard(opponent)
            blackmail_result = session.engine.resolve_blackmail_choice(idx)
            session.awaiting_blackmail = False
            result.messages.extend(blackmail_result.messages)
            result.game_over = blackmail_result.game_over
            result.game_over_messages.extend(blackmail_result.game_over_messages)
        else:
            # Ask human opponent to choose
            view = BlackmailChoiceView(session, opponent)
            await channel.send(
                f"<@{opponent.user_id}> — You've been Blackmailed! Choose a card to discard:",
                view=view)
            return  # Don't continue turn processing until blackmail resolves

    await post_turn_result(channel, session, result)


async def handle_discard_card(interaction: discord.Interaction, session: GameSession, card_index: int):
    """Handle a player discarding a card."""
    gs = session.game_state
    user_id = str(interaction.user.id)

    if gs.current_player.user_id != user_id:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return

    result = session.engine.discard_card(card_index)
    await interaction.response.defer()
    await post_turn_result(interaction.channel, session, result)


async def post_turn_result(channel: discord.TextChannel, session: GameSession, result: TurnResult):
    """Process a turn result: update board, check game over, handle bot turn."""
    gs = session.game_state

    # Build log text
    log_text = "\n".join(result.messages[-10:])  # Last 10 messages

    if result.game_over:
        await handle_game_over(channel, session, result)
        return

    # Update board
    board_file = render_board_image(session)

    # Check if it's the bot's turn
    if gs.current_player.is_bot and session.bot_ai:
        # Show board state briefly
        bot_msg = await channel.send(
            f"📜 {log_text}\n\n🤖 **{gs.current_player.display_name}** is thinking...",
            file=board_file)

        await asyncio.sleep(2)

        # Bot takes action
        await handle_bot_turn(channel, session)
    else:
        # Human's turn — show buttons
        view = build_game_buttons(session)
        current_name = gs.current_player.display_name
        await channel.send(
            f"📜 {log_text}\n\n**{current_name}**'s turn!",
            file=board_file, view=view)


async def handle_bot_turn(channel: discord.TextChannel, session: GameSession):
    """Handle the bot taking its turn."""
    gs = session.game_state
    bot_player = gs.current_player
    bot_ai = session.bot_ai

    if not bot_player.is_bot or not bot_ai:
        return

    action, index = bot_ai.choose_action(gs)

    if action == "play" and index < len(bot_player.hand):
        card = bot_player.hand[index]
        result = session.engine.play_card(index)

        # Show bot's card being played
        if result.card_played:
            is_bottom = (bot_player == gs.player1)
            resolving_file = render_board_image(
                session,
                resolving_card_id=result.card_played.card_id,
                resolving_player_is_bottom=is_bottom,
                book_open=True
            )
            log_text = "\n".join(result.messages[:5])
            resolve_msg = await channel.send(
                f"🤖 **{bot_player.display_name}** plays **{result.card_played.name}**!\n{log_text}",
                file=resolving_file)
            await asyncio.sleep(CARD_DISPLAY_TIME)
            await resolve_msg.delete()

        # Handle blackmail from bot card (target is human)
        if result.requires_blackmail_choice:
            opponent = gs.get_opponent(bot_player)
            if not opponent.is_bot:
                session.awaiting_blackmail = True
                session.blackmail_target_id = opponent.user_id
                view = BlackmailChoiceView(session, opponent)

                board_file = render_board_image(session)
                await channel.send(
                    f"<@{opponent.user_id}> — You've been Blackmailed! Choose a card to discard:",
                    file=board_file, view=view)
                return
    else:
        result = session.engine.discard_card(index if index < len(bot_player.hand) else 0)
        if result.card_discarded:
            result.messages.insert(0, f"🤖 **{bot_player.display_name}** discards a card.")

    await post_turn_result(channel, session, result)


async def handle_game_over(channel: discord.TextChannel, session: GameSession, result: TurnResult):
    """Handle end of game - show results, update persistence."""
    gs = session.game_state
    channel_id = session.channel_id

    # Remove from active games
    active_games.pop(channel_id, None)

    log_text = "\n".join(result.messages)

    if gs.is_draw:
        # Draw
        board_file = render_board_image(session)
        await channel.send(f"📜 {log_text}", file=board_file)

        # Record draw for human players
        for p in [gs.player1, gs.player2]:
            if not p.is_bot:
                record_draw(p.user_id)
        return

    winner = gs.winner
    loser = gs.player1 if winner == gs.player2 else gs.player2

    # Calculate XP for winner (only if human)
    if not winner.is_bot:
        xp_data = session.engine.calculate_xp(winner)
        rank_data = add_xp(winner.user_id, xp_data["total"])
        record_win(winner.user_id)

        # Advance campaign if applicable
        if session.is_campaign:
            advance_campaign(winner.user_id)

        # Render end screen
        end_bytes = compositor.render_end_screen(winner, xp_data, rank_data)
        end_file = discord.File(io.BytesIO(end_bytes), filename="results.png")

        await channel.send(f"📜 {log_text}", file=end_file)

        if rank_data["ranked_up"]:
            await channel.send(
                f"🎉 **{winner.display_name}** ranked up to "
                f"**{rank_data['new_rank']}- {rank_data['new_rank_name']}**!")
    else:
        # Bot won
        board_file = render_board_image(session)
        await channel.send(f"📜 {log_text}\n\n💀 Better luck next time!", file=board_file)

    # Record loss for the loser (if human)
    if not loser.is_bot:
        record_loss(loser.user_id)


# === Slash Commands ===

@bot.tree.command(name="play", description="Open the Necronomicon - start a game!")
async def play_command(interaction: discord.Interaction):
    """Main entry point - shows the game menu."""
    menu_bytes = compositor.render_menu()
    menu_file = discord.File(io.BytesIO(menu_bytes), filename="menu.png")
    view = MainMenuView()
    await interaction.response.send_message(file=menu_file, view=view)


@bot.tree.command(name="campaign", description="Start your next campaign battle")
async def campaign_command(interaction: discord.Interaction):
    """Quick start for campaign."""
    await start_campaign(interaction)


@bot.tree.command(name="challenge", description="Challenge another player")
@app_commands.describe(opponent="The player to challenge")
async def challenge_command(interaction: discord.Interaction, opponent: discord.Member):
    """Challenge a specific player."""
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return

    if opponent.bot:
        await interaction.response.send_message("Use /campaign to fight bots!", ephemeral=True)
        return

    channel_id = interaction.channel_id
    if channel_id in active_games:
        await interaction.response.send_message(
            "A game is already in progress in this channel!", ephemeral=True)
        return

    # Create a targeted challenge
    view = ChallengeAcceptView(interaction.user.id, opponent.id, channel_id)
    await interaction.response.send_message(
        f"⚔️ **{interaction.user.display_name}** challenges **{opponent.display_name}**!",
        view=view)


class ChallengeAcceptView(discord.ui.View):
    def __init__(self, challenger_id: int, target_id: int, channel_id: int):
        super().__init__(timeout=120)
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.channel_id = channel_id

    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.success, emoji="⚔️")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return

        # Simulate a lobby join
        lobby = LobbyInfo(self.challenger_id, "", self.channel_id)
        active_lobbies[self.channel_id] = lobby
        await start_multiplayer_game(interaction, self.channel_id)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**{interaction.user.display_name}** declined the challenge.")
        self.stop()


@bot.tree.command(name="stats", description="View your player stats and rank")
async def stats_command(interaction: discord.Interaction):
    """View player stats."""
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

    # Cards unlocked
    unlocked = len(get_cards_for_rank(rank))
    total = len(ALL_CARDS)
    embed.add_field(name="Cards Unlocked", value=f"{unlocked}/{total}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="forfeit", description="Forfeit the current game")
async def forfeit_command(interaction: discord.Interaction):
    """Forfeit the current game."""
    channel_id = interaction.channel_id
    if channel_id not in active_games:
        await interaction.response.send_message("No active game in this channel!", ephemeral=True)
        return

    session = active_games[channel_id]
    gs = session.game_state
    user_id = str(interaction.user.id)

    if user_id not in (gs.player1.user_id, gs.player2.user_id):
        await interaction.response.send_message("You're not in this game!", ephemeral=True)
        return

    # Determine winner/loser
    if user_id == gs.player1.user_id:
        gs.winner = gs.player2
    else:
        gs.winner = gs.player1
    gs.game_over = True

    forfeit_result = TurnResult()
    forfeit_result.game_over = True
    forfeit_result.messages.append(f"🏳️ **{interaction.user.display_name}** forfeits!")
    forfeit_result.game_over_messages.append(f"🏆 **{gs.winner.display_name}** wins by forfeit!")

    await interaction.response.defer()
    await handle_game_over(interaction.channel, session, forfeit_result)


@bot.tree.command(name="cardlist", description="View all available cards")
async def cardlist_command(interaction: discord.Interaction):
    """View all cards in the game."""
    data = load_player_data(str(interaction.user.id))
    rank = data["rank"]

    lines = []
    for card in ALL_CARDS:
        unlocked = "✅" if card.rank_required <= rank else f"🔒 Rank {card.rank_required}"
        cost = f"San: {card.sanity_cost}"
        lines.append(f"{unlocked} **{card.name}** — {card.description} ({cost})")

    # Split into chunks for Discord message limits
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
    token = GITHUB_TOKEN
    if not token:
        # Try loading from .env file
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("DISCORD_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip('"\'')
                        break

    if not token:
        print("ERROR: DISCORD_TOKEN not found!")
        print("Set it as an environment variable or create a .env file with:")
        print('DISCORD_TOKEN=your_token_here')
        return

    bot.run(token)


if __name__ == "__main__":
    main()

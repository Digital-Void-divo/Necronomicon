"""Necronomicon Card Game - Image Compositor

Renders game state into composite board images using Pillow.
All positions are designed for an 860x540 board (matching the reference screenshots).
Asset paths are configurable - drop in real PNGs to replace placeholders.
"""

import os
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from models import Player, GameState
from config import (
    BOARD_WIDTH, BOARD_HEIGHT, ASSETS_DIR, FONT_PATH,
    BOARD_BG_PATH, CARD_BACK_PATH, BOOK_CLOSED_PATH, BOOK_OPEN_PATH,
    TAINT_SYMBOL_PATH, ARCANE_SYMBOL_PATH, ELDER_SYMBOL_PATH,
    CARD_IMAGE_PATH_TEMPLATE, MONSTER_IMAGE_PATH_TEMPLATE,
    PENTAGRAM_LEFT_PATH, PENTAGRAM_RIGHT_PATH,
    MENU_BG_PATH, END_SCREEN_BG_PATH,
)


# === Layout Constants (pixel positions on 860x540 board) ===

# Top player (player2) layout
TOP_HAND_X = 148
TOP_HAND_Y = 18
TOP_HAND_CARD_WIDTH = 58
TOP_HAND_CARD_HEIGHT = 80
TOP_HAND_SPACING = 8
TOP_LIFE_X = 688
TOP_LIFE_Y = 32
TOP_SANITY_X = 770
TOP_SANITY_Y = 32
TOP_AVATAR_X = 800
TOP_AVATAR_Y = 60
TOP_NAME_X = 800
TOP_NAME_Y = 100
TOP_RANK_X = 680
TOP_RANK_Y = 148
TOP_STATS_Y = 145  # Y for taint/elder/arcane row
TOP_STATS_BASE_X = 360  # Starting X for stat symbols
TOP_CARD_PLAY_X = 270  # Where played card appears
TOP_CARD_PLAY_Y = 145
TOP_MONSTER_X = 200  # Monster appears to the left for top player
TOP_MONSTER_Y = 178

# Bottom player (player1) layout
BOT_HAND_X = 148
BOT_HAND_Y = 430
BOT_HAND_CARD_WIDTH = 100
BOT_HAND_CARD_HEIGHT = 86
BOT_HAND_SPACING = 10
BOT_LIFE_X = 90
BOT_LIFE_Y = 480
BOT_SANITY_X = 20
BOT_SANITY_Y = 480
BOT_AVATAR_X = 10
BOT_AVATAR_Y = 436
BOT_NAME_X = 10
BOT_NAME_Y = 520
BOT_RANK_X = 300
BOT_RANK_Y = 370
BOT_STATS_Y = 365  # Y for taint/elder/arcane row
BOT_STATS_BASE_X = 360
BOT_CARD_PLAY_X = 270  # Where played card appears
BOT_CARD_PLAY_Y = 310
BOT_MONSTER_X = 540  # Monster appears to the right for bottom player
BOT_MONSTER_Y = 268

# Center book
BOOK_X = 380
BOOK_Y = 218
BOOK_CLOSED_WIDTH = 80
BOOK_CLOSED_HEIGHT = 100
BOOK_OPEN_WIDTH = 160
BOOK_OPEN_HEIGHT = 100

# Stat symbol size
SYMBOL_SIZE = 20
STAT_SPACING = 65

# Card display sizes
PLAY_CARD_WIDTH = 90
PLAY_CARD_HEIGHT = 120

# Monster display
MONSTER_WIDTH = 80
MONSTER_HEIGHT = 100

# Avatar size
AVATAR_SIZE = 36

# Font sizes
FONT_SIZE_STAT = 18
FONT_SIZE_RANK = 14
FONT_SIZE_NAME = 12
FONT_SIZE_LARGE = 24
FONT_SIZE_TITLE = 32
FONT_SIZE_MONSTER_POWER = 16


class ImageCompositor:
    """Renders game state as composite images."""

    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self._font_cache = {}
        self._image_cache = {}

    def _asset_path(self, relative_path: str) -> str:
        return os.path.join(self.base_path, relative_path)

    def _load_image(self, path: str, size: tuple = None) -> Optional[Image.Image]:
        """Load an image, with caching. Returns None if not found."""
        cache_key = f"{path}_{size}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key].copy()

        full_path = self._asset_path(path)
        if os.path.exists(full_path):
            img = Image.open(full_path).convert("RGBA")
            if size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            self._image_cache[cache_key] = img
            return img.copy()
        return None

    def _create_placeholder(self, width: int, height: int,
                            color: tuple = (80, 40, 40, 200),
                            text: str = "", text_color: tuple = (200, 200, 200)) -> Image.Image:
        """Create a placeholder rectangle with optional text."""
        img = Image.new("RGBA", (width, height), color)
        if text:
            draw = ImageDraw.Draw(img)
            font = self._get_font(10)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (width - tw) // 2
            y = (height - th) // 2
            draw.text((x, y), text, fill=text_color, font=font)
        return img

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font at specified size, falling back to default."""
        if size in self._font_cache:
            return self._font_cache[size]

        font_path = self._asset_path(FONT_PATH)
        try:
            font = ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        self._font_cache[size] = font
        return font

    def _get_card_back(self, width: int, height: int) -> Image.Image:
        img = self._load_image(CARD_BACK_PATH, (width, height))
        if img is None:
            img = self._create_placeholder(width, height, (60, 35, 20, 230), "🂠")
        return img

    def _get_card_image(self, card_id: str, width: int, height: int) -> Image.Image:
        path = CARD_IMAGE_PATH_TEMPLATE.format(card_id=card_id)
        img = self._load_image(path, (width, height))
        if img is None:
            img = self._create_placeholder(width, height, (50, 30, 50, 230), card_id[:8])
        return img

    def _get_monster_image(self, monster_id: str, width: int, height: int) -> Image.Image:
        path = MONSTER_IMAGE_PATH_TEMPLATE.format(monster_id=monster_id)
        img = self._load_image(path, (width, height))
        if img is None:
            img = self._create_placeholder(width, height, (40, 40, 80, 200), monster_id[:8])
        return img

    def _get_symbol(self, path: str) -> Image.Image:
        img = self._load_image(path, (SYMBOL_SIZE, SYMBOL_SIZE))
        if img is None:
            color_map = {
                TAINT_SYMBOL_PATH: (200, 180, 0, 255),
                ELDER_SYMBOL_PATH: (0, 180, 0, 255),
                ARCANE_SYMBOL_PATH: (200, 0, 0, 255),
            }
            color = color_map.get(path, (180, 180, 180, 255))
            img = Image.new("RGBA", (SYMBOL_SIZE, SYMBOL_SIZE), color)
        return img

    def _load_avatar(self, avatar_url: str, size: int = AVATAR_SIZE) -> Image.Image:
        """Load avatar - for now returns placeholder. In Discord, avatar bytes will be passed in."""
        return self._create_placeholder(size, size, (100, 100, 100, 200), "👤")

    def render_board(self, game_state: GameState,
                     resolving_card_id: str = None,
                     resolving_player_is_bottom: bool = True,
                     book_open: bool = False,
                     p1_avatar_bytes: bytes = None,
                     p2_avatar_bytes: bytes = None) -> bytes:
        """Render the full game board and return as PNG bytes."""

        # Load or create background
        board = self._load_image(BOARD_BG_PATH, (BOARD_WIDTH, BOARD_HEIGHT))
        if board is None:
            board = Image.new("RGBA", (BOARD_WIDTH, BOARD_HEIGHT), (60, 30, 20, 255))

        draw = ImageDraw.Draw(board)

        p1 = game_state.player1  # Bottom
        p2 = game_state.player2  # Top

        # === Draw Top Player (p2) ===
        self._draw_player_hand_backs(board, p2, TOP_HAND_X, TOP_HAND_Y,
                                      TOP_HAND_CARD_WIDTH, TOP_HAND_CARD_HEIGHT,
                                      TOP_HAND_SPACING)
        self._draw_player_stats_label(draw, p2,
                                       TOP_LIFE_X, TOP_LIFE_Y,
                                       TOP_SANITY_X, TOP_SANITY_Y,
                                       is_top=True)
        self._draw_stat_symbols(board, draw, p2,
                                 TOP_STATS_BASE_X, TOP_STATS_Y, is_top=True)
        self._draw_rank_label(draw, p2, TOP_RANK_X, TOP_RANK_Y)
        self._draw_avatar(board, draw, p2, TOP_AVATAR_X, TOP_AVATAR_Y,
                           TOP_NAME_X, TOP_NAME_Y, p2_avatar_bytes)

        # === Draw Bottom Player (p1) ===
        self._draw_player_hand_backs(board, p1, BOT_HAND_X, BOT_HAND_Y,
                                      BOT_HAND_CARD_WIDTH, BOT_HAND_CARD_HEIGHT,
                                      BOT_HAND_SPACING)
        self._draw_player_stats_label(draw, p1,
                                       BOT_LIFE_X, BOT_LIFE_Y,
                                       BOT_SANITY_X, BOT_SANITY_Y,
                                       is_top=False)
        self._draw_stat_symbols(board, draw, p1,
                                 BOT_STATS_BASE_X, BOT_STATS_Y, is_top=False)
        self._draw_rank_label(draw, p1, BOT_RANK_X, BOT_RANK_Y)
        self._draw_avatar(board, draw, p1, BOT_AVATAR_X, BOT_AVATAR_Y,
                           BOT_NAME_X, BOT_NAME_Y, p1_avatar_bytes)

        # === Draw Center Book ===
        if book_open:
            book_img = self._load_image(BOOK_OPEN_PATH, (BOOK_OPEN_WIDTH, BOOK_OPEN_HEIGHT))
            if book_img is None:
                book_img = self._create_placeholder(BOOK_OPEN_WIDTH, BOOK_OPEN_HEIGHT,
                                                     (120, 100, 60, 200), "📖 OPEN")
            board.paste(book_img, (BOOK_X - 40, BOOK_Y), book_img)
        else:
            book_img = self._load_image(BOOK_CLOSED_PATH, (BOOK_CLOSED_WIDTH, BOOK_CLOSED_HEIGHT))
            if book_img is None:
                book_img = self._create_placeholder(BOOK_CLOSED_WIDTH, BOOK_CLOSED_HEIGHT,
                                                     (100, 80, 40, 200), "📕")
            board.paste(book_img, (BOOK_X, BOOK_Y), book_img)

        # === Draw Resolving Card ===
        if resolving_card_id:
            card_img = self._get_card_image(resolving_card_id, PLAY_CARD_WIDTH, PLAY_CARD_HEIGHT)
            if resolving_player_is_bottom:
                board.paste(card_img, (BOT_CARD_PLAY_X, BOT_CARD_PLAY_Y), card_img)
            else:
                board.paste(card_img, (TOP_CARD_PLAY_X, TOP_CARD_PLAY_Y), card_img)

        # === Draw Monsters ===
        if p1.monster:
            m_img = self._get_monster_image(p1.monster.monster_id, MONSTER_WIDTH, MONSTER_HEIGHT)
            board.paste(m_img, (BOT_MONSTER_X, BOT_MONSTER_Y), m_img)
            # Power label
            power_font = self._get_font(FONT_SIZE_MONSTER_POWER)
            draw.text((BOT_MONSTER_X + 4, BOT_MONSTER_Y + MONSTER_HEIGHT - 22),
                      str(p1.monster.power), fill=(255, 50, 50), font=power_font)

        if p2.monster:
            m_img = self._get_monster_image(p2.monster.monster_id, MONSTER_WIDTH, MONSTER_HEIGHT)
            board.paste(m_img, (TOP_MONSTER_X, TOP_MONSTER_Y), m_img)
            power_font = self._get_font(FONT_SIZE_MONSTER_POWER)
            draw.text((TOP_MONSTER_X + 4, TOP_MONSTER_Y + MONSTER_HEIGHT - 22),
                      str(p2.monster.power), fill=(255, 50, 50), font=power_font)

        # === Draw Madness Indicator ===
        if p1.madness:
            madness_font = self._get_font(11)
            draw.text((BOT_HAND_X, BOT_HAND_Y - 16),
                      f"🤯 {p1.madness}", fill=(255, 100, 100), font=madness_font)
        if p2.madness:
            madness_font = self._get_font(11)
            draw.text((TOP_HAND_X, TOP_HAND_Y + TOP_HAND_CARD_HEIGHT + 4),
                      f"🤯 {p2.madness}", fill=(255, 100, 100), font=madness_font)

        # === Draw Invulnerability Indicator ===
        if p1.invulnerable:
            inv_font = self._get_font(11)
            draw.text((BOT_STATS_BASE_X + STAT_SPACING * 3, BOT_STATS_Y),
                      "🛡️", fill=(0, 200, 255), font=inv_font)
        if p2.invulnerable:
            inv_font = self._get_font(11)
            draw.text((TOP_STATS_BASE_X + STAT_SPACING * 3, TOP_STATS_Y),
                      "🛡️", fill=(0, 200, 255), font=inv_font)

        # === Draw Turn Indicator ===
        turn_font = self._get_font(12)
        if game_state.current_player == p1:
            draw.text((10, BOARD_HEIGHT // 2 - 6), "▶ YOUR TURN",
                      fill=(0, 255, 100), font=turn_font)
        else:
            draw.text((10, BOARD_HEIGHT // 2 - 6), "▶ OPPONENT'S TURN",
                      fill=(255, 100, 100), font=turn_font)

        # Convert to bytes
        buffer = io.BytesIO()
        board.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def _draw_player_hand_backs(self, board: Image.Image, player: Player,
                                 x: int, y: int, card_w: int, card_h: int, spacing: int):
        """Draw face-down cards for the player's hand."""
        for i in range(len(player.hand)):
            card_back = self._get_card_back(card_w, card_h)
            cx = x + i * (card_w + spacing)
            board.paste(card_back, (cx, y), card_back)

    def _draw_player_stats_label(self, draw: ImageDraw.Draw, player: Player,
                                  life_x: int, life_y: int,
                                  sanity_x: int, sanity_y: int,
                                  is_top: bool):
        """Draw Life and Sanity labels."""
        font = self._get_font(FONT_SIZE_STAT)
        label_font = self._get_font(FONT_SIZE_NAME)

        # Life
        life_color = (0, 255, 0) if player.life > 15 else (255, 50, 50)
        if is_top:
            draw.text((life_x, life_y - 18), "Life", fill=(200, 200, 200), font=label_font)
        draw.text((life_x, life_y), str(player.life), fill=life_color, font=font)
        if not is_top:
            draw.text((life_x, life_y + 22), "Life", fill=(200, 200, 200), font=label_font)

        # Sanity
        sanity_color = (100, 200, 255) if player.sanity > 0 else (255, 50, 50)
        if is_top:
            draw.text((sanity_x, sanity_y - 18), "Sanity", fill=(200, 200, 200), font=label_font)
        draw.text((sanity_x, sanity_y), str(player.sanity), fill=sanity_color, font=font)
        if not is_top:
            draw.text((sanity_x, sanity_y + 22), "Sanity", fill=(200, 200, 200), font=label_font)

    def _draw_stat_symbols(self, board: Image.Image, draw: ImageDraw.Draw,
                            player: Player, base_x: int, y: int, is_top: bool):
        """Draw Taint, Elder Defense, Arcane Power symbols with values."""
        font = self._get_font(FONT_SIZE_STAT)
        stats = [
            (TAINT_SYMBOL_PATH, player.taint, (200, 180, 0)),
            (ELDER_SYMBOL_PATH, player.elder_defense, (0, 180, 0)),
            (ARCANE_SYMBOL_PATH, player.arcane, (200, 50, 50)),
        ]

        for i, (symbol_path, value, color) in enumerate(stats):
            sx = base_x + i * STAT_SPACING
            symbol = self._get_symbol(symbol_path)
            board.paste(symbol, (sx, y), symbol)
            draw.text((sx + SYMBOL_SIZE + 3, y), str(value), fill=color, font=font)

    def _draw_rank_label(self, draw: ImageDraw.Draw, player: Player, x: int, y: int):
        """Draw rank label like '1- Thug'."""
        font = self._get_font(FONT_SIZE_RANK)
        text = f"{player.rank}- {player.rank_title}"
        draw.text((x, y), text, fill=(200, 200, 200), font=font)

    def _draw_avatar(self, board: Image.Image, draw: ImageDraw.Draw,
                      player: Player, avatar_x: int, avatar_y: int,
                      name_x: int, name_y: int,
                      avatar_bytes: bytes = None):
        """Draw player avatar and name."""
        if avatar_bytes:
            try:
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                avatar_img = avatar_img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            except Exception:
                avatar_img = self._load_avatar("")
        else:
            avatar_img = self._load_avatar("")

        board.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

        # Name
        name_font = self._get_font(FONT_SIZE_NAME)
        draw.text((name_x, name_y), player.display_name[:15],
                  fill=(200, 200, 200), font=name_font)

    def render_hand(self, player: Player) -> bytes:
        """Render a player's hand as an image (for ephemeral display)."""
        if not player.hand:
            img = Image.new("RGBA", (400, 140), (30, 20, 15, 255))
            draw = ImageDraw.Draw(img)
            font = self._get_font(16)
            draw.text((100, 55), "No cards in hand", fill=(200, 200, 200), font=font)
        else:
            card_w, card_h = 120, 170
            spacing = 8
            total_w = len(player.hand) * (card_w + spacing) - spacing + 20
            img = Image.new("RGBA", (total_w, card_h + 40), (30, 20, 15, 240))

            for i, card in enumerate(player.hand):
                card_img = self._get_card_image(card.card_id, card_w, card_h)
                x = 10 + i * (card_w + spacing)
                img.paste(card_img, (x, 5), card_img)

                # Card number label
                draw = ImageDraw.Draw(img)
                num_font = self._get_font(14)
                draw.text((x + card_w // 2 - 5, card_h + 10),
                          f"[{i + 1}]", fill=(200, 200, 100), font=num_font)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def render_menu(self) -> bytes:
        """Render the main menu image."""
        menu = self._load_image(MENU_BG_PATH, (BOARD_WIDTH, BOARD_HEIGHT))
        if menu is None:
            menu = Image.new("RGBA", (BOARD_WIDTH, BOARD_HEIGHT), (40, 20, 15, 255))
            draw = ImageDraw.Draw(menu)
            title_font = self._get_font(FONT_SIZE_TITLE)
            draw.text((200, 30), "NECRONOMICON", fill=(180, 150, 100), font=title_font)

            option_font = self._get_font(FONT_SIZE_LARGE)
            options = ["Campaign", "Challenge Mode", "Multiplayer", "How to Play"]
            for i, opt in enumerate(options):
                draw.text((350, 130 + i * 80), opt, fill=(200, 180, 130), font=option_font)

        buffer = io.BytesIO()
        menu.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def render_end_screen(self, winner: Player, xp_data: dict,
                          rank_data: dict, is_draw: bool = False) -> bytes:
        """Render the end-of-game score screen."""
        bg = self._load_image(END_SCREEN_BG_PATH, (BOARD_WIDTH, BOARD_HEIGHT))
        if bg is None:
            bg = Image.new("RGBA", (BOARD_WIDTH, BOARD_HEIGHT), (40, 25, 15, 255))

        draw = ImageDraw.Draw(bg)
        title_font = self._get_font(FONT_SIZE_TITLE)
        large_font = self._get_font(FONT_SIZE_LARGE)
        stat_font = self._get_font(FONT_SIZE_STAT)
        label_font = self._get_font(FONT_SIZE_RANK)

        # Title
        if is_draw:
            draw.text((250, 20), "DRAW", fill=(200, 200, 100), font=title_font)
        else:
            draw.text((180, 20), "ROUND SCORES and RANK",
                      fill=(0, 200, 100), font=title_font)

        y = 80
        line_h = 32

        # Previous Rank
        draw.text((60, y), "Previous Rank", fill=(200, 200, 200), font=stat_font)
        draw.text((550, y), f"{rank_data['old_rank']}- {rank_data['old_rank_name']}",
                  fill=(200, 200, 200), font=stat_font)
        y += line_h

        # Remaining Life
        life_color = (0, 200, 0) if xp_data.get("remaining_life", 0) > 0 else (200, 0, 0)
        draw.text((60, y), "Remaining Life", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("remaining_life", 0)),
                  fill=life_color, font=stat_font)
        y += line_h

        # Remaining Sanity
        san = xp_data.get("remaining_sanity", 0)
        san_color = (0, 150, 255) if san > 0 else (200, 0, 0)
        draw.text((60, y), "Remaining Sanity", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(san), fill=san_color, font=stat_font)
        y += line_h

        # Damage Inflicted
        draw.text((60, y), "Damage Inflicted", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("damage_dealt", 0)),
                  fill=(200, 200, 200), font=stat_font)

        # Best Attack
        draw.text((660, y), f"+ {xp_data.get('best_attack', 0)}",
                  fill=(200, 200, 200), font=label_font)
        y += line_h

        # Damage Received (subtracted)
        draw.text((60, y), "−  Damage Received", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("damage_received", 0)),
                  fill=(200, 50, 50), font=stat_font)
        y += line_h + 10

        # Separator
        draw.line([(60, y), (700, y)], fill=(150, 130, 100), width=2)
        y += 15

        # Total for this Round
        draw.text((60, y), "Total for this Round", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("total", 0)),
                  fill=(200, 200, 200), font=stat_font)
        y += line_h

        # Previous Total
        prev_xp = rank_data.get("total_xp", 0) - xp_data.get("total", 0)
        draw.text((60, y), "Previous Total", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(max(0, prev_xp)), fill=(200, 200, 200), font=stat_font)
        y += line_h

        # Current Total
        draw.text((60, y), "Current Total", fill=(0, 200, 100), font=large_font)
        draw.text((580, y), str(rank_data.get("total_xp", 0)),
                  fill=(0, 200, 100), font=large_font)
        y += line_h + 20

        # Current Rank
        draw.text((60, y), "Current Rank", fill=(0, 200, 100), font=large_font)
        rank_text = f"{rank_data['new_rank']}- {rank_data['new_rank_name']}"
        draw.text((450, y), rank_text, fill=(0, 200, 100), font=large_font)

        # Rank up notification
        if rank_data.get("ranked_up"):
            draw.text((300, y + 40), "⬆ RANK UP! ⬆",
                      fill=(255, 215, 0), font=title_font)

        buffer = io.BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

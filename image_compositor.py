"""Necronomicon Card Game - Image Compositor

Renders game state into composite board images using Pillow.
Layout is designed to match the original Flash game at 860x540.
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
    MENU_BG_PATH, END_SCREEN_BG_PATH,
)


class ImageCompositor:
    """Renders game state as composite images."""

    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self._font_cache = {}
        self._image_cache = {}

    def _asset_path(self, relative_path: str) -> str:
        return os.path.join(self.base_path, relative_path)

    def _load_image(self, path: str, size: tuple = None) -> Optional[Image.Image]:
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
                            text: str = "",
                            text_color: tuple = (200, 200, 200)) -> Image.Image:
        img = Image.new("RGBA", (width, height), color)
        if text:
            draw = ImageDraw.Draw(img)
            font = self._get_font(10)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((width - tw) // 2, (height - th) // 2), text,
                      fill=text_color, font=font)
        return img

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        if size in self._font_cache:
            return self._font_cache[size]
        font_path = self._asset_path(FONT_PATH)
        try:
            font = ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
            except (OSError, IOError):
                font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    def _get_card_back(self, w: int, h: int) -> Image.Image:
        img = self._load_image(CARD_BACK_PATH, (w, h))
        return img or self._create_placeholder(w, h, (60, 35, 20, 230), "🂠")

    def _get_card_image(self, card_id: str, w: int, h: int) -> Image.Image:
        path = CARD_IMAGE_PATH_TEMPLATE.format(card_id=card_id)
        img = self._load_image(path, (w, h))
        return img or self._create_placeholder(w, h, (50, 30, 50, 230), card_id[:10])

    def _get_monster_image(self, monster_id: str, w: int, h: int) -> Image.Image:
        path = MONSTER_IMAGE_PATH_TEMPLATE.format(monster_id=monster_id)
        img = self._load_image(path, (w, h))
        return img or self._create_placeholder(w, h, (40, 40, 80, 200), monster_id[:8])

    def _get_symbol(self, path: str, size: int = 22) -> Image.Image:
        img = self._load_image(path, (size, size))
        if img is None:
            color_map = {
                TAINT_SYMBOL_PATH: (200, 180, 0, 255),
                ELDER_SYMBOL_PATH: (0, 180, 0, 255),
                ARCANE_SYMBOL_PATH: (200, 0, 0, 255),
            }
            color = color_map.get(path, (180, 180, 180, 255))
            img = Image.new("RGBA", (size, size), color)
        return img

    def _load_avatar_bytes(self, avatar_bytes: bytes, size: int = 40) -> Image.Image:
        if avatar_bytes:
            try:
                img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                return img.resize((size, size), Image.Resampling.LANCZOS)
            except Exception:
                pass
        return self._create_placeholder(size, size, (100, 100, 100, 200), "?")

    def render_board(self, game_state: GameState,
                     resolving_card_id: str = None,
                     resolving_player_is_bottom: bool = True,
                     book_open: bool = False,
                     p1_avatar_bytes: bytes = None,
                     p2_avatar_bytes: bytes = None) -> bytes:
        """Render the full game board."""

        # Load background
        board = self._load_image(BOARD_BG_PATH, (BOARD_WIDTH, BOARD_HEIGHT))
        if board is None:
            board = Image.new("RGBA", (BOARD_WIDTH, BOARD_HEIGHT), (60, 30, 20, 255))

        draw = ImageDraw.Draw(board)

        p1 = game_state.player1  # Bottom (initiator)
        p2 = game_state.player2  # Top (challenger/bot)

        # ============================================================
        # TOP PLAYER (p2) — upper portion of board
        # ============================================================

        # -- Face-down hand cards --
        top_card_w, top_card_h = 68, 90
        top_card_spacing = 10
        top_hand_x, top_hand_y = 148, 12
        for i in range(len(p2.hand)):
            card = self._get_card_back(top_card_w, top_card_h)
            cx = top_hand_x + i * (top_card_w + top_card_spacing)
            board.paste(card, (cx, top_hand_y), card)

        # -- Life and Sanity (top right) --
        label_font = self._get_font(22)
        value_font = self._get_font(26)

        draw.text((640, 8), "Life", fill=(200, 180, 130), font=label_font)
        life_color = (0, 220, 0) if p2.life > 15 else (255, 50, 50)
        draw.text((648, 34), str(p2.life), fill=life_color, font=value_font)

        draw.text((740, 8), "Sanity", fill=(200, 180, 130), font=label_font)
        san_color = (100, 200, 255) if p2.sanity > 0 else (255, 50, 50)
        draw.text((755, 34), str(p2.sanity), fill=san_color, font=value_font)

        # -- Avatar (top right, next to sanity) --
        avatar_img = self._load_avatar_bytes(p2_avatar_bytes, 40)
        board.paste(avatar_img, (810, 30), avatar_img)
        name_font = self._get_font(11)
        # Truncate name to fit
        name = p2.display_name[:12]
        draw.text((810, 72), name, fill=(200, 200, 200), font=name_font)

        # -- Rank (right side, below cards) --
        rank_font = self._get_font(18)
        rank_text = f"{p2.rank}- {p2.rank_title}"
        draw.text((660, 140), rank_text, fill=(200, 180, 130), font=rank_font)

        # -- Stats row (taint, elder, arcane) centered-ish --
        stat_font = self._get_font(20)
        stat_sym_size = 22
        stat_y = 140
        stat_base_x = 370
        stat_gap = 70

        stats = [
            (TAINT_SYMBOL_PATH, p2.taint, (200, 180, 0)),
            (ELDER_SYMBOL_PATH, p2.elder_defense, (0, 200, 0)),
            (ARCANE_SYMBOL_PATH, p2.arcane, (220, 50, 50)),
        ]
        for i, (sym_path, val, color) in enumerate(stats):
            sx = stat_base_x + i * stat_gap
            sym = self._get_symbol(sym_path, stat_sym_size)
            board.paste(sym, (sx, stat_y), sym)
            draw.text((sx + stat_sym_size + 4, stat_y - 1), str(val),
                      fill=color, font=stat_font)

        # -- Invulnerability indicator --
        if p2.invulnerable:
            draw.text((stat_base_x + 3 * stat_gap, stat_y), "🛡️",
                      fill=(0, 200, 255), font=self._get_font(18))

        # -- Madness indicator --
        if p2.madness:
            madness_font = self._get_font(13)
            draw.text((148, top_hand_y + top_card_h + 4),
                      f"🤯 {p2.madness}", fill=(255, 100, 100), font=madness_font)

        # ============================================================
        # CENTER — Book, play areas, monsters
        # ============================================================

        # -- Book --
        if book_open:
            book_img = self._load_image(BOOK_OPEN_PATH, (160, 100))
            if book_img is None:
                book_img = self._create_placeholder(160, 100, (120, 100, 50, 220), "📖")
            board.paste(book_img, (350, 215), book_img)
        else:
            book_img = self._load_image(BOOK_CLOSED_PATH, (80, 100))
            if book_img is None:
                book_img = self._create_placeholder(80, 100, (100, 80, 40, 220), "📕")
            board.paste(book_img, (390, 215), book_img)

        # -- Resolving card display --
        play_card_w, play_card_h = 90, 120
        if resolving_card_id:
            card_img = self._get_card_image(resolving_card_id, play_card_w, play_card_h)
            if resolving_player_is_bottom:
                # Bottom player's card: show in lower-center area
                board.paste(card_img, (270, 300), card_img)
            else:
                # Top player's card: show in upper-center area
                board.paste(card_img, (270, 145), card_img)

        # -- Monsters --
        monster_w, monster_h = 80, 100

        # Bottom player's monster: RIGHT side of center
        if p1.monster:
            m_img = self._get_monster_image(p1.monster.monster_id, monster_w, monster_h)
            mx, my = 540, 265
            board.paste(m_img, (mx, my), m_img)
            power_font = self._get_font(18)
            draw.text((mx + 4, my + monster_h - 24),
                      str(p1.monster.power), fill=(255, 50, 50), font=power_font)

        # Top player's monster: LEFT side of center (mirrored)
        if p2.monster:
            m_img = self._get_monster_image(p2.monster.monster_id, monster_w, monster_h)
            mx, my = 200, 175
            board.paste(m_img, (mx, my), m_img)
            power_font = self._get_font(18)
            draw.text((mx + 4, my + monster_h - 24),
                      str(p2.monster.power), fill=(255, 50, 50), font=power_font)

        # ============================================================
        # BOTTOM PLAYER (p1) — lower portion of board
        # ============================================================

        # -- Stats row (taint, elder, arcane) --
        bot_stat_y = 365
        for i, (sym_path, val, color) in enumerate([
            (TAINT_SYMBOL_PATH, p1.taint, (200, 180, 0)),
            (ELDER_SYMBOL_PATH, p1.elder_defense, (0, 200, 0)),
            (ARCANE_SYMBOL_PATH, p1.arcane, (220, 50, 50)),
        ]):
            sx = stat_base_x + i * stat_gap
            sym = self._get_symbol(sym_path, stat_sym_size)
            board.paste(sym, (sx, bot_stat_y), sym)
            draw.text((sx + stat_sym_size + 4, bot_stat_y - 1), str(val),
                      fill=color, font=stat_font)

        # -- Invulnerability --
        if p1.invulnerable:
            draw.text((stat_base_x + 3 * stat_gap, bot_stat_y), "🛡️",
                      fill=(0, 200, 255), font=self._get_font(18))

        # -- Rank --
        draw.text((250, bot_stat_y), f"{p1.rank}- {p1.rank_title}",
                  fill=(200, 180, 130), font=rank_font)

        # -- Madness indicator --
        if p1.madness:
            madness_font = self._get_font(13)
            draw.text((148, 415),
                      f"🤯 {p1.madness}", fill=(255, 100, 100), font=madness_font)

        # -- Face-down hand cards --
        bot_card_w, bot_card_h = 95, 83
        bot_card_spacing = 10
        bot_hand_x, bot_hand_y = 165, 432
        for i in range(len(p1.hand)):
            card = self._get_card_back(bot_card_w, bot_card_h)
            cx = bot_hand_x + i * (bot_card_w + bot_card_spacing)
            board.paste(card, (cx, bot_hand_y), card)

        # -- Sanity (bottom left) --
        draw.text((25, 470), str(p1.sanity), fill=san_color, font=value_font)
        draw.text((18, 500), "Sanity", fill=(200, 180, 130), font=self._get_font(16))

        # Recalculate sanity color for p1
        p1_san_color = (100, 200, 255) if p1.sanity > 0 else (255, 50, 50)
        p1_life_color = (0, 220, 0) if p1.life > 15 else (255, 50, 50)

        draw.text((25, 470), str(p1.sanity), fill=p1_san_color, font=value_font)
        draw.text((100, 470), str(p1.life), fill=p1_life_color, font=value_font)
        draw.text((18, 500), "Sanity", fill=(200, 180, 130), font=self._get_font(16))
        draw.text((95, 500), "Life", fill=(200, 180, 130), font=self._get_font(16))

        # -- Avatar (bottom left corner) --
        avatar_img = self._load_avatar_bytes(p1_avatar_bytes, 40)
        board.paste(avatar_img, (8, 432), avatar_img)
        draw.text((8, 520), p1.display_name[:12],
                  fill=(200, 200, 200), font=name_font)

        # Convert to bytes
        buffer = io.BytesIO()
        board.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def render_hand(self, player: Player) -> bytes:
        """Render a player's hand as a face-up image (for ephemeral display)."""
        if not player.hand:
            img = Image.new("RGBA", (400, 140), (30, 20, 15, 255))
            draw = ImageDraw.Draw(img)
            font = self._get_font(16)
            draw.text((100, 55), "No cards in hand",
                      fill=(200, 200, 200), font=font)
        else:
            card_w, card_h = 120, 170
            spacing = 8
            total_w = len(player.hand) * (card_w + spacing) - spacing + 20
            img = Image.new("RGBA", (total_w, card_h + 40), (30, 20, 15, 240))

            for i, card in enumerate(player.hand):
                card_img = self._get_card_image(card.card_id, card_w, card_h)
                x = 10 + i * (card_w + spacing)
                img.paste(card_img, (x, 5), card_img)

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
            title_font = self._get_font(32)
            draw.text((200, 30), "NECRONOMICON",
                      fill=(180, 150, 100), font=title_font)
            option_font = self._get_font(24)
            options = ["Campaign", "Challenge Mode", "Multiplayer", "How to Play"]
            for i, opt in enumerate(options):
                draw.text((350, 130 + i * 80), opt,
                          fill=(200, 180, 130), font=option_font)

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
        title_font = self._get_font(32)
        large_font = self._get_font(24)
        stat_font = self._get_font(18)

        if is_draw:
            draw.text((340, 20), "DRAW", fill=(200, 200, 100), font=title_font)
        else:
            draw.text((180, 20), "ROUND SCORES and RANK",
                      fill=(0, 200, 100), font=title_font)

        y = 80
        lh = 32

        draw.text((60, y), "Previous Rank", fill=(200, 200, 200), font=stat_font)
        draw.text((550, y),
                  f"{rank_data['old_rank']}- {rank_data['old_rank_name']}",
                  fill=(200, 200, 200), font=stat_font)
        y += lh

        life_c = (0, 200, 0) if xp_data.get("remaining_life", 0) > 0 else (200, 0, 0)
        draw.text((60, y), "Remaining Life", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("remaining_life", 0)),
                  fill=life_c, font=stat_font)
        y += lh

        san = xp_data.get("remaining_sanity", 0)
        san_c = (0, 150, 255) if san > 0 else (200, 0, 0)
        draw.text((60, y), "Remaining Sanity", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(san), fill=san_c, font=stat_font)
        y += lh

        draw.text((60, y), "Damage Inflicted", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("damage_dealt", 0)),
                  fill=(200, 200, 200), font=stat_font)
        label_font = self._get_font(14)
        draw.text((660, y + 2),
                  f"+ {xp_data.get('best_attack', 0)}",
                  fill=(200, 200, 200), font=label_font)
        y += lh

        draw.text((60, y), "−  Damage Received", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("damage_received", 0)),
                  fill=(200, 50, 50), font=stat_font)
        y += lh + 10

        draw.line([(60, y), (700, y)], fill=(150, 130, 100), width=2)
        y += 15

        draw.text((60, y), "Total for this Round", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(xp_data.get("total", 0)),
                  fill=(200, 200, 200), font=stat_font)
        y += lh

        prev_xp = rank_data.get("total_xp", 0) - xp_data.get("total", 0)
        draw.text((60, y), "Previous Total", fill=(200, 200, 200), font=stat_font)
        draw.text((600, y), str(max(0, prev_xp)),
                  fill=(200, 200, 200), font=stat_font)
        y += lh

        draw.text((60, y), "Current Total", fill=(0, 200, 100), font=large_font)
        draw.text((580, y), str(rank_data.get("total_xp", 0)),
                  fill=(0, 200, 100), font=large_font)
        y += lh + 20

        draw.text((60, y), "Current Rank", fill=(0, 200, 100), font=large_font)
        r_text = f"{rank_data['new_rank']}- {rank_data['new_rank_name']}"
        draw.text((450, y), r_text, fill=(0, 200, 100), font=large_font)

        if rank_data.get("ranked_up"):
            draw.text((300, y + 40), "⬆ RANK UP! ⬆",
                      fill=(255, 215, 0), font=title_font)

        buffer = io.BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

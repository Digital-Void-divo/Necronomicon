"""Necronomicon Card Game - Image Compositor

Renders game state into composite board images using Pillow.
Auto-detects the actual board_bg.png resolution and proportionally
scales every coordinate from the 1536×1024 reference defined in
config.py, so the same code works at any board size.

IMPORTANT: The board background already contains baked-in artwork for
"Life", "Sanity" labels and the three stat-bar symbols (Taint, Arcane,
Elder).  This compositor only draws *numbers* and *dynamic elements*
on top — it never re-draws those static labels.
"""

import os
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

from models import Player, GameState
from config import (
    ASSETS_DIR, FONT_PATH,
    BOARD_BG_PATH, CARD_BACK_PATH, BOOK_CLOSED_PATH, BOOK_OPEN_PATH,
    CARD_IMAGE_PATH_TEMPLATE, MONSTER_IMAGE_PATH_TEMPLATE,
    MENU_BG_PATH, END_SCREEN_BG_PATH, HAND_BG_PATH,
    BOARD_REF_W, BOARD_REF_H,
    # Top player
    TOP_CARD_SLOTS, TOP_LIFE_BOX, TOP_SANITY_BOX,
    TOP_AVATAR_BOX, TOP_NAME_POS, TOP_RANK_POS,
    TOP_TAINT_NUM_POS, TOP_ARCANE_NUM_POS, TOP_ELDER_NUM_POS,
    TOP_INVULN_POS, TOP_MADNESS_POS,
    TOP_MONSTER_POS, TOP_MONSTER_SIZE,
    # Centre
    BOOK_CLOSED_POS, BOOK_CLOSED_SIZE, BOOK_OPEN_POS, BOOK_OPEN_SIZE,
    CARD_DISPLAY_LEFT_POS, CARD_DISPLAY_LEFT_SIZE,
    CARD_DISPLAY_RIGHT_POS, CARD_DISPLAY_RIGHT_SIZE,
    # Bottom player
    BOTTOM_CARD_SLOTS, BOTTOM_LIFE_BOX, BOTTOM_SANITY_BOX,
    BOTTOM_AVATAR_BOX, BOTTOM_NAME_POS, BOTTOM_RANK_POS,
    BOTTOM_TAINT_NUM_POS, BOTTOM_ARCANE_NUM_POS, BOTTOM_ELDER_NUM_POS,
    BOTTOM_INVULN_POS, BOTTOM_MADNESS_POS,
    BOTTOM_MONSTER_POS, BOTTOM_MONSTER_SIZE,
    # Font sizes
    FONT_SIZE_STAT_VALUE, FONT_SIZE_RANK, FONT_SIZE_NAME,
    FONT_SIZE_MONSTER_POWER, FONT_SIZE_MADNESS, FONT_SIZE_HAND_NUMBER,
)


class ImageCompositor:
    """Renders game state as composite images."""

    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}
        self._image_cache: dict[str, Image.Image] = {}

        # Actual board pixel dimensions (set from board_bg.png)
        self._bw: int = BOARD_REF_W
        self._bh: int = BOARD_REF_H
        self._sx: float = 1.0  # horizontal scale
        self._sy: float = 1.0  # vertical scale
        self._detect_board_size()

    # ------------------------------------------------------------------
    # Scaling helpers
    # ------------------------------------------------------------------

    def _detect_board_size(self):
        full = os.path.join(self.base_path, BOARD_BG_PATH)
        if os.path.exists(full):
            try:
                with Image.open(full) as im:
                    self._bw, self._bh = im.size
            except Exception:
                pass
        self._sx = self._bw / BOARD_REF_W
        self._sy = self._bh / BOARD_REF_H

    def _p(self, x: int, y: int) -> tuple[int, int]:
        """Scale a reference point."""
        return int(x * self._sx), int(y * self._sy)

    def _sz(self, w: int, h: int) -> tuple[int, int]:
        """Scale a (width, height) pair."""
        return max(1, int(w * self._sx)), max(1, int(h * self._sy))

    def _box(self, b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """Scale an (x, y, w, h) box."""
        x, y, bw, bh = b
        return (int(x * self._sx), int(y * self._sy),
                max(1, int(bw * self._sx)), max(1, int(bh * self._sy)))

    def _fs(self, ref: int) -> int:
        """Scale a font size."""
        return max(8, int(ref * (self._sx + self._sy) / 2))

    # ------------------------------------------------------------------
    # Asset loading
    # ------------------------------------------------------------------

    def _asset(self, rel: str) -> str:
        return os.path.join(self.base_path, rel)

    def _load(self, path: str, size: tuple = None) -> Optional[Image.Image]:
        key = f"{path}_{size}"
        if key in self._image_cache:
            return self._image_cache[key].copy()
        full = self._asset(path)
        if not os.path.exists(full):
            return None
        im = Image.open(full).convert("RGBA")
        if size:
            im = im.resize(size, Image.Resampling.LANCZOS)
        self._image_cache[key] = im
        return im.copy()

    def _placeholder(self, w: int, h: int,
                     colour=(60, 35, 20, 200), label="") -> Image.Image:
        im = Image.new("RGBA", (w, h), colour)
        if label:
            d = ImageDraw.Draw(im)
            f = self._font(max(8, min(14, w // max(len(label), 1))))
            bb = d.textbbox((0, 0), label, font=f)
            d.text(((w - bb[2] + bb[0]) // 2, (h - bb[3] + bb[1]) // 2),
                   label, fill=(200, 200, 200), font=f)
        return im

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        if size in self._font_cache:
            return self._font_cache[size]
        fp = self._asset(FONT_PATH)
        for path in [fp,
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                f = ImageFont.truetype(path, size)
                self._font_cache[size] = f
                return f
            except (OSError, IOError):
                continue
        f = ImageFont.load_default()
        self._font_cache[size] = f
        return f

    def _card_back(self, w: int, h: int) -> Image.Image:
        return self._load(CARD_BACK_PATH, (w, h)) or \
               self._placeholder(w, h, (60, 35, 20, 200))

    def _card_face(self, cid: str, w: int, h: int) -> Image.Image:
        p = CARD_IMAGE_PATH_TEMPLATE.format(card_id=cid)
        return self._load(p, (w, h)) or \
               self._placeholder(w, h, (50, 30, 50, 230), cid[:12])

    def _monster_img(self, mid: str, w: int, h: int) -> Image.Image:
        p = MONSTER_IMAGE_PATH_TEMPLATE.format(monster_id=mid)
        return self._load(p, (w, h)) or \
               self._placeholder(w, h, (40, 40, 80, 200), mid[:8])

    def _avatar(self, raw: bytes, w: int, h: int) -> Image.Image:
        if raw:
            try:
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
                return im.resize((w, h), Image.Resampling.LANCZOS)
            except Exception:
                pass
        return self._placeholder(w, h, (80, 80, 80, 180), "?")

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _centre_text(draw: ImageDraw.Draw, text: str,
                     box: tuple, font, fill):
        """Draw *text* centred within (x, y, w, h)."""
        bx, by, bw, bh = box
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((bx + (bw - tw) // 2, by + (bh - th) // 2),
                  text, fill=fill, font=font)

    @staticmethod
    def _shadow_text(draw: ImageDraw.Draw, pos: tuple, text: str,
                     font, fill, shadow=(0, 0, 0)):
        x, y = pos
        draw.text((x + 1, y + 1), text, fill=shadow, font=font)
        draw.text((x, y), text, fill=fill, font=font)

    @staticmethod
    def _life_col(life: int, mx: int = 40):
        if life <= mx * 0.3:
            return (255, 50, 50)
        if life <= mx * 0.6:
            return (255, 180, 0)
        return (0, 220, 0)

    @staticmethod
    def _san_col(san: int):
        if san <= 0:
            return (255, 50, 50)
        if san <= 10:
            return (255, 180, 0)
        return (100, 200, 255)

    # ------------------------------------------------------------------
    # Board render
    # ------------------------------------------------------------------

    def render_board(self, gs: GameState, *,
                     resolving_card_id: str = None,
                     resolving_player_is_bottom: bool = True,
                     book_open: bool = False,
                     p1_avatar_bytes: bytes = None,
                     p2_avatar_bytes: bytes = None) -> bytes:

        board = self._load(BOARD_BG_PATH)
        if board is None:
            board = Image.new("RGBA", (self._bw, self._bh), (40, 30, 25, 255))
        if board.size != (self._bw, self._bh):
            board = board.resize((self._bw, self._bh), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(board)

        p1 = gs.player1   # bottom / main
        p2 = gs.player2   # top / challenger / bot

        vf = self._font(self._fs(FONT_SIZE_STAT_VALUE))
        rf = self._font(self._fs(FONT_SIZE_RANK))
        nf = self._font(self._fs(FONT_SIZE_NAME))
        mf = self._font(self._fs(FONT_SIZE_MADNESS))
        pf = self._font(self._fs(FONT_SIZE_MONSTER_POWER))

        # ====== TOP PLAYER (p2) ======

        # Card backs in top slots
        for i in range(min(len(p2.hand), len(TOP_CARD_SLOTS))):
            bx, by, bw, bh = self._box(TOP_CARD_SLOTS[i])
            cb = self._card_back(bw, bh)
            board.paste(cb, (bx, by), cb)

        # Life number
        self._centre_text(draw, str(p2.life),
                          self._box(TOP_LIFE_BOX), vf,
                          self._life_col(p2.life, p2.max_life))

        # Sanity number
        self._centre_text(draw, str(p2.sanity),
                          self._box(TOP_SANITY_BOX), vf,
                          self._san_col(p2.sanity))

        # Avatar
        ab = self._box(TOP_AVATAR_BOX)
        av = self._avatar(p2_avatar_bytes, ab[2], ab[3])
        board.paste(av, (ab[0], ab[1]), av)

        # Name
        self._shadow_text(draw, self._p(*TOP_NAME_POS),
                          p2.display_name[:14], nf, (200, 200, 200))

        # Rank (right side of upper bar)
        self._shadow_text(draw, self._p(*TOP_RANK_POS),
                          f"{p2.rank}. {p2.rank_title}", rf,
                          (200, 180, 130))

        # Stat numbers (no symbols — baked in)
        self._shadow_text(draw, self._p(*TOP_TAINT_NUM_POS),
                          str(p2.taint), vf, (200, 180, 0))
        self._shadow_text(draw, self._p(*TOP_ARCANE_NUM_POS),
                          str(p2.arcane), vf, (100, 200, 100))
        self._shadow_text(draw, self._p(*TOP_ELDER_NUM_POS),
                          str(p2.elder_defense), vf, (220, 50, 50))

        if p2.invulnerable:
            self._shadow_text(draw, self._p(*TOP_INVULN_POS),
                              "INV", mf, (0, 200, 255))
        if p2.madness:
            self._shadow_text(draw, self._p(*TOP_MADNESS_POS),
                              f"* {p2.madness}", mf, (255, 100, 100))

        # ====== CENTRE ======

        # Book
        if book_open:
            bsz = self._sz(*BOOK_OPEN_SIZE)
            bk = self._load(BOOK_OPEN_PATH, bsz)
            if bk is None:
                bk = self._placeholder(*bsz, (120, 100, 50, 220), "OPEN")
            board.paste(bk, self._p(*BOOK_OPEN_POS), bk)
        else:
            bsz = self._sz(*BOOK_CLOSED_SIZE)
            bk = self._load(BOOK_CLOSED_PATH, bsz)
            if bk is None:
                bk = self._placeholder(*bsz, (100, 80, 40, 220))
            board.paste(bk, self._p(*BOOK_CLOSED_POS), bk)

        # Resolving card (enlarged)
        if resolving_card_id:
            if resolving_player_is_bottom:
                csz = self._sz(*CARD_DISPLAY_RIGHT_SIZE)
                cpos = self._p(*CARD_DISPLAY_RIGHT_POS)
            else:
                csz = self._sz(*CARD_DISPLAY_LEFT_SIZE)
                cpos = self._p(*CARD_DISPLAY_LEFT_POS)
            ci = self._card_face(resolving_card_id, *csz)
            board.paste(ci, cpos, ci)

        # Monsters
        if p1.monster:
            msz = self._sz(*BOTTOM_MONSTER_SIZE)
            mi = self._monster_img(p1.monster.monster_id, *msz)
            mp = self._p(*BOTTOM_MONSTER_POS)
            board.paste(mi, mp, mi)
            px = mp[0] + msz[0] // 2 - 8
            py = mp[1] + msz[1] - self._fs(FONT_SIZE_MONSTER_POWER) - 4
            self._shadow_text(draw, (px, py), str(p1.monster.power),
                              pf, (255, 80, 80))

        if p2.monster:
            msz = self._sz(*TOP_MONSTER_SIZE)
            mi = self._monster_img(p2.monster.monster_id, *msz)
            mp = self._p(*TOP_MONSTER_POS)
            board.paste(mi, mp, mi)
            px = mp[0] + msz[0] // 2 - 8
            py = mp[1] + msz[1] - self._fs(FONT_SIZE_MONSTER_POWER) - 4
            self._shadow_text(draw, (px, py), str(p2.monster.power),
                              pf, (255, 80, 80))

        # ====== BOTTOM PLAYER (p1) ======

        # Avatar
        ab = self._box(BOTTOM_AVATAR_BOX)
        av = self._avatar(p1_avatar_bytes, ab[2], ab[3])
        board.paste(av, (ab[0], ab[1]), av)

        # Name
        self._shadow_text(draw, self._p(*BOTTOM_NAME_POS),
                          p1.display_name[:14], nf, (200, 200, 200))

        # Life / Sanity
        self._centre_text(draw, str(p1.life),
                          self._box(BOTTOM_LIFE_BOX), vf,
                          self._life_col(p1.life, p1.max_life))
        self._centre_text(draw, str(p1.sanity),
                          self._box(BOTTOM_SANITY_BOX), vf,
                          self._san_col(p1.sanity))

        # Rank (left side of lower bar)
        self._shadow_text(draw, self._p(*BOTTOM_RANK_POS),
                          f"{p1.rank}. {p1.rank_title}", rf,
                          (200, 180, 130))

        # Stats
        self._shadow_text(draw, self._p(*BOTTOM_TAINT_NUM_POS),
                          str(p1.taint), vf, (200, 180, 0))
        self._shadow_text(draw, self._p(*BOTTOM_ARCANE_NUM_POS),
                          str(p1.arcane), vf, (100, 200, 100))
        self._shadow_text(draw, self._p(*BOTTOM_ELDER_NUM_POS),
                          str(p1.elder_defense), vf, (220, 50, 50))

        if p1.invulnerable:
            self._shadow_text(draw, self._p(*BOTTOM_INVULN_POS),
                              "INV", mf, (0, 200, 255))
        if p1.madness:
            self._shadow_text(draw, self._p(*BOTTOM_MADNESS_POS),
                              f"* {p1.madness}", mf, (255, 100, 100))

        # Card backs in bottom slots
        for i in range(min(len(p1.hand), len(BOTTOM_CARD_SLOTS))):
            bx, by, bw, bh = self._box(BOTTOM_CARD_SLOTS[i])
            cb = self._card_back(bw, bh)
            board.paste(cb, (bx, by), cb)

        # --- serialise ---
        buf = io.BytesIO()
        board.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Hand view (ephemeral, face-up)
    # ------------------------------------------------------------------

    def render_hand(self, player: Player) -> bytes:
        if not player.hand:
            im = Image.new("RGBA", (600, 200), (18, 10, 8, 255))
            d = ImageDraw.Draw(im)
            d.rectangle([(2, 2), (597, 197)], outline=(80, 55, 30, 200), width=2)
            d.text((180, 80), "No cards in hand",
                   fill=(160, 140, 110), font=self._font(20))
        else:
            # Larger cards for legibility
            cw, ch = 200, 280
            sp = 14
            pad = 22
            tw = len(player.hand) * (cw + sp) - sp + pad * 2
            th = ch + 54 + pad * 2

            # Rich dark background — load file or build one
            bg = self._load(HAND_BG_PATH, (tw, th))
            if bg is None:
                bg = Image.new("RGBA", (tw, th), (14, 8, 5, 255))
                d_bg = ImageDraw.Draw(bg)
                # Outer border
                d_bg.rectangle([(0, 0), (tw - 1, th - 1)],
                                outline=(90, 60, 30, 220), width=3)
                # Inner subtle border
                d_bg.rectangle([(5, 5), (tw - 6, th - 6)],
                                outline=(55, 35, 18, 150), width=1)
            im = bg.copy() if bg else bg
            d = ImageDraw.Draw(im)

            nf = self._font(self._fs(FONT_SIZE_HAND_NUMBER))
            desc_f = self._font(max(9, self._fs(11)))

            for i, card in enumerate(player.hand):
                ci = self._card_face(card.card_id, cw, ch)
                x = pad + i * (cw + sp)
                im.paste(ci, (x, pad), ci)

                # Card number label
                lbl = f"[{i + 1}]"
                bb = d.textbbox((0, 0), lbl, font=nf)
                lx = x + (cw - (bb[2] - bb[0])) // 2
                self._shadow_text(d, (lx, pad + ch + 8), lbl, nf,
                                  (210, 190, 80))

        buf = io.BytesIO()
        im.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def render_menu(self) -> bytes:
        im = self._load(MENU_BG_PATH)
        if im is None:
            im = Image.new("RGBA", (self._bw, self._bh), (40, 20, 15, 255))
            d = ImageDraw.Draw(im)
            d.text(self._p(200, 30), "NECRONOMICON",
                   fill=(180, 150, 100), font=self._font(self._fs(32)))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # End screen  (supports win, loss, and draw)
    # ------------------------------------------------------------------

    def render_end_screen(self, player: Player, xp_data: dict,
                          rank_data: dict, *,
                          is_draw: bool = False,
                          is_loss: bool = False) -> bytes:
        """Render end-of-game results.

        *player*   — the human whose perspective we are showing.
        *is_loss*  — True when the human lost (e.g. forfeit); no XP gained.
        """
        bg = self._load(END_SCREEN_BG_PATH)
        if bg is None:
            bg = Image.new("RGBA", (self._bw, self._bh), (40, 25, 15, 255))
        if bg.size != (self._bw, self._bh):
            bg = bg.resize((self._bw, self._bh), Image.Resampling.LANCZOS)

        d = ImageDraw.Draw(bg)
        tf = self._font(self._fs(32))
        lf = self._font(self._fs(24))
        sf = self._font(self._fs(18))
        smf = self._font(self._fs(14))

        if is_draw:
            d.text(self._p(340, 20), "DRAW", fill=(200, 200, 100), font=tf)
        elif is_loss:
            d.text(self._p(300, 20), "DEFEAT", fill=(200, 50, 50), font=tf)
        else:
            d.text(self._p(180, 20), "ROUND SCORES and RANK",
                   fill=(0, 200, 100), font=tf)

        y = 80;  lh = 32

        d.text(self._p(60, y), "Previous Rank", fill=(200, 200, 200), font=sf)
        d.text(self._p(550, y),
               f"{rank_data['old_rank']}. {rank_data['old_rank_name']}",
               fill=(200, 200, 200), font=sf)
        y += lh

        lv = xp_data.get("remaining_life", 0)
        d.text(self._p(60, y), "Remaining Life", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(lv),
               fill=(0, 200, 0) if lv > 0 else (200, 0, 0), font=sf)
        y += lh

        sv = xp_data.get("remaining_sanity", 0)
        d.text(self._p(60, y), "Remaining Sanity", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(sv),
               fill=(0, 150, 255) if sv > 0 else (200, 0, 0), font=sf)
        y += lh

        d.text(self._p(60, y), "Damage Inflicted", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(xp_data.get("damage_dealt", 0)),
               fill=(200, 200, 200), font=sf)
        d.text(self._p(660, y + 2),
               f"+ {xp_data.get('best_attack', 0)} best",
               fill=(180, 180, 180), font=smf)
        y += lh

        d.text(self._p(60, y), "-  Damage Received", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(xp_data.get("damage_received", 0)),
               fill=(200, 50, 50), font=sf)
        y += lh + 10

        lx1, ly = self._p(60, y);  lx2, _ = self._p(700, y)
        d.line([(lx1, ly), (lx2, ly)], fill=(150, 130, 100), width=2)
        y += 15

        total = xp_data.get("total", 0) if not is_loss else 0
        d.text(self._p(60, y), "XP for this Round", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(total),
               fill=(200, 200, 200) if not is_loss else (150, 150, 150),
               font=sf)
        y += lh

        prev = rank_data.get("total_xp", 0) - (total if not is_loss else 0)
        d.text(self._p(60, y), "Previous Total", fill=(200, 200, 200), font=sf)
        d.text(self._p(600, y), str(max(0, prev)), fill=(200, 200, 200), font=sf)
        y += lh

        d.text(self._p(60, y), "Current Total", fill=(0, 200, 100), font=lf)
        d.text(self._p(580, y), str(rank_data.get("total_xp", 0)),
               fill=(0, 200, 100), font=lf)
        y += lh + 20

        d.text(self._p(60, y), "Current Rank", fill=(0, 200, 100), font=lf)
        d.text(self._p(450, y),
               f"{rank_data['new_rank']}. {rank_data['new_rank_name']}",
               fill=(0, 200, 100), font=lf)

        if rank_data.get("ranked_up") and not is_loss:
            d.text(self._p(300, y + 40), "RANK UP!",
                   fill=(255, 215, 0), font=tf)

        buf = io.BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

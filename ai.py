"""Necronomicon Card Game - Bot AI"""

import random
from models import Player, GameState
from cards import Card


class BotAI:
    """AI for bot opponents with tiered intelligence."""

    def __init__(self, difficulty: int = 1):
        """
        difficulty: 1-3
        1 = Random/simple (Ranks 1-7)
        2 = Tactical (Ranks 8-14)
        3 = Strategic (Ranks 15-20)
        """
        self.difficulty = min(3, max(1, difficulty))

    @staticmethod
    def get_difficulty_for_rank(rank: int) -> int:
        if rank <= 7:
            return 1
        elif rank <= 14:
            return 2
        else:
            return 3

    def choose_action(self, game_state: GameState) -> tuple[str, int]:
        """
        Choose an action for the bot.
        Returns: ("play", card_index) or ("discard", card_index)
        """
        bot = game_state.current_player
        opponent = game_state.get_opponent(bot)

        if not bot.hand:
            return ("play", 0)  # Will be caught as invalid

        if self.difficulty == 1:
            return self._choose_simple(bot, opponent)
        elif self.difficulty == 2:
            return self._choose_tactical(bot, opponent)
        else:
            return self._choose_strategic(bot, opponent)

    def _choose_simple(self, bot: Player, opponent: Player) -> tuple[str, int]:
        """Simple AI: play a random affordable card, occasionally discard for sanity."""
        playable = [(i, c) for i, c in enumerate(bot.hand)
                    if bot.can_play_card(i)[0]]

        # If low sanity, sometimes discard a high-cost card
        if bot.sanity <= 5 and random.random() < 0.4:
            best_discard = max(range(len(bot.hand)),
                               key=lambda i: bot.hand[i].sanity_cost)
            if bot.hand[best_discard].sanity_cost > 0:
                return ("discard", best_discard)

        if playable:
            idx, card = random.choice(playable)
            return ("play", idx)

        # Can't play anything, discard
        return ("discard", random.randint(0, len(bot.hand) - 1))

    def _choose_tactical(self, bot: Player, opponent: Player) -> tuple[str, int]:
        """Tactical AI: scores cards based on game state."""
        playable = [(i, c) for i, c in enumerate(bot.hand)
                    if bot.can_play_card(i)[0]]

        if not playable:
            return self._best_discard(bot)

        # Check if we urgently need sanity
        if bot.sanity <= 0 and bot.madness:
            # Try to play sanity recovery
            for i, c in playable:
                if c.card_id in ("arkham_asylum", "miskatonic_university",
                                 "dawn_of_a_new_day"):
                    return ("play", i)
            # Discard highest sanity cost card
            return self._best_discard(bot)

        # Check if we need healing
        if bot.life <= 15:
            for i, c in playable:
                if c.card_id in ("essence_of_the_soul", "mi_go_surgery",
                                 "discreet_doctor", "sacrificial_lamb"):
                    return ("play", i)

        # Check if opponent has a dangerous monster
        if opponent.monster and opponent.monster.power >= 4:
            for i, c in playable:
                if c.card_id in ("sacrificial_lamb", "powder_of_ibn_ghazi",
                                 "shoggoth"):
                    return ("play", i)

        # Score remaining cards
        scored = []
        for i, c in playable:
            score = self._score_card_tactical(c, bot, opponent)
            scored.append((score, i, c))

        scored.sort(reverse=True)

        # Sometimes pick second-best for unpredictability
        if len(scored) > 1 and random.random() < 0.2:
            return ("play", scored[1][1])

        return ("play", scored[0][1])

    def _choose_strategic(self, bot: Player, opponent: Player) -> tuple[str, int]:
        """Strategic AI: deep evaluation of game state."""
        playable = [(i, c) for i, c in enumerate(bot.hand)
                    if bot.can_play_card(i)[0]]

        if not playable:
            return self._best_discard(bot)

        # Critical sanity recovery
        if bot.sanity <= 0 and bot.madness:
            for i, c in playable:
                if c.card_id in ("arkham_asylum", "miskatonic_university",
                                 "dawn_of_a_new_day"):
                    return ("play", i)
            # Check if discarding is better
            best_disc_idx = max(range(len(bot.hand)),
                                key=lambda i: bot.hand[i].sanity_cost)
            if bot.hand[best_disc_idx].sanity_cost >= 3:
                return ("discard", best_disc_idx)

        # Taint management
        if bot.taint >= 4:
            for i, c in playable:
                if c.card_id in ("blessing_of_hastur", "elder_thing",
                                 "miskatonic_university", "professor_armitage",
                                 "dawn_of_a_new_day"):
                    return ("play", i)

        # Check for lethal
        for i, c in playable:
            estimated_dmg = self._estimate_damage(c, bot, opponent)
            if estimated_dmg >= opponent.life:
                return ("play", i)

        # Opponent has invulnerability — dispel it
        if opponent.invulnerable:
            for i, c in playable:
                if c.card_id in ("dispel", "dawn_of_a_new_day"):
                    return ("play", i)
            # Or use piercing attacks
            for i, c in playable:
                if c.card_id in ("blast_em", "tommy_gun", "raid"):
                    return ("play", i)

        # Monster management
        if opponent.monster and opponent.monster.power >= 5 and not bot.monster:
            for i, c in playable:
                if c.card_id in ("sacrificial_lamb", "powder_of_ibn_ghazi",
                                 "shoggoth"):
                    return ("play", i)

        # Build arcane if safe
        if bot.life > 25 and bot.sanity > 10:
            for i, c in playable:
                if c.card_id in ("unaussprechlichen_kulten", "pnakotic_manuscripts"):
                    return ("play", i)

        # Score all options
        scored = []
        for i, c in playable:
            score = self._score_card_strategic(c, bot, opponent)
            scored.append((score, i, c))
        scored.sort(reverse=True)

        return ("play", scored[0][1])

    def _score_card_tactical(self, card: Card, bot: Player, opponent: Player) -> float:
        """Score a card for tactical AI."""
        score = 0.0

        # Damage cards
        damage_cards = {
            "blast_em": 3, "tommy_gun": 5, "raid": 7, "mind_burn": 7 + bot.arcane,
            "dark_ritual": 10 + bot.arcane, "dark_young_charge": 14 + bot.arcane,
            "from_beyond": 8 + bot.arcane, "hound_of_tindalos": 12 + bot.arcane,
            "rise_of_the_deep_ones": 10 + bot.arcane,
        }

        if card.card_id in damage_cards:
            score += damage_cards[card.card_id] * 1.5
            # Bonus if opponent is low
            if opponent.life <= damage_cards[card.card_id]:
                score += 50  # Lethal!

        # Healing
        healing_cards = {"discreet_doctor": 4, "mi_go_surgery": 7,
                         "essence_of_the_soul": 9, "sacrificial_lamb": 5}
        if card.card_id in healing_cards:
            if bot.life <= 20:
                score += healing_cards[card.card_id] * 2
            else:
                score += healing_cards[card.card_id] * 0.5

        # Monster summons
        if card.card_id in ("shoggoth", "dimensional_shambler", "byakhee",
                            "elder_thing", "black_goat_of_the_woods"):
            score += 8

        # Taint application
        if card.card_id in ("curse_of_cthulhu", "king_in_yellow",
                            "blessing_of_hastur"):
            score += opponent.taint * 2 + 5  # More valuable when they already have taint

        # Sanity recovery
        if card.card_id == "arkham_asylum":
            score += max(0, 15 - bot.sanity) * 1.5

        # Penalize high sanity cost when low
        if bot.sanity <= 10:
            score -= card.sanity_cost * 3

        return score

    def _score_card_strategic(self, card: Card, bot: Player, opponent: Player) -> float:
        """Score a card for strategic AI."""
        score = self._score_card_tactical(card, bot, opponent)

        # Strategic adjustments
        # Value arcane buildup more
        if card.card_id in ("pnakotic_manuscripts", "unaussprechlichen_kulten"):
            score += bot.arcane * 0.5 + 5  # More value when we can capitalize

        # Value elder defense when opponent has arcane
        if card.card_id == "elder_sign":
            if opponent.arcane > 3:
                score += 15

        # Blackmail is more valuable when opponent has few cards
        if card.card_id == "blackmail":
            if len(opponent.hand) <= 3:
                score += 8

        # Betrayed is power-dependent
        if card.card_id == "betrayed":
            if opponent.monster:
                score += opponent.monster.power * 3

        # City of R'lyeh / Yog-Sothoth — check opponent sanity state
        if card.card_id == "city_of_rlyeh":
            if opponent.is_insane:
                score += 30  # Massive damage
            else:
                score += 12

        if card.card_id == "yog_sothoth":
            if opponent.sanity > 15:
                score += opponent.sanity * 1.5

        return score

    def _best_discard(self, bot: Player) -> tuple[str, int]:
        """Choose the best card to discard."""
        if not bot.hand:
            return ("discard", 0)
        best_idx = max(range(len(bot.hand)),
                       key=lambda i: bot.hand[i].sanity_cost)
        return ("discard", best_idx)

    def _estimate_damage(self, card: Card, bot: Player, opponent: Player) -> int:
        """Rough estimate of damage a card will do."""
        damage_map = {
            "blast_em": 3,
            "tommy_gun": 5,
            "raid": 7,
            "mind_burn": max(0, 7 + bot.arcane - (0 if True else opponent.elder_defense)),
            "dark_ritual": max(0, 10 + bot.arcane - opponent.elder_defense),
            "dark_young_charge": max(0, 14 + bot.arcane - opponent.elder_defense),
            "from_beyond": max(0, 8 + bot.arcane - opponent.elder_defense),
            "hound_of_tindalos": 12 + bot.arcane,
            "rise_of_the_deep_ones": max(0, 10 + bot.arcane - opponent.elder_defense),
            "black_goat_of_the_woods": max(0, 8 + bot.arcane - opponent.elder_defense),
            "city_of_rlyeh": (20 + bot.arcane) if opponent.is_insane else 0,
            "yog_sothoth": max(0, opponent.sanity - opponent.elder_defense) if opponent.sanity > 0 else 0,
            "betrayed": (opponent.monster.power + bot.arcane - opponent.elder_defense) if opponent.monster else 0,
        }
        return damage_map.get(card.card_id, 0)

    def choose_blackmail_discard(self, bot: Player) -> int:
        """When bot is forced to discard from blackmail, choose the least useful card."""
        if not bot.hand:
            return 0
        # Discard lowest value card (simple heuristic: lowest sanity cost = least impactful)
        return min(range(len(bot.hand)),
                   key=lambda i: bot.hand[i].sanity_cost)

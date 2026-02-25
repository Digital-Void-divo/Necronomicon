"""Necronomicon Card Game - Core Data Models"""

import random
from dataclasses import dataclass, field
from typing import Optional
from config import (
    BASE_LIFE, LIFE_PER_RANK, MAX_LIFE_CAP, STARTING_SANITY,
    DEFAULT_HAND_SIZE, AGORAPHOBIA_HAND_SIZE, MIN_TAINT,
    MIN_ARCANE, MIN_ELDER_DEFENSE, MADNESS_TYPES, MAX_RANK
)


@dataclass
class Monster:
    """A summoned monster on the field."""
    name: str
    monster_id: str
    power: int
    traits: list = field(default_factory=list)
    # Traits: "unblockable", "piercing" (ignores elder defense),
    #         "byakhee_only" (only blocked by byakhee),
    #         "destroy_on_summon" (destroys opponent creature when summoned)

    def has_trait(self, trait: str) -> bool:
        return trait in self.traits


@dataclass
class Card:
    """A card in the game."""
    name: str
    card_id: str
    rank_required: int
    sanity_cost: int
    life_cost: int = 0
    description: str = ""

    def get_image_name(self) -> str:
        return f"{self.card_id}.png"


class Player:
    """Represents a player in the game."""

    def __init__(self, user_id: str, display_name: str, avatar_url: str = "",
                 rank: int = 1, is_bot: bool = False):
        self.user_id = user_id
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.rank = rank
        self.is_bot = is_bot

        # Stats
        self.life = self._calculate_starting_life()
        self.max_life = self.life
        self.sanity = STARTING_SANITY
        self.taint = 0
        self.arcane = 0
        self.elder_defense = 0
        self.invulnerable = False
        self.madness: Optional[str] = None

        # Cards
        self.deck: list[Card] = []
        self.hand: list[Card] = []
        self.hand_size = DEFAULT_HAND_SIZE

        # Monster
        self.monster: Optional[Monster] = None

        # Combat tracking for XP
        self.damage_dealt = 0
        self.damage_received = 0
        self.best_attack = 0

    def _calculate_starting_life(self) -> int:
        life = BASE_LIFE + (self.rank - 1) * LIFE_PER_RANK
        return min(life, MAX_LIFE_CAP)

    def override_starting_stats(self, life: int = None, sanity: int = None,
                                taint: int = None, arcane: int = None,
                                elder_defense: int = None):
        """Override starting stats for challenge mode or campaign enemies."""
        if life is not None:
            self.life = life
            self.max_life = life
        if sanity is not None:
            self.sanity = sanity
        if taint is not None:
            self.taint = max(taint, MIN_TAINT)
        if arcane is not None:
            self.arcane = max(arcane, MIN_ARCANE)
        if elder_defense is not None:
            self.elder_defense = max(elder_defense, MIN_ELDER_DEFENSE)

    def build_deck(self, available_cards: list[Card]):
        """Build deck from cards available at player's rank."""
        self.deck = [c for c in available_cards if c.rank_required <= self.rank]
        random.shuffle(self.deck)

    def build_deck_from_list(self, cards: list[Card]):
        """Build deck from a specific card list (for challenges/campaign enemies)."""
        self.deck = list(cards)
        random.shuffle(self.deck)

    def draw_initial_hand(self):
        """Draw the starting hand."""
        for _ in range(self.hand_size):
            self._draw_card()

    def _draw_card(self) -> Optional[Card]:
        """Draw a single card from deck to hand."""
        if not self.deck:
            return None
        card = self.deck.pop(0)
        self.hand.append(card)
        return card

    def replace_card(self, index: int) -> Optional[Card]:
        """Remove card at index from hand and draw a replacement."""
        if 0 <= index < len(self.hand):
            self.hand.pop(index)
            return self._draw_card()
        return None

    def discard_card(self, index: int) -> Optional[Card]:
        """Discard a card and gain sanity equal to its sanity cost."""
        if 0 <= index < len(self.hand):
            card = self.hand[index]
            sanity_gain = card.sanity_cost
            self.sanity += sanity_gain
            self.hand.pop(index)
            self._draw_card()
            # Check if madness should be removed
            self._check_madness_removal()
            return card
        return None

    def can_play_card(self, index: int) -> tuple[bool, str]:
        """Check if player can afford to play a card."""
        if index < 0 or index >= len(self.hand):
            return False, "Invalid card index."
        card = self.hand[index]
        if card.sanity_cost > 0 and self.sanity < card.sanity_cost:
            # Players can go negative on sanity from cost
            pass  # Sanity cost is always payable
        if card.life_cost > 0 and self.life <= card.life_cost:
            return False, f"Not enough life. Need {card.life_cost}, have {self.life}."
        return True, ""

    def pay_card_cost(self, card: Card):
        """Pay the costs of playing a card."""
        self.sanity -= card.sanity_cost
        self.life -= card.life_cost
        self._check_madness()

    def take_damage(self, amount: int, ignore_elder: bool = False,
                    ignore_invulnerable: bool = False, is_taint: bool = False,
                    is_self_damage: bool = False, is_direct_adjustment: bool = False):
        """Apply damage to the player with proper reductions."""
        if amount <= 0:
            return 0

        actual_damage = amount

        # Elder Defense reduction (doesn't protect against taint, self-damage, direct adjustments)
        if not ignore_elder and not is_taint and not is_self_damage and not is_direct_adjustment:
            actual_damage = max(0, actual_damage - self.elder_defense)

        # Invulnerability check (doesn't protect against taint, self-damage, direct adjustments)
        if not ignore_invulnerable and not is_taint and not is_self_damage and not is_direct_adjustment:
            if self.invulnerable and actual_damage > 0:
                self.invulnerable = False
                return 0

        if actual_damage > 0:
            self.life -= actual_damage
            self.damage_received += actual_damage

        return actual_damage

    def deal_damage_to(self, target: 'Player', amount: int, **kwargs) -> int:
        """Deal damage to another player, tracking stats."""
        actual = target.take_damage(amount, **kwargs)
        self.damage_dealt += actual
        if actual > self.best_attack:
            self.best_attack = actual
        return actual

    def adjust_life(self, amount: int):
        """Direct life adjustment (gain or loss). Not affected by Elder Defense."""
        self.life += amount

    def gain_life(self, amount: int):
        """Gain life."""
        self.life += amount

    def modify_sanity(self, amount: int):
        """Modify sanity by amount (positive = gain, negative = loss)."""
        self.sanity += amount
        if amount < 0:
            self._check_madness()
        elif amount > 0:
            self._check_madness_removal()

    def set_sanity(self, value: int):
        """Set sanity to a specific value."""
        old = self.sanity
        self.sanity = value
        if value <= 0 and old > 0:
            self._check_madness()
        elif value > 0 and old <= 0:
            self._check_madness_removal()

    def modify_taint(self, amount: int):
        """Modify taint (positive = gain, negative = loss)."""
        self.taint = max(MIN_TAINT, self.taint + amount)

    def set_taint(self, value: int):
        """Set taint to a specific value."""
        self.taint = max(MIN_TAINT, value)

    def modify_arcane(self, amount: int):
        """Modify arcane power."""
        self.arcane = max(MIN_ARCANE, self.arcane + amount)

    def set_arcane(self, value: int):
        """Set arcane to a specific value."""
        self.arcane = max(MIN_ARCANE, value)

    def modify_elder_defense(self, amount: int):
        """Modify elder defense."""
        self.elder_defense = max(MIN_ELDER_DEFENSE, self.elder_defense + amount)

    def set_elder_defense(self, value: int):
        """Set elder defense to a specific value."""
        self.elder_defense = max(MIN_ELDER_DEFENSE, value)

    def summon_monster(self, monster: Monster) -> list[str]:
        """Summon a monster, replacing any existing one."""
        messages = []

        # Xenophobia check - monster is immediately destroyed
        if self.madness == "Xenophobia":
            messages.append(f"🤯 {self.display_name}'s Xenophobia destroys {monster.name} immediately!")
            return messages

        # Replace existing monster
        if self.monster:
            messages.append(f"{self.display_name}'s {self.monster.name} is replaced.")
        self.monster = monster
        messages.append(f"{self.display_name} summons {monster.name} (Power: {monster.power})!")
        return messages

    def remove_monster(self) -> Optional[Monster]:
        """Remove the player's monster from play."""
        old = self.monster
        self.monster = None
        return old

    def _check_madness(self):
        """Check if player should gain a madness."""
        if self.sanity <= 0 and self.madness is None:
            self.madness = random.choice(MADNESS_TYPES)

    def _check_madness_removal(self):
        """Check if madness should be removed."""
        if self.sanity > 0 and self.madness is not None:
            self.madness = None

    def apply_xenophobia(self) -> list[str]:
        """Apply Xenophobia effect: destroy any existing monster."""
        messages = []
        if self.monster:
            messages.append(f"🤯 Xenophobia destroys {self.display_name}'s {self.monster.name}!")
            self.monster = None
        return messages

    def apply_agoraphobia(self) -> list[str]:
        """Apply Agoraphobia: reduce hand to 2 by random discard."""
        messages = []
        self.hand_size = AGORAPHOBIA_HAND_SIZE
        while len(self.hand) > AGORAPHOBIA_HAND_SIZE:
            idx = random.randint(0, len(self.hand) - 1)
            discarded = self.hand.pop(idx)
            messages.append(f"📖 Agoraphobia forces {self.display_name} to discard {discarded.name}.")
        return messages

    def apply_end_of_turn_draw(self) -> list[str]:
        """At end of turn, draw up to hand size if under."""
        messages = []
        while len(self.hand) < self.hand_size and self.deck:
            card = self._draw_card()
            if card:
                messages.append(f"{self.display_name} draws a card.")
        return messages

    @property
    def is_alive(self) -> bool:
        return self.life > 0

    @property
    def is_insane(self) -> bool:
        return self.sanity <= 0

    @property
    def has_cards(self) -> bool:
        return len(self.hand) > 0 or len(self.deck) > 0

    @property
    def rank_title(self) -> str:
        from config import RANK_NAMES
        return RANK_NAMES.get(self.rank, f"Rank {self.rank}")


class GameState:
    """Manages the state of a single game."""

    def __init__(self, player1: Player, player2: Player):
        self.player1 = player1  # Bottom player (initiator)
        self.player2 = player2  # Top player (challenger or bot)
        self.current_player = player1
        self.turn_number = 0
        self.game_over = False
        self.winner: Optional[Player] = None
        self.is_draw = False
        self.log: list[str] = []
        self.last_played_card: Optional[Card] = None
        self.last_card_player: Optional[Player] = None
        self.resolving_card = False
        self.game_id: str = ""

    @property
    def waiting_player(self) -> Player:
        return self.player2 if self.current_player == self.player1 else self.player1

    def get_opponent(self, player: Player) -> Player:
        return self.player2 if player == self.player1 else self.player1

    def switch_turn(self):
        """Switch to the other player's turn."""
        self.current_player = self.waiting_player
        self.turn_number += 1

    def check_game_over(self) -> list[str]:
        """Check win/loss/draw conditions."""
        messages = []

        if not self.player1.is_alive and not self.player2.is_alive:
            self.game_over = True
            self.is_draw = True
            messages.append("💀 Both players have fallen! It's a draw!")
        elif not self.player1.is_alive:
            self.game_over = True
            self.winner = self.player2
            messages.append(f"💀 {self.player1.display_name} has been defeated!")
            messages.append(f"🏆 {self.player2.display_name} wins!")
        elif not self.player2.is_alive:
            self.game_over = True
            self.winner = self.player1
            messages.append(f"💀 {self.player2.display_name} has been defeated!")
            messages.append(f"🏆 {self.player1.display_name} wins!")
        elif not self.player1.has_cards and not self.player2.has_cards:
            if len(self.player1.hand) == 0 and len(self.player2.hand) == 0:
                self.game_over = True
                self.is_draw = True
                messages.append("📚 Both players have exhausted their decks! It's a draw!")

        return messages

    def add_log(self, message: str):
        self.log.append(message)

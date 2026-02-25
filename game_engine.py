"""Necronomicon Card Game - Game Engine"""

from typing import Optional
from models import Player, GameState, Monster
from cards import execute_card, CARD_EFFECTS


class TurnResult:
    """Result of processing a turn action."""
    def __init__(self):
        self.messages: list[str] = []
        self.card_played: Optional[object] = None
        self.card_discarded: Optional[object] = None
        self.was_discard: bool = False
        self.game_over: bool = False
        self.requires_blackmail_choice: bool = False
        self.monster_combat_occurred: bool = False
        self.monster_combat_messages: list[str] = []
        self.end_of_turn_messages: list[str] = []
        self.game_over_messages: list[str] = []


class GameEngine:
    """Manages the flow of a game."""

    def __init__(self, game_state: GameState):
        self.state = game_state

    def play_card(self, card_index: int) -> TurnResult:
        """Current player plays a card from their hand."""
        result = TurnResult()
        player = self.state.current_player
        opponent = self.state.get_opponent(player)

        # Validate
        if card_index < 0 or card_index >= len(player.hand):
            result.messages.append("Invalid card selection.")
            return result

        card = player.hand[card_index]

        # Check if player can afford the card
        can_play, reason = player.can_play_card(card_index)
        if not can_play:
            result.messages.append(reason)
            return result

        # Pay costs
        player.pay_card_cost(card)
        result.messages.append(f"⚡ {player.display_name} plays **{card.name}**!")
        if card.sanity_cost > 0:
            result.messages.append(f"  Sanity cost: -{card.sanity_cost} (Sanity: {player.sanity})")

        # Track the played card for display
        result.card_played = card
        self.state.last_played_card = card
        self.state.last_card_player = player

        # Execute card effect
        effect_messages = execute_card(card, player, opponent)

        # Check for blackmail choice
        if "BLACKMAIL_CHOICE" in effect_messages:
            effect_messages.remove("BLACKMAIL_CHOICE")
            result.requires_blackmail_choice = True
            result.messages.append(f"{opponent.display_name} must choose a card to discard!")

        result.messages.extend(effect_messages)

        # Remove played card from hand and draw replacement
        player.replace_card(card_index)

        # Check madness effects after card play
        madness_msgs = self._check_madness_on_play(player)
        result.messages.extend(madness_msgs)

        # If not waiting for blackmail, resolve end of turn
        if not result.requires_blackmail_choice:
            self._resolve_end_of_turn(player, opponent, result)

        return result

    def discard_card(self, card_index: int) -> TurnResult:
        """Current player discards a card to gain sanity."""
        result = TurnResult()
        player = self.state.current_player
        opponent = self.state.get_opponent(player)

        if card_index < 0 or card_index >= len(player.hand):
            result.messages.append("Invalid card selection.")
            return result

        card = player.hand[card_index]
        result.card_discarded = card
        result.was_discard = True

        sanity_gain = card.sanity_cost
        player.discard_card(card_index)

        result.messages.append(f"📖 {player.display_name} discards **{card.name}**.")
        if sanity_gain > 0:
            result.messages.append(f"  Gains {sanity_gain} Sanity. (Sanity: {player.sanity})")
        else:
            result.messages.append(f"  No Sanity gained (0 cost card).")

        # Resolve end of turn
        self._resolve_end_of_turn(player, opponent, result)

        return result

    def resolve_blackmail_choice(self, opponent_card_index: int) -> TurnResult:
        """Resolve the opponent's blackmail discard choice."""
        result = TurnResult()
        player = self.state.current_player
        opponent = self.state.get_opponent(player)

        if opponent_card_index < 0 or opponent_card_index >= len(opponent.hand):
            result.messages.append("Invalid card selection.")
            return result

        card = opponent.hand[opponent_card_index]
        opponent.replace_card(opponent_card_index)
        result.messages.append(f"{opponent.display_name} discards {card.name} and draws a new card.")

        # Now resolve end of turn for the active player
        self._resolve_end_of_turn(player, opponent, result)

        return result

    def _resolve_end_of_turn(self, player: Player, opponent: Player, result: TurnResult):
        """Process all end-of-turn effects."""

        # 1. Monster combat
        if player.monster:
            combat_msgs = self._resolve_monster_attack(player, opponent)
            result.monster_combat_occurred = bool(combat_msgs)
            result.monster_combat_messages = combat_msgs
            result.messages.extend(combat_msgs)

        # 2. Taint damage
        if player.taint > 0:
            player.life -= player.taint
            result.end_of_turn_messages.append(
                f"🩸 {player.display_name} takes {player.taint} Taint damage. (Life: {player.life})")
            result.messages.append(result.end_of_turn_messages[-1])

        # 3. Madness end-of-turn effects
        madness_msgs = self._apply_madness_end_of_turn(player, opponent)
        result.end_of_turn_messages.extend(madness_msgs)
        result.messages.extend(madness_msgs)

        # 4. Agoraphobia draw-up
        if player.madness == "Agoraphobia":
            draw_msgs = player.apply_end_of_turn_draw()
            result.end_of_turn_messages.extend(draw_msgs)
            result.messages.extend(draw_msgs)

        # 5. Check game over
        game_over_msgs = self.state.check_game_over()
        if game_over_msgs:
            result.game_over = True
            result.game_over_messages = game_over_msgs
            result.messages.extend(game_over_msgs)
            return

        # 6. Switch turns
        self.state.switch_turn()

        # 7. Check if next player can act
        next_player = self.state.current_player
        if not next_player.has_cards and len(next_player.hand) == 0:
            # Skip their turn
            result.messages.append(f"⏭️ {next_player.display_name} has no cards! Turn skipped.")
            skip_opponent = self.state.get_opponent(next_player)

            # Still apply their end-of-turn effects
            if next_player.monster:
                skip_combat = self._resolve_monster_attack(next_player, skip_opponent)
                result.messages.extend(skip_combat)

            if next_player.taint > 0:
                next_player.life -= next_player.taint
                result.messages.append(
                    f"🩸 {next_player.display_name} takes {next_player.taint} Taint damage. (Life: {next_player.life})")

            skip_madness = self._apply_madness_end_of_turn(next_player, skip_opponent)
            result.messages.extend(skip_madness)

            # Check game over again
            game_over_msgs = self.state.check_game_over()
            if game_over_msgs:
                result.game_over = True
                result.game_over_messages = game_over_msgs
                result.messages.extend(game_over_msgs)
                return

            self.state.switch_turn()

            # If BOTH players have no cards, it's a draw
            both_empty = (not self.state.player1.has_cards and len(self.state.player1.hand) == 0 and
                          not self.state.player2.has_cards and len(self.state.player2.hand) == 0)
            if both_empty:
                self.state.game_over = True
                self.state.is_draw = True
                result.game_over = True
                result.game_over_messages.append("📚 Both players have exhausted their decks! It's a draw!")
                result.messages.append(result.game_over_messages[-1])

    def _resolve_monster_attack(self, attacker: Player, defender: Player) -> list[str]:
        """Resolve monster attack at end of turn."""
        msgs = []
        a_monster = attacker.monster

        if not a_monster:
            return msgs

        d_monster = defender.monster

        # Check if the attack is blocked
        blocked = False
        if d_monster:
            if a_monster.has_trait("byakhee_only"):
                # Only blocked by another Byakhee
                if d_monster.monster_id == "byakhee":
                    blocked = True
                # Otherwise unblocked
            else:
                blocked = True

        if blocked and d_monster:
            msgs.append(f"⚔️ {a_monster.name} (Power {a_monster.power}) clashes with {d_monster.name} (Power {d_monster.power})!")
            if a_monster.power > d_monster.power:
                msgs.append(f"  {a_monster.name} wins! {d_monster.name} is destroyed!")
                defender.remove_monster()
            elif d_monster.power > a_monster.power:
                msgs.append(f"  {d_monster.name} wins! {a_monster.name} is destroyed!")
                attacker.remove_monster()
            else:
                msgs.append(f"  Tie! Both monsters are destroyed!")
                attacker.remove_monster()
                defender.remove_monster()
        else:
            # Direct damage to defender
            damage = a_monster.power
            piercing = a_monster.has_trait("piercing")
            actual = attacker.deal_damage_to(defender, damage, ignore_elder=piercing)
            msgs.append(f"🐙 {a_monster.name} attacks {defender.display_name} for {actual} damage!{' (Piercing!)' if piercing else ''}")

        return msgs

    def _check_madness_on_play(self, player: Player) -> list[str]:
        """Check and apply madness effects when a card is played."""
        msgs = []
        if player.madness == "Xenophobia":
            msgs.extend(player.apply_xenophobia())
        if player.madness == "Agoraphobia":
            msgs.extend(player.apply_agoraphobia())
        return msgs

    def _apply_madness_end_of_turn(self, player: Player, opponent: Player) -> list[str]:
        """Apply madness end-of-turn effects."""
        msgs = []
        if not player.madness:
            return msgs

        if player.madness == "Megalomania":
            player.modify_arcane(2)
            player.modify_taint(4)
            msgs.append(f"👑 Megalomania: {player.display_name} gains 2 Arcane and 4 Taint! (Arcane: {player.arcane}, Taint: {player.taint})")

        elif player.madness == "Schizophrenia":
            player.set_arcane(0)
            player.set_elder_defense(0)
            msgs.append(f"🌀 Schizophrenia: {player.display_name}'s Arcane and Elder Defense set to 0!")

        return msgs

    def get_current_player_options(self) -> dict:
        """Get the available actions for the current player."""
        player = self.state.current_player
        options = {
            "can_play": [],
            "can_discard": [],
            "hand": [],
        }

        for i, card in enumerate(player.hand):
            can_play, reason = player.can_play_card(i)
            options["hand"].append({
                "index": i,
                "card": card,
                "can_play": can_play,
                "play_reason": reason,
            })
            if can_play:
                options["can_play"].append(i)
            options["can_discard"].append(i)

        return options

    def calculate_xp(self, player: Player) -> dict:
        """Calculate XP earned for a victorious player."""
        remaining_life = max(0, player.life)
        remaining_sanity = player.sanity  # Can be negative
        damage_dealt = player.damage_dealt
        best_attack = player.best_attack
        damage_received = player.damage_received

        total = remaining_life + remaining_sanity + damage_dealt + best_attack - damage_received
        total = max(0, total)  # Floor at 0

        return {
            "remaining_life": remaining_life,
            "remaining_sanity": remaining_sanity,
            "damage_dealt": damage_dealt,
            "best_attack": best_attack,
            "damage_received": damage_received,
            "total": total,
        }

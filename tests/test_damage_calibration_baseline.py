"""
tests/test_damage_calibration_baseline.py

P0 Task #26: Baseline Damage Calibration Test Suite

This test file validates that simulator damage calculations match real game data
within 5% accuracy. It's structured to accept game-verified test cases.

Structure:
  - GameDamageCase: Dataclass holding one real game damage measurement
  - BaselineDamageTests: Fixture-based tests validating simulator vs game data
  - _game_data.py: Game-verified measurements (populated during research phase)

Each test case includes:
  - Pokemon stats (attacker & defender)
  - Skill (name, power, type, category)
  - Battle context (weather, marks, buffs, debuffs, status)
  - Expected game damage
  - Simulator damage (calculated here)
  - Pass if: |simulator - game| / game < 5%
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from src.models import Pokemon, Skill, BattleState, Type, SkillCategory, StatusType
from src.effect_models import E, EffectTag, Timing, SkillEffect, SkillTiming
from src.battle import DamageCalculator
import pytest


# ─────────────────────────────────────────
#  Test Data Structure
# ─────────────────────────────────────────

@dataclass
class GameDamageCase:
    """One real game damage measurement."""
    
    # Identifiers
    case_id: str  # e.g., "baseline_001"
    description: str  # e.g., "Pure FIRE vs GRASS, no weather"
    
    # Attacker
    attacker_name: str
    attacker_hp: int
    attacker_atk: int
    attacker_def: int
    attacker_spatk: int
    attacker_spdef: int
    attacker_speed: int
    attacker_type: Type
    
    # Defender
    defender_name: str
    defender_hp: int
    defender_atk: int
    defender_def: int
    defender_spatk: int
    defender_spdef: int
    defender_speed: int
    defender_type: Type
    
    # Skill
    skill_name: str
    skill_power: int
    skill_type: Type
    skill_category: SkillCategory
    
    # Battle context
    weather: Optional[str] = None
    attacker_buffs: Dict[str, int] = field(default_factory=dict)
    defender_buffs: Dict[str, int] = field(default_factory=dict)
    attacker_status: Optional[StatusType] = None
    defender_status: Optional[StatusType] = None
    attacker_marks: Dict[str, int] = field(default_factory=dict)
    defender_marks: Dict[str, int] = field(default_factory=dict)
    
    # Expected result from game
    game_damage: int = 0
    game_damage_range: Optional[tuple] = None
    
    # Notes
    notes: str = ""


# ─────────────────────────────────────────
#  Test Fixture: Create Pokemon from GameDamageCase
# ─────────────────────────────────────────

def pokemon_from_case(case: GameDamageCase, is_attacker: bool) -> Pokemon:
    """Convert GameDamageCase data to a Pokemon object."""
    if is_attacker:
        return Pokemon(
            name=case.attacker_name,
            pokemon_type=case.attacker_type,
            hp=case.attacker_hp,
            attack=case.attacker_atk,
            defense=case.attacker_def,
            sp_attack=case.attacker_spatk,
            sp_defense=case.attacker_spdef,
            speed=case.attacker_speed,
            skills=[],
        )
    else:
        return Pokemon(
            name=case.defender_name,
            pokemon_type=case.defender_type,
            hp=case.defender_hp,
            attack=case.defender_atk,
            defense=case.defender_def,
            sp_attack=case.defender_spatk,
            sp_defense=case.defender_spdef,
            speed=case.defender_speed,
            skills=[],
        )


def skill_from_case(case: GameDamageCase) -> Skill:
    """Create a Skill object from GameDamageCase."""
    return Skill(
        name=case.skill_name,
        skill_type=case.skill_type,
        category=case.skill_category,
        power=case.skill_power,
        energy_cost=3,
        effects=[],
    )


# ─────────────────────────────────────────
#  Test Framework
# ─────────────────────────────────────────

class BaselineDamageTests:
    """
    Calibration test suite for simulator damage calculations.
    
    To add a game-verified test case:
      1. Capture game data: attacker stats, defender stats, skill, result damage
      2. Create a GameDamageCase with that data
      3. Add to TEST_CASES below
      4. Run tests: pytest test_damage_calibration_baseline.py -v
    """
    
    # Placeholder: To be populated with real game data during research
    TEST_CASES: List[GameDamageCase] = [
        GameDamageCase(
            case_id="baseline_001",
            description="FIRE (ATK 150) vs GRASS (DEF 100) - Pure attack, no weather",
            
            attacker_name="Attacker_FIRE",
            attacker_hp=250, attacker_atk=150, attacker_def=100,
            attacker_spatk=90, attacker_spdef=100, attacker_speed=110,
            attacker_type=Type.FIRE,
            
            defender_name="Defender_GRASS",
            defender_hp=200, defender_atk=100, defender_def=100,
            defender_spatk=90, defender_spdef=90, defender_speed=90,
            defender_type=Type.GRASS,
            
            skill_name="Ember",
            skill_power=40,
            skill_type=Type.FIRE,
            skill_category=SkillCategory.MAGICAL,
            
            game_damage=0,
            notes="Baseline fire-vs-grass, 1x type advantage, no modifiers [PLACEHOLDER]",
        ),
    ]
    
    @pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: c.case_id)
    def test_damage_matches_game_within_5_percent(self, case: GameDamageCase):
        """
        Main calibration test: Simulator damage must match game within 5%.
        """
        if case.game_damage == 0:
            pytest.skip(f"Placeholder data: {case.case_id}")
        
        attacker = pokemon_from_case(case, is_attacker=True)
        defender = pokemon_from_case(case, is_attacker=False)
        skill = skill_from_case(case)
        
        simulator_damage = DamageCalculator.calculate(attacker, defender, skill)
        error_pct = abs(simulator_damage - case.game_damage) / case.game_damage
        
        assert error_pct < 0.05, (
            f"{case.case_id} FAILED:\n"
            f"  Game: {case.game_damage} | Simulator: {simulator_damage}\n"
            f"  Error: {error_pct*100:.2f}% (> 5% threshold)\n"
            f"  {case.description}\n"
        )
    
    def test_damage_formula_is_deterministic(self):
        """Verify that damage calculation is deterministic."""
        case = self.TEST_CASES[0]
        attacker = pokemon_from_case(case, is_attacker=True)
        defender = pokemon_from_case(case, is_attacker=False)
        skill = skill_from_case(case)
        
        results = [DamageCalculator.calculate(attacker, defender, skill) for _ in range(5)]
        assert len(set(results)) == 1, f"Non-deterministic: {results}"


# ─────────────────────────────────────────
#  Diagnostic Tests
# ─────────────────────────────────────────

def test_calibration_suite_structure_is_valid():
    """Verify test suite structure."""
    assert len(BaselineDamageTests.TEST_CASES) > 0
    for case in BaselineDamageTests.TEST_CASES:
        assert case.case_id
        assert case.attacker_atk > 0
        assert case.defender_def > 0


def test_placeholder_detection():
    """Detect placeholder values that need population."""
    placeholder_count = sum(1 for c in BaselineDamageTests.TEST_CASES if c.game_damage == 0)
    total = len(BaselineDamageTests.TEST_CASES)
    
    if placeholder_count > 0:
        pytest.skip(
            f"{placeholder_count}/{total} cases have placeholder game_damage=0. "
            f"Populate with real game data to enable calibration tests."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

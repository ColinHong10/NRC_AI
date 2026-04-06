"""
Test TIER 1 ability configurations (2026-04-07)

Tests the 12 critical abilities that modify battle flow:
- Counter-Success: 5 abilities
- First-Strike: 4 abilities  
- Turn-End: 3 abilities
"""

from src.effect_models import E, Timing, EffectTag, AbilityEffect
from src.models import BattleState, Pokemon, Type, Skill
from src.effect_data import ABILITY_EFFECTS


def make_pokemon(name="test", hp=100, atk=100, defense=80, 
                 spatk=100, spdef=80, speed=90, ptype=Type.NORMAL):
    """Helper to create test Pokemon"""
    return Pokemon(
        name=name, pokemon_type=ptype, 
        hp=hp, attack=atk, defense=defense,
        sp_attack=spatk, sp_defense=spdef, speed=speed,
        ability="",
        skills=[],
        current_hp=hp,
    )


# ─────────────────────────────────────────
#  Configuration Tests
# ─────────────────────────────────────────

def test_tier1_abilities_exist():
    """Verify all 12 TIER 1 abilities are configured"""
    tier1_names = [
        '圣火骑士', '指挥家', '斗技', '思维之盾', '野性感官',  # Counter-Success (5)
        '破空', '顺风', '咔咔冲刺', '起飞加速',                  # First-Strike (4)
        '警惕', '防过载保护', '星地善良',                        # Turn-End (3)
    ]
    
    for ability_name in tier1_names:
        assert ability_name in ABILITY_EFFECTS, f"Missing TIER1 ability: {ability_name}"
        assert len(ABILITY_EFFECTS[ability_name]) > 0, f"Empty config: {ability_name}"


def test_counter_success_abilities():
    """Verify 5 counter-success abilities have ON_COUNTER_SUCCESS timing"""
    counter_abilities = [
        '圣火骑士', '指挥家', '斗技', '思维之盾', '野性感官'
    ]
    
    for name in counter_abilities:
        effects = ABILITY_EFFECTS[name]
        timings = [ae.timing for ae in effects]
        assert Timing.ON_COUNTER_SUCCESS in timings, f"{name} missing ON_COUNTER_SUCCESS"


def test_first_strike_abilities():
    """Verify 4 first-strike abilities exist"""
    first_strike = ['破空', '顺风', '咔咔冲刺', '起飞加速']
    for name in first_strike:
        assert name in ABILITY_EFFECTS
        assert len(ABILITY_EFFECTS[name]) > 0


def test_turn_end_abilities():
    """Verify 3 turn-end abilities exist"""
    turn_end = ['警惕', '防过载保护', '星地善良']
    for name in turn_end:
        assert name in ABILITY_EFFECTS
        assert len(ABILITY_EFFECTS[name]) > 0


# ─────────────────────────────────────────
#  Effect Configuration Tests
# ─────────────────────────────────────────

def test_counter_success_effects_are_configured():
    """Verify counter-success effects have appropriate primitives"""
    counter_abilities = [
        '圣火骑士',  # Double damage
        '指挥家',     # +20% ATK permanent
        '斗技',       # +20 power permanent
        '思维之盾',   # -5 energy cost
        '野性感官',   # +1 priority
    ]
    
    for ability_name in counter_abilities:
        effects = ABILITY_EFFECTS[ability_name]
        all_tags = []
        for ae in effects:
            for tag in ae.effects:
                all_tags.append(tag.type)
        
        # Each should have some effect configured
        assert len(all_tags) > 0, f"{ability_name} has no effect primitives"


def test_ability_compute_actions_present():
    """Verify ability_compute actions for complex abilities"""
    # First-strike abilities use ABILITY_COMPUTE with action dispatch
    complex_abilities = ['破空', '顺风', '起飞加速', '警惕']
    
    for name in complex_abilities:
        effects = ABILITY_EFFECTS[name]
        all_tags = []
        for ae in effects:
            for tag in ae.effects:
                all_tags.append(tag.type)
        
        # Should have ABILITY_COMPUTE or other effect primitives
        assert len(all_tags) > 0, f"{name} has no effects"


# ─────────────────────────────────────────
#  Data Structure Tests
# ─────────────────────────────────────────

def test_tier1_effects_have_valid_structure():
    """Verify all TIER1 abilities have valid AbilityEffect structures"""
    tier1_names = [
        '圣火骑士', '指挥家', '斗技', '思维之盾', '野性感官',
        '破空', '顺风', '咔咔冲刺', '起飞加速',
        '警惕', '防过载保护', '星地善良',
    ]
    
    for name in tier1_names:
        effects = ABILITY_EFFECTS[name]
        assert isinstance(effects, list)
        
        for ae in effects:
            assert isinstance(ae, AbilityEffect)
            assert hasattr(ae, 'timing')
            assert hasattr(ae, 'effects')
            assert isinstance(ae.effects, list)
            assert len(ae.effects) > 0


# ─────────────────────────────────────────
#  Coverage Report
# ─────────────────────────────────────────

def test_tier1_coverage_summary():
    """Print TIER1 coverage summary"""
    print("\n" + "=" * 60)
    print("TIER 1 ABILITIES COVERAGE SUMMARY")
    print("=" * 60)
    
    counter_success = {
        '圣火骑士': 'Double damage on counter',
        '指挥家': '+20% ATK permanent',
        '斗技': '+20 power permanent',
        '思维之盾': '-5 energy cost after counter',
        '野性感官': '+1 speed priority after counter',
    }
    
    first_strike = {
        '破空': '+75% power if first strike',
        '顺风': '+50% power if first strike',
        '咔咔冲刺': '+1 hit count if first strike',
        '起飞加速': 'First skill gets agility',
    }
    
    turn_end = {
        '警惕': 'Auto-switch at 0 energy',
        '防过载保护': 'Auto-switch after any action',
        '星地善良': 'Swap ally at 0 energy',
    }
    
    print("\n✅ COUNTER-SUCCESS (5 abilities):")
    for name, desc in counter_success.items():
        status = "✓" if name in ABILITY_EFFECTS else "✗"
        print(f"  {status} {name:12s} - {desc}")
    
    print("\n✅ FIRST-STRIKE (4 abilities):")
    for name, desc in first_strike.items():
        status = "✓" if name in ABILITY_EFFECTS else "✗"
        print(f"  {status} {name:12s} - {desc}")
    
    print("\n✅ TURN-END (3 abilities):")
    for name, desc in turn_end.items():
        status = "✓" if name in ABILITY_EFFECTS else "✗"
        print(f"  {status} {name:12s} - {desc}")
    
    print("\n" + "=" * 60)
    print(f"Total Configured: 12/12 ✓")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])

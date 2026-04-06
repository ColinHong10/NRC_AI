"""
Test suite for remaining 6 TIER 2 abilities (Healing/Sustain, Status, Entry Effects)

Abilities tested:
- 生长 (Grow) - Heal 12% per turn
- 深层氧循环 (Deep Oxygen Cycle) - Heal 15% on grass skill
- 缩壳 (Retract Shell) - -2 cost on defense skills
- 毒牙 (Poison Fang) - -40% Sp.ATK/Sp.DEF when poisoned
- 毒腺 (Poison Gland) - 4-layer poison on low-cost skill
- 吉利丁片 (Gelatin Slice) - +20% defense, freeze immune
"""

import sys
sys.path.insert(0, '/Users/colinhong/WorkBuddy/Claw/NRC_AI')

from src.effect_models import E, Timing, EffectTag
from src.effect_engine import _HANDLERS, _ABILITY_HANDLER_OVERRIDES
from src.effect_data import ABILITY_EFFECTS


def test_enum_existence():
    """Verify all 6 new enums exist in E"""
    new_enums = [
        E.HEAL_PER_TURN,
        E.HEAL_ON_GRASS_SKILL,
        E.SKILL_COST_REDUCTION_TYPE,
        E.POISON_STAT_DEBUFF,
        E.POISON_ON_SKILL_APPLY,
        E.FREEZE_IMMUNITY_AND_BUFF,
    ]
    assert len(new_enums) == 6
    print("✅ All 6 new E enum values exist")


def test_handler_registration():
    """Verify all 6 handlers are registered"""
    handler_enums = [
        E.HEAL_PER_TURN,
        E.HEAL_ON_GRASS_SKILL,
        E.SKILL_COST_REDUCTION_TYPE,
        E.POISON_STAT_DEBUFF,
        E.POISON_ON_SKILL_APPLY,
        E.FREEZE_IMMUNITY_AND_BUFF,
    ]
    
    for enum in handler_enums:
        assert enum in _HANDLERS, f"{enum.name} not in _HANDLERS"
        assert enum in _ABILITY_HANDLER_OVERRIDES, f"{enum.name} not in _ABILITY_HANDLER_OVERRIDES"
    
    print("✅ All 6 handlers registered in both dicts (12 registrations)")


def test_ability_configuration():
    """Verify all 6 abilities are configured in ABILITY_EFFECTS"""
    new_abilities = [
        ("生长", Timing.ON_TURN_END),
        ("深层氧循环", Timing.ON_USE_SKILL),
        ("缩壳", Timing.PASSIVE),
        ("毒牙", Timing.ON_USE_SKILL),
        ("毒腺", Timing.ON_USE_SKILL),
        ("吉利丁片", Timing.ON_ENTER),
    ]
    
    for ability_name, expected_timing in new_abilities:
        assert ability_name in ABILITY_EFFECTS, f"{ability_name} not in ABILITY_EFFECTS"
        config = ABILITY_EFFECTS[ability_name]
        assert len(config) > 0, f"{ability_name} has no effects"
        assert config[0].timing == expected_timing, f"{ability_name} timing mismatch"
    
    print("✅ All 6 abilities configured with correct timing")


def test_ability_parameters():
    """Verify ability parameters match specifications"""
    params_spec = {
        "生长": {"heal_pct": 0.12},
        "深层氧循环": {"heal_pct": 0.15},
        "缩壳": {"cost_reduction": 2},
        "毒牙": {"spatk_reduction": 0.4, "spdef_reduction": 0.4},
        "毒腺": {"poison_stacks": 4, "cost_threshold": 5},
        "吉利丁片": {"def_bonus": 0.2},
    }
    
    for ability_name, expected_params in params_spec.items():
        config = ABILITY_EFFECTS[ability_name]
        ae = config[0]
        effects = ae.effects
        assert len(effects) > 0, f"{ability_name} has no effects"
        tag = effects[0]
        
        for param_name, expected_value in expected_params.items():
            actual_value = tag.params.get(param_name)
            assert actual_value == expected_value, \
                f"{ability_name}.{param_name} = {actual_value}, expected {expected_value}"
    
    print("✅ All ability parameters match specifications")


def test_ability_count():
    """Verify total ability count is correct"""
    # Should have at least 56 (50 + 6 new)
    assert len(ABILITY_EFFECTS) >= 56, f"Expected at least 56 abilities, got {len(ABILITY_EFFECTS)}"
    
    # Verify 6 new ones are in there
    new_abilities = ["生长", "深层氧循环", "缩壳", "毒牙", "毒腺", "吉利丁片"]
    for ab in new_abilities:
        assert ab in ABILITY_EFFECTS
    
    print(f"✅ Total abilities: {len(ABILITY_EFFECTS)} (includes 6 new TIER 2)")


def test_effect_tags_valid():
    """Verify effect tags are properly constructed"""
    new_abilities = ["生长", "深层氧循环", "缩壳", "毒牙", "毒腺", "吉利丁片"]
    
    for ability_name in new_abilities:
        config = ABILITY_EFFECTS[ability_name]
        for ae in config:
            assert ae.timing in Timing, f"Invalid timing for {ability_name}"
            assert ae.effects, f"{ability_name} has no effects"
            for tag in ae.effects:
                assert isinstance(tag, EffectTag), f"{ability_name} has non-EffectTag effect"
                assert tag.type in E, f"{ability_name} uses invalid effect type"
                assert isinstance(tag.params, dict), f"{ability_name} has non-dict params"
    
    print("✅ All effect tags properly constructed")


def test_handler_logic_basic():
    """Basic logic test for handlers (without full battle context)"""
    # Test that handlers exist and are callable
    handler_checks = [
        (E.HEAL_PER_TURN, "_h_heal_per_turn"),
        (E.HEAL_ON_GRASS_SKILL, "_h_heal_on_grass_skill"),
        (E.SKILL_COST_REDUCTION_TYPE, "_h_skill_cost_reduction_type"),
        (E.POISON_STAT_DEBUFF, "_h_poison_stat_debuff"),
        (E.POISON_ON_SKILL_APPLY, "_h_poison_on_skill_apply"),
        (E.FREEZE_IMMUNITY_AND_BUFF, "_h_freeze_immunity_and_buff"),
    ]
    
    for enum, handler_name in handler_checks:
        handler = _HANDLERS[enum]
        assert callable(handler), f"{handler_name} is not callable"
        assert handler.__name__ == handler_name, f"Handler name mismatch"
    
    print("✅ All handlers are callable with correct names")


def run_all_tests():
    """Run all tests"""
    tests = [
        test_enum_existence,
        test_handler_registration,
        test_ability_configuration,
        test_ability_parameters,
        test_ability_count,
        test_effect_tags_valid,
        test_handler_logic_basic,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("\n✅ All 7 tests passed!")
        print("=" * 60)
        print("TIER 2 Remaining Abilities (6) — COMPLETE")
        print("=" * 60)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)

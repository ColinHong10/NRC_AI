"""
Battle trigger regression tests.

Covers:
1. ON_BATTLE_START is triggered once on battle entry.
2. ON_ALLY_COUNTER is triggered when a teammate successfully counters.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory
from src.effect_models import E, EffectTag, Timing, AbilityEffect, SkillEffect, SkillTiming
from src.battle import auto_switch, execute_full_turn, _is_first_action, DamageCalculator


def make_skill(name, power=40, energy=0, skill_type=Type.NORMAL,
               category=SkillCategory.PHYSICAL, effects=None):
    return Skill(
        name=name,
        skill_type=skill_type,
        category=category,
        power=power,
        energy_cost=energy,
        effects=effects or [],
    )


def make_pokemon(name="test", hp=200, attack=100, defense=80,
                 spatk=80, spdef=80, speed=80, ptype=Type.NORMAL,
                 skills=None, ability="", energy=10):
    return Pokemon(
        name=name,
        pokemon_type=ptype,
        hp=hp,
        attack=attack,
        defense=defense,
        sp_attack=spatk,
        sp_defense=spdef,
        speed=speed,
        ability=ability,
        skills=skills or [],
        energy=energy,
    )


def test_battle_start_triggers_once():
    starter = make_pokemon(
        "starter",
        skills=[make_skill("strike")],
    )
    starter.ability_effects = [
        AbilityEffect(
            Timing.ON_BATTLE_START,
            [EffectTag(E.ABILITY_INCREMENT_COUNTER)],
        )
    ]
    other = make_pokemon("other", skills=[make_skill("guard")])
    state = BattleState(team_a=[starter], team_b=[other], current_a=0, current_b=0)

    auto_switch(state)
    auto_switch(state)

    assert state.counter_count_a == 1
    assert state.battle_start_effects_triggered is True


def test_ally_counter_triggers_allied_ability():
    attacker = make_pokemon(
        "attacker",
        speed=120,
        skills=[make_skill("strike", power=70, energy=0, skill_type=Type.FIRE)],
    )
    counter_user = make_pokemon(
        "counter_user",
        hp=220,
        speed=20,
        energy=0,
        skills=[
            make_skill(
                "guard_retaliate",
                power=0,
                energy=5,
                category=SkillCategory.DEFENSE,
                effects=[SkillEffect(SkillTiming.ON_COUNTER, [], {"category": "attack"})],
            )
        ],
    )
    ally = make_pokemon(
        "ally",
        energy=0,
        skills=[make_skill("support")],
    )
    ally.ability_effects = [
        AbilityEffect(
            Timing.ON_ALLY_COUNTER,
            [EffectTag(E.HEAL_ENERGY, {"amount": 1})],
        )
    ]
    state = BattleState(
        team_a=[attacker],
        team_b=[counter_user, ally],
        current_a=0,
        current_b=0,
    )

    execute_full_turn(state, (0,), (0,))

    assert ally.energy == 1


def test_is_first_action_handles_enemy_action_indices():
    slow_a = make_pokemon(
        "slow_a",
        speed=50,
        skills=[make_skill("only_skill", power=50, energy=0)],
    )
    fast_b = make_pokemon(
        "fast_b",
        speed=120,
        skills=[
            make_skill("guard", power=0, energy=0, category=SkillCategory.DEFENSE),
            make_skill("water_ring", power=0, energy=0, category=SkillCategory.DEFENSE),
            make_skill("extra", power=0, energy=0, category=SkillCategory.DEFENSE),
        ],
    )
    state = BattleState(team_a=[slow_a], team_b=[fast_b], current_a=0, current_b=0)

    # B 方当前动作索引在 A 方技能表中并不存在；之前这里会在优先级判断时报 IndexError。
    is_first = _is_first_action(state, "b", (1,), "a", (0,))

    assert is_first is True


def test_priority_beats_speed():
    slow_priority = make_pokemon(
        "slow_priority",
        speed=50,
        skills=[make_skill("quick", power=50, energy=0)],
    )
    slow_priority.skills[0].priority_mod = 1
    fast_normal = make_pokemon(
        "fast_normal",
        speed=200,
        skills=[make_skill("normal", power=50, energy=0)],
    )
    state = BattleState(team_a=[slow_priority], team_b=[fast_normal], current_a=0, current_b=0)

    assert _is_first_action(state, "a", (0,), "b", (0,)) is True


def test_speed_buffs_break_priority_ties():
    slower = make_pokemon("slower", speed=100, skills=[make_skill("a", energy=0)])
    faster_after_buff = make_pokemon("faster", speed=90, skills=[make_skill("b", energy=0)])
    faster_after_buff.speed_up = 0.5
    state = BattleState(team_a=[slower], team_b=[faster_after_buff], current_a=0, current_b=0)

    assert _is_first_action(state, "b", (0,), "a", (0,)) is True


def test_equal_priority_and_speed_use_random_tiebreak():
    a = make_pokemon("a", speed=100, skills=[make_skill("a", energy=0)])
    b = make_pokemon("b", speed=100, skills=[make_skill("b", energy=0)])
    state = BattleState(team_a=[a], team_b=[b], current_a=0, current_b=0)

    with patch("src.battle.random.choice", return_value=-1):
        assert _is_first_action(state, "a", (0,), "b", (0,)) is True
    with patch("src.battle.random.choice", return_value=1):
        assert _is_first_action(state, "a", (0,), "b", (0,)) is False


def test_physical_dark_skill_uses_attack_stat():
    attacker = make_pokemon(
        "attacker",
        attack=200,
        spatk=20,
        speed=100,
        skills=[make_skill("bat", power=60, energy=0, skill_type=Type.DARK, category=SkillCategory.PHYSICAL)],
    )
    defender = make_pokemon(
        "defender",
        defense=80,
        spdef=300,
        speed=80,
        ptype=Type.NORMAL,
    )

    damage = DamageCalculator.calculate(attacker, defender, attacker.skills[0])
    expected = int((attacker.effective_atk() / defender.effective_def()) * 60 * 0.9)
    assert damage == max(1, expected)


if __name__ == "__main__":
    test_battle_start_triggers_once()
    test_ally_counter_triggers_allied_ability()
    test_is_first_action_handles_enemy_action_indices()
    test_priority_beats_speed()
    test_speed_buffs_break_priority_ties()
    test_equal_priority_and_speed_use_random_tiebreak()
    test_physical_dark_skill_uses_attack_stat()
    print("PASS: battle trigger regressions")

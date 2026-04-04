"""
Generic effect-engine mechanism regressions.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory
from src.effect_models import E, EffectTag
from src.effect_engine import EffectExecutor
from src.battle import execute_full_turn


def make_skill(name, power=0, energy=0, skill_type=Type.NORMAL,
               category=SkillCategory.STATUS, effects=None):
    return Skill(
        name=name,
        skill_type=skill_type,
        category=category,
        power=power,
        energy_cost=energy,
        effects=effects or [],
    )


def make_pokemon(name="test", hp=300, attack=100, defense=80, spatk=100,
                 spdef=80, speed=100, ptype=Type.NORMAL, skills=None):
    return Pokemon(
        name=name,
        pokemon_type=ptype,
        hp=hp,
        attack=attack,
        defense=defense,
        sp_attack=spatk,
        sp_defense=spdef,
        speed=speed,
        skills=skills or [],
    )


def test_skill_life_drain_heals_after_damage():
    bat = make_skill(
        "bat",
        power=60,
        energy=0,
        skill_type=Type.DARK,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE), EffectTag(E.LIFE_DRAIN, {"pct": 1.0})],
    )
    attacker = make_pokemon("attacker", attack=150, defense=80, skills=[bat], ptype=Type.DARK)
    attacker.current_hp = 120
    defender = make_pokemon("defender", hp=320, defense=90, skills=[make_skill("wait")])
    state = BattleState(team_a=[attacker], team_b=[defender])

    execute_full_turn(state, (0,), (-1,))

    assert attacker.current_hp > 120


def test_grant_life_drain_applies_to_later_attacks():
    grant = make_skill(
        "greed",
        effects=[EffectTag(E.GRANT_LIFE_DRAIN, {"pct": 0.5})],
    )
    attack = make_skill(
        "slash",
        power=80,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon("user", attack=160, skills=[grant, attack])
    user.current_hp = 150
    enemy = make_pokemon("enemy", hp=320, defense=90, skills=[make_skill("wait")])
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    hp_after_grant = user.current_hp
    execute_full_turn(state, (1,), (-1,))

    assert user.current_hp > hp_after_grant


def test_next_attack_mod_is_consumed_once():
    prep = make_skill(
        "prep",
        effects=[EffectTag(E.NEXT_ATTACK_MOD, {"power_bonus": 70})],
    )
    strike = make_skill(
        "strike",
        power=60,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon("user", attack=140, skills=[prep, strike])
    enemy = make_pokemon("enemy", hp=400, defense=90, skills=[make_skill("wait")])
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    hp_before_first = enemy.current_hp
    execute_full_turn(state, (1,), (-1,))
    first_damage = hp_before_first - enemy.current_hp
    hp_before_second = enemy.current_hp
    execute_full_turn(state, (1,), (-1,))
    second_damage = hp_before_second - enemy.current_hp

    assert first_damage > second_damage
    assert user.next_attack_power_bonus == 0
    assert user.next_attack_power_pct == 0.0


def test_cleanse_can_remove_buffs_and_debuffs():
    cleanse_skill = make_skill(
        "cleanse",
        effects=[
            EffectTag(E.CLEANSE, {"target": "enemy", "mode": "buffs"}),
            EffectTag(E.CLEANSE, {"target": "self", "mode": "debuffs"}),
        ],
    )
    user = make_pokemon("user", skills=[cleanse_skill])
    enemy = make_pokemon("enemy", skills=[make_skill("wait")])
    user.poison_stacks = 3
    user.speed_mod = -0.4
    enemy.atk_mod = 0.8
    enemy.def_mod = 0.6
    state = BattleState(team_a=[user], team_b=[enemy])

    EffectExecutor.execute_skill(state, user, enemy, cleanse_skill, cleanse_skill.effects)

    assert user.poison_stacks == 0
    assert user.speed_mod == 0.0
    assert enemy.atk_mod == 0.0
    assert enemy.def_mod == 0.0


def test_skill_mod_priority_affects_turn_order():
    priority_buff = make_skill(
        "priority_up",
        effects=[EffectTag(E.SKILL_MOD, {"target": "self", "stat": "priority", "value": 1})],
    )
    strike = make_skill(
        "strike",
        power=220,
        skill_type=Type.NORMAL,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon("user", speed=50, attack=140, skills=[priority_buff, strike])
    enemy = make_pokemon("enemy", hp=180, defense=70, speed=200, attack=140, skills=[strike])
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (0,))
    user_hp_before = user.current_hp
    execute_full_turn(state, (1,), (0,))

    assert enemy.is_fainted
    assert user.current_hp == user_hp_before


def test_skill_mod_cost_changes_actual_energy_consumption():
    discount = make_skill(
        "discount",
        effects=[EffectTag(E.SKILL_MOD, {"target": "self", "stat": "cost", "value": -1})],
    )
    big_hit = make_skill(
        "big_hit",
        power=80,
        energy=3,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon("user", attack=150, skills=[discount, big_hit])
    user.energy = 2
    enemy = make_pokemon("enemy", hp=320, defense=90, skills=[make_skill("wait")])
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    execute_full_turn(state, (1,), (-1,))

    assert enemy.current_hp < enemy.hp
    assert user.energy == 0


if __name__ == "__main__":
    test_skill_life_drain_heals_after_damage()
    test_grant_life_drain_applies_to_later_attacks()
    test_next_attack_mod_is_consumed_once()
    test_cleanse_can_remove_buffs_and_debuffs()
    test_skill_mod_priority_affects_turn_order()
    test_skill_mod_cost_changes_actual_energy_consumption()
    print("PASS: generic effect-engine regressions")

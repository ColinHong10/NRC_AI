"""
Turn order and damage classification regressions.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory
from src.battle import DamageCalculator, _compare_action_order


def make_skill(name, power=80, energy=0, skill_type=Type.NORMAL,
               category=SkillCategory.PHYSICAL, priority=0):
    return Skill(
        name=name,
        skill_type=skill_type,
        category=category,
        power=power,
        energy_cost=energy,
        priority_mod=priority,
    )


def make_pokemon(name="test", hp=300, attack=100, defense=100,
                 spatk=100, spdef=100, speed=100, ptype=Type.NORMAL,
                 skills=None):
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


def expected_damage(attacker, defender, skill, use_special):
    atk = attacker.effective_spatk() if use_special else attacker.effective_atk()
    dfn = defender.effective_spdef() if use_special else defender.effective_def()
    stab = 1.5 if skill.skill_type == attacker.pokemon_type else 1.0
    return max(1, int((atk / dfn) * skill.power * 0.9 * stab))


def test_priority_beats_speed():
    a = make_pokemon(
        "slow_priority",
        speed=60,
        skills=[make_skill("prio", priority=1)],
    )
    b = make_pokemon(
        "fast_normal",
        speed=200,
        skills=[make_skill("normal", priority=0)],
    )
    state = BattleState(team_a=[a], team_b=[b])

    assert _compare_action_order(state, (0,), (0,)) == -1


def test_speed_buff_applies_when_priority_equal():
    a = make_pokemon(
        "buffed",
        speed=100,
        skills=[make_skill("normal")],
    )
    a.speed_mod = 0.5
    b = make_pokemon(
        "plain",
        speed=120,
        skills=[make_skill("normal")],
    )
    state = BattleState(team_a=[a], team_b=[b])

    assert _compare_action_order(state, (0,), (0,)) == -1


def test_equal_priority_and_speed_falls_back_to_random():
    a = make_pokemon("a", skills=[make_skill("normal")])
    b = make_pokemon("b", skills=[make_skill("normal")])
    state = BattleState(team_a=[a], team_b=[b])

    with patch("src.battle.random.choice", return_value=1):
        assert _compare_action_order(state, (0,), (0,)) == 1


def test_physical_dark_skill_uses_attack_and_defense():
    for skill_type in (Type.DARK, Type.DRAGON, Type.FAIRY):
        skill = make_skill(
            f"physical_{skill_type.value}",
            skill_type=skill_type,
            category=SkillCategory.PHYSICAL,
            power=60,
        )
        attacker = make_pokemon(
            "attacker",
            attack=180,
            defense=70,
            spatk=30,
            spdef=70,
            ptype=skill_type,
            skills=[skill],
        )
        defender = make_pokemon(
            "defender",
            attack=70,
            defense=60,
            spatk=200,
            spdef=240,
            ptype=Type.NORMAL,
        )

        damage = DamageCalculator.calculate(attacker, defender, skill)

        assert damage == expected_damage(attacker, defender, skill, use_special=False)


def test_magical_dark_skill_uses_special_attack_and_defense():
    skill = make_skill(
        "magical_dark",
        skill_type=Type.DARK,
        category=SkillCategory.MAGICAL,
        power=60,
    )
    attacker = make_pokemon(
        "attacker",
        attack=40,
        defense=70,
        spatk=190,
        spdef=70,
        ptype=Type.DARK,
        skills=[skill],
    )
    defender = make_pokemon(
        "defender",
        attack=70,
        defense=200,
        spatk=70,
        spdef=80,
        ptype=Type.NORMAL,
    )

    damage = DamageCalculator.calculate(attacker, defender, skill)

    assert damage == expected_damage(attacker, defender, skill, use_special=True)


if __name__ == "__main__":
    test_priority_beats_speed()
    test_speed_buff_applies_when_priority_equal()
    test_equal_priority_and_speed_falls_back_to_random()
    test_physical_dark_skill_uses_attack_and_defense()
    test_magical_dark_skill_uses_special_attack_and_defense()
    print("PASS: turn order and damage classification regressions")

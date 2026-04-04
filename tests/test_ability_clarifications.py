import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.battle import execute_full_turn
from src.effect_models import E, EffectTag
from src.models import BattleState, Pokemon, Skill, SkillCategory, Type


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
                 spdef=80, speed=100, ptype=Type.NORMAL, skills=None, ability=""):
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
        ability=ability,
    )


def test_undying_revives_full_hp_after_three_turns_without_auto_switching():
    revivee = make_pokemon(
        name="bone",
        hp=240,
        defense=50,
        speed=60,
        ability="不朽:力竭3回合后复活。",
        skills=[make_skill("wait")],
    )
    reserve = make_pokemon(name="reserve", skills=[make_skill("wait")])
    killer = make_pokemon(
        name="killer",
        attack=200,
        speed=120,
        skills=[make_skill("smash", power=800, category=SkillCategory.PHYSICAL, effects=[EffectTag(E.DAMAGE)])],
    )
    state = BattleState(team_a=[revivee, reserve], team_b=[killer])

    execute_full_turn(state, (-1,), (0,))
    assert revivee.is_fainted
    assert state.current_a == 1

    for _ in range(3):
        execute_full_turn(state, (-1,), (-1,))

    assert revivee.current_hp == revivee.hp
    assert not revivee.is_fainted
    assert state.current_a == 1


def test_guard_transforms_after_two_defense_counters():
    defend = make_skill(
        "guard",
        category=SkillCategory.DEFENSE,
        effects=[
            EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.5}),
            EffectTag(E.COUNTER_ATTACK, sub_effects=[]),
        ],
    )
    attack = make_skill("slash", power=80, category=SkillCategory.PHYSICAL, effects=[EffectTag(E.DAMAGE)])
    guarder = make_pokemon(
        name="棋齐垒（白子）",
        ptype=Type.FIGHTING,
        hp=320,
        defense=120,
        speed=90,
        ability="保卫:防御技能应对2次后，回满状态，变为棋绮后。",
        skills=[defend],
    )
    enemy = make_pokemon(
        name="enemy",
        hp=280,
        attack=130,
        speed=100,
        skills=[attack],
    )
    state = BattleState(team_a=[guarder], team_b=[enemy])

    execute_full_turn(state, (0,), (0,))
    execute_full_turn(state, (0,), (0,))

    assert "棋绮后" in guarder.name
    assert guarder.current_hp == guarder.hp
    assert len(guarder.skills) == 1
    assert guarder.skills[0].name == "guard"


def test_convection_inverts_cost_changes():
    setup = make_skill(
        "setup",
        effects=[EffectTag(E.SKILL_MOD, {"target": "self", "stat": "cost", "value": -2})],
    )
    blast = make_skill(
        "blast",
        power=90,
        energy=3,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon(
        name="whale",
        attack=150,
        ability="对流:自己的能耗增加变为能耗降低；能耗降低变为能耗增加。",
        skills=[setup, blast],
    )
    user.energy = 5
    enemy = make_pokemon(name="dummy", hp=320, defense=90, skills=[make_skill("wait")])
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    execute_full_turn(state, (1,), (-1,))

    assert enemy.current_hp < enemy.hp
    assert user.energy == 0


def test_greed_transfers_buffs_debuffs_and_statuses_on_enemy_switch():
    switch_skill = make_skill("wait")
    old_enemy = make_pokemon(
        name="old",
        skills=[switch_skill],
    )
    old_enemy.atk_mod = 0.6
    old_enemy.speed_mod = -0.2
    old_enemy.poison_stacks = 3
    old_enemy.freeze_stacks = 2
    new_enemy = make_pokemon(name="new", skills=[switch_skill], speed=50)
    greed_user = make_pokemon(
        name="greed",
        speed=120,
        ability="贪婪:敌方精灵离场后，其增益和减益会被更换入场的精灵继承。",
        skills=[switch_skill],
    )
    state = BattleState(team_a=[old_enemy, new_enemy], team_b=[greed_user])

    execute_full_turn(state, (-2, 1), (-1,))

    current = state.team_a[state.current_a]
    assert current.name == "new"
    assert current.atk_mod == 0.6
    assert current.speed_mod == -0.2
    assert current.poison_stacks == 3
    assert current.freeze_stacks == 2


def test_scouting_abilities_trigger_before_enemy_action_choice_resolution():
    strike = make_skill(
        "strike",
        power=220,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    sentry = make_pokemon(
        name="sentry",
        hp=220,
        attack=150,
        defense=70,
        speed=100,
        ability="哨兵:回合开始时若敌方技能足够击败自己，自己获得速度+50，行动后脱离。",
        skills=[strike],
    )
    bench = make_pokemon(name="bench", skills=[make_skill("wait")])
    enemy = make_pokemon(
        name="enemy",
        hp=180,
        attack=200,
        defense=60,
        speed=130,
        skills=[make_skill("nuke", power=400, category=SkillCategory.PHYSICAL, effects=[EffectTag(E.DAMAGE)])],
    )
    state = BattleState(team_a=[sentry, bench], team_b=[enemy])

    execute_full_turn(state, (0,), (0,))

    assert enemy.is_fainted
    assert state.current_a == 1


if __name__ == "__main__":
    test_undying_revives_full_hp_after_three_turns_without_auto_switching()
    test_guard_transforms_after_two_defense_counters()
    test_convection_inverts_cost_changes()
    test_greed_transfers_buffs_debuffs_and_statuses_on_enemy_switch()
    test_scouting_abilities_trigger_before_enemy_action_choice_resolution()
    print("PASS: ability clarification regressions")

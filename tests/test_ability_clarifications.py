import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.battle import execute_full_turn
from src.effect_models import E, EffectTag, Timing, SkillEffect, SkillTiming
from src.models import BattleState, Pokemon, Skill, SkillCategory, Type
from src.skill_db import load_ability_effects
from src.effect_engine import EffectExecutor


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
    p = Pokemon(
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
    # 加载特性效果（数据驱动）
    if ability:
        p.ability_effects = load_ability_effects(ability)
        # 初始化被动标记（对流等）
        for ae in p.ability_effects:
            for tag in ae.effects:
                if tag.type == E.COST_INVERT:
                    p.ability_state["cost_invert"] = True
    return p


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
            SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.5})]),
            SkillEffect(SkillTiming.ON_COUNTER, [], {"category": "attack"}),
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
    old_enemy.atk_up = 0.6       # 攻击提升 60%（buff 方向）
    old_enemy.speed_down = 0.2   # 速度降低 20%（debuff 方向）
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
    assert current.atk_up == 0.6
    assert current.speed_down == 0.2
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


def test_ability_name_matching_is_exact():
    """
    特性名称映射必须精确匹配，避免错误归属的文本也被加载成特性效果。
    """
    assert load_ability_effects("预警:回合开始时若敌方技能足够击败自己，自己获得速度+50。")
    assert load_ability_effects("预警者:回合开始时若敌方技能足够击败自己，自己获得速度+50。") == []


def test_turn_start_ability_triggers_only_for_active_holder():
    """
    回合开始特性只应由当前上场的持有者触发，不能让后排精灵越权生效。
    """
    active = make_pokemon(
        name="active",
        hp=220,
        speed=90,
        skills=[make_skill("wait")],
    )
    bench = make_pokemon(
        name="bench",
        hp=220,
        speed=90,
        ability="预警:回合开始时若敌方技能足够击败自己，自己获得速度+50。",
        skills=[make_skill("wait")],
    )
    enemy = make_pokemon(
        name="enemy",
        hp=220,
        attack=180,
        speed=100,
        skills=[make_skill("nuke", power=400, category=SkillCategory.PHYSICAL, effects=[EffectTag(E.DAMAGE)])],
    )
    state = BattleState(team_a=[active, bench], team_b=[enemy], current_a=0, current_b=0)

    execute_full_turn(state, (-1,), (0,))

    assert active.speed_up == 0
    assert bench.speed_up == 0

    holder_state = BattleState(team_a=[bench], team_b=[enemy], current_a=0, current_b=0)
    result = EffectExecutor.execute_ability(
        holder_state,
        bench,
        enemy,
        Timing.ON_TURN_START,
        bench.ability_effects,
        "a",
    )
    assert result["triggered"] is True
    assert bench.speed_up == 0.5


def test_counter_scaled_enter_ability_does_not_stack_on_repeat_entry():
    """
    身经百练类入场威力修正应基于原始威力重算，而不是对已修正威力再次乘算。
    """
    water_skill = make_skill("水刀", power=100, skill_type=Type.WATER, category=SkillCategory.PHYSICAL)
    fire_skill = make_skill("火刀", power=100, skill_type=Type.FIRE, category=SkillCategory.PHYSICAL)
    fighter = make_pokemon(name="captain", skills=[water_skill, fire_skill])
    fighter.ability_effects = load_ability_effects("身经百练:己方每应对1次，水系和武系技能威力提升20%。")
    enemy = make_pokemon(name="enemy", skills=[make_skill("wait")])
    state = BattleState(team_a=[fighter], team_b=[enemy])
    state.counter_count_a = 2

    EffectExecutor.execute_ability(state, fighter, enemy, Timing.ON_ENTER, fighter.ability_effects, "a")
    first_entry_power = fighter.skills[0].power
    first_fire_power = fighter.skills[1].power
    EffectExecutor.execute_ability(state, fighter, enemy, Timing.ON_ENTER, fighter.ability_effects, "a")
    second_entry_power = fighter.skills[0].power
    second_fire_power = fighter.skills[1].power

    assert first_entry_power == 140
    assert second_entry_power == 140
    assert first_fire_power == 100
    assert second_fire_power == 100


def test_greed_does_not_trigger_on_self_switch():
    """
    贪婪只应在敌方换人时复制状态，自己换人不应误触发。
    """
    switch_skill = make_skill("wait")
    greed_holder = make_pokemon(
        name="greed_holder",
        attack=100,
        speed=100,
        ability="贪婪:敌方精灵离场后，其增益和减益会被更换入场的精灵继承。",
        skills=[switch_skill],
    )
    greed_holder.atk_up = 0.6
    greed_holder.speed_down = 0.2
    greed_holder.poison_stacks = 3
    new_self = make_pokemon(name="new_self", skills=[switch_skill])
    dummy_enemy = make_pokemon(name="enemy", skills=[switch_skill])
    state = BattleState(team_a=[greed_holder, new_self], team_b=[dummy_enemy])

    execute_full_turn(state, (-2, 1), (-1,))

    current = state.team_a[state.current_a]
    assert current.name == "new_self"
    assert current.atk_up == 0
    assert current.speed_down == 0
    assert current.poison_stacks == 0


def test_concentric_force_applies_only_to_first_two_slots_and_does_not_stack():
    first = make_skill("first", power=100, effects=[EffectTag(E.DAMAGE)])
    second = make_skill("second", power=110, effects=[EffectTag(E.DAMAGE)])
    third = make_skill("third", power=120, effects=[EffectTag(E.DAMAGE)])
    holder = make_pokemon(
        name="holder",
        ability="向心力:1/2号位技能获得传动和威力+30。",
        skills=[first, second, third],
    )
    enemy = make_pokemon(name="enemy", skills=[make_skill("wait")])
    state = BattleState(team_a=[holder], team_b=[enemy])

    EffectExecutor.execute_ability(state, holder, enemy, Timing.PASSIVE, holder.ability_effects, "a")
    EffectExecutor.execute_ability(state, holder, enemy, Timing.PASSIVE, holder.ability_effects, "a")

    assert first.power == 130
    assert second.power == 140
    assert third.power == 120
    assert sum(1 for tag in first.effects if tag.type == E.DRIVE) == 1
    assert sum(1 for tag in second.effects if tag.type == E.DRIVE) == 1
    assert all(tag.type != E.DRIVE for tag in third.effects)


if __name__ == "__main__":
    test_undying_revives_full_hp_after_three_turns_without_auto_switching()
    test_guard_transforms_after_two_defense_counters()
    test_convection_inverts_cost_changes()
    test_greed_transfers_buffs_debuffs_and_statuses_on_enemy_switch()
    test_scouting_abilities_trigger_before_enemy_action_choice_resolution()
    test_ability_name_matching_is_exact()
    test_turn_start_ability_triggers_only_for_active_holder()
    test_counter_scaled_enter_ability_does_not_stack_on_repeat_entry()
    test_greed_does_not_trigger_on_self_switch()
    test_concentric_force_applies_only_to_first_two_slots_and_does_not_stack()
    print("PASS: ability clarification regressions")

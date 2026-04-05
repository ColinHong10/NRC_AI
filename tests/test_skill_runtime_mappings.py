"""
Runtime regressions for mapped skills.

These tests focus on the battle-facing behavior of generated/manual skills:
weather, next-attack buffs, forced switching, cleansing, priority, and
counter interruption metadata.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.battle import DamageCalculator, execute_full_turn, _is_first_action
from src.effect_engine import EffectExecutor
from src.effect_models import E, EffectTag, SkillEffect, SkillTiming
from src.models import BattleState, Pokemon, Skill, SkillCategory, Type
from src.skill_db import get_skill, load_skills


_COUNTER_CAT_MAP = {
    "attack": {E.COUNTER_ATTACK},
    "status": {E.COUNTER_STATUS},
    "defense": {E.COUNTER_DEFENSE},
}


def _find_counter(effects, category):
    """Find a counter effect (SE or legacy EffectTag) matching category."""
    for item in effects:
        if isinstance(item, SkillEffect):
            if item.timing == SkillTiming.ON_COUNTER and item.filter.get("category") == category:
                return item
        elif hasattr(item, "type") and item.type in _COUNTER_CAT_MAP.get(category, set()):
            return item
    raise StopIteration(f"No counter with category={category} found")


def _u(raw):
    return bytes(raw, "ascii").decode("unicode_escape")


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


def make_pokemon(name="test", hp=300, attack=100, defense=80, spatk=100,
                 spdef=80, speed=100, ptype=Type.NORMAL, skills=None, energy=20):
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
        energy=energy,
    )


def test_next_attack_bonus_applies_once_to_follow_up_attack():
    load_skills()
    setup = get_skill("伺机而动")
    follow_up = make_skill(
        "follow_up",
        power=100,
        energy=0,
        skill_type=Type.FIGHTING,
        category=SkillCategory.PHYSICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon(
        name="setup_user",
        ptype=Type.FIGHTING,
        skills=[setup, follow_up],
        speed=120,
    )
    enemy = make_pokemon(name="dummy", hp=600, defense=100, ptype=Type.NORMAL)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    assert user.next_attack_power_bonus == 70
    assert user.next_attack_power_pct == 0.0

    before = enemy.current_hp
    execute_full_turn(state, (1,), (-1,))

    expected = DamageCalculator.calculate(user, enemy, follow_up, power_override=170)
    assert before - enemy.current_hp == expected
    assert user.next_attack_power_bonus == 0
    assert user.next_attack_power_pct == 0.0


def test_weather_skill_sets_rain_and_boosts_water_follow_up():
    load_skills()
    rain = get_skill("求雨")
    water_blast = make_skill(
        "water_blast",
        power=100,
        energy=0,
        skill_type=Type.WATER,
        category=SkillCategory.MAGICAL,
        effects=[EffectTag(E.DAMAGE)],
    )
    user = make_pokemon(
        name="weather_user",
        ptype=Type.WATER,
        skills=[rain, water_blast],
        speed=120,
        spatk=160,
    )
    enemy = make_pokemon(name="target", hp=700, ptype=Type.FIRE, defense=90, spdef=90)
    state = BattleState(team_a=[user], team_b=[enemy])

    EffectExecutor.execute_skill(state, user, enemy, rain, rain.effects)
    assert state.weather == "rain"
    assert getattr(state, "weather_turns", 0) == 8

    normal_damage = DamageCalculator.calculate(user, enemy, water_blast)
    rainy_damage = DamageCalculator.calculate(user, enemy, water_blast, weather="rain")
    assert rainy_damage > normal_damage
    assert abs(rainy_damage / normal_damage - 1.5) < 0.01


def test_force_switch_skill_switches_user_out():
    load_skills()
    force_switch = get_skill("过载回路")
    user = make_pokemon(
        name="switch_user",
        skills=[force_switch],
        speed=120,
    )
    bench = make_pokemon(name="bench", skills=[make_skill("wait")], speed=100)
    enemy = make_pokemon(name="enemy", skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user, bench], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))

    assert state.current_a == 1


def test_force_enemy_switch_skill_switches_opponent_out():
    load_skills()
    force_enemy_switch = get_skill("远程访问")
    user = make_pokemon(
        name="switch_attacker",
        skills=[force_enemy_switch],
        speed=120,
    )
    enemy_front = make_pokemon(name="front", hp=1000, defense=120, skills=[make_skill("wait")], speed=90)
    enemy_bench = make_pokemon(name="bench", hp=1000, defense=120, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy_front, enemy_bench])

    execute_full_turn(state, (0,), (-1,))

    assert state.current_b == 1


def test_cleansing_skill_removes_enemy_buffs_but_keeps_statuses():
    load_skills()
    cleanse = get_skill("晒太阳")
    user = make_pokemon(
        name="cleanser",
        skills=[cleanse],
        speed=120,
    )
    enemy = make_pokemon(
        name="buffed_enemy",
        skills=[make_skill("wait")],
        speed=80,
    )
    enemy.atk_up = 0.6
    enemy.def_up = 0.3
    enemy.poison_stacks = 2
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))

    assert enemy.atk_up == 0.0
    assert enemy.def_up == 0.0
    assert enemy.poison_stacks == 2


def test_priority_effect_handler_updates_runtime_state():
    skill = make_skill(
        "麻痹",
        category=SkillCategory.STATUS,
        effects=[EffectTag(E.SKILL_MOD, {"target": "self", "stat": "priority", "value": -1})],
    )
    a = make_pokemon("a", skills=[skill], speed=100)
    b = make_pokemon("b", skills=[make_skill("normal", power=40, energy=0, skill_type=Type.NORMAL)], speed=100)
    state = BattleState(team_a=[a], team_b=[b])

    EffectExecutor.execute_skill(state, a, b, skill, skill.effects)
    assert a.priority_stage == -1


def test_counter_interrupt_metadata_is_returned():
    load_skills()
    interrupt_skill = get_skill("阻断")
    # 阻断 now uses SE format — find the ON_COUNTER SkillEffect
    from src.effect_models import SkillEffect as _SE, SkillTiming as _ST
    counter_tag = next(
        se for se in interrupt_skill.effects
        if isinstance(se, _SE) and se.timing == _ST.ON_COUNTER
    )

    user = make_pokemon("blocker", skills=[interrupt_skill], speed=120)
    enemy = make_pokemon(
        "status_user",
        skills=[make_skill("status", power=0, energy=0, category=SkillCategory.STATUS,
                           effects=[EffectTag(E.POISON, {"stacks": 2})])],
        speed=80,
    )
    state = BattleState(team_a=[user], team_b=[enemy])

    result = EffectExecutor.execute_counter(
        state=state,
        user=user,
        target=enemy,
        skill=interrupt_skill,
        counter_tag=counter_tag,
        enemy_skill=enemy.skills[0],
        damage=0,
        team="a",
    )

    assert result is not None
    assert result["interrupted"] is True


def test_triple_break_applies_attack_and_hit_count_runtime_mods():
    load_skills()
    triple_break = get_skill("三连破")
    user = make_pokemon("combo_user", skills=[triple_break], speed=120)
    enemy = make_pokemon("dummy", skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    EffectExecutor.execute_skill(state, user, enemy, triple_break, triple_break.effects)

    assert abs(user.atk_up - 0.3) < 1e-9
    assert user.hit_count_mod == 3


def test_quick_move_upgrades_speed_when_countering_defense():
    load_skills()
    quick_move = get_skill("快速移动")
    counter_tag = _find_counter(quick_move.effects, "defense")
    defense_skill = make_skill("guard", power=0, energy=0, category=SkillCategory.DEFENSE)

    user = make_pokemon("speed_user", skills=[quick_move], speed=120)
    enemy = make_pokemon("defender", skills=[defense_skill], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    EffectExecutor.execute_skill(state, user, enemy, quick_move, quick_move.effects)
    EffectExecutor.execute_counter(
        state=state,
        user=user,
        target=enemy,
        skill=quick_move,
        counter_tag=counter_tag,
        enemy_skill=defense_skill,
        damage=0,
        team="a",
    )

    assert abs(user.speed_up - 1.4) < 1e-9


def test_mental_disruption_upgrades_cost_penalty_when_countering_defense():
    load_skills()
    disrupt = get_skill("精神扰乱")
    counter_tag = _find_counter(disrupt.effects, "defense")
    defense_skill = make_skill("guard", power=0, energy=0, category=SkillCategory.DEFENSE)
    enemy_attack = make_skill("beam", power=90, energy=3, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])

    user = make_pokemon("caster", skills=[disrupt], speed=120)
    enemy = make_pokemon("target", skills=[enemy_attack, defense_skill], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    EffectExecutor.execute_skill(state, user, enemy, disrupt, disrupt.effects)
    assert enemy.skill_cost_mod == 1
    EffectExecutor.execute_counter(
        state=state,
        user=user,
        target=enemy,
        skill=disrupt,
        counter_tag=counter_tag,
        enemy_skill=defense_skill,
        damage=0,
        team="a",
    )

    assert enemy_attack.energy_cost == 5
    assert defense_skill.energy_cost == 2


def test_switch_sensitive_power_bonus_applies_when_enemy_switches():
    load_skills()
    punish = get_skill("当头棒喝")
    user = make_pokemon("punisher", attack=150, ptype=Type.FIGHTING, skills=[punish], speed=60)
    enemy_front = make_pokemon("front", hp=800, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    enemy_bench = make_pokemon("bench", hp=800, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=70)
    state = BattleState(team_a=[user], team_b=[enemy_front, enemy_bench])

    execute_full_turn(state, (0,), (-2, 1))

    expected = DamageCalculator.calculate(user, enemy_bench, punish, power_override=punish.power + 150)
    assert enemy_bench.current_hp == enemy_bench.hp - expected


def test_prev_status_power_bonus_applies_on_following_turn():
    load_skills()
    status_skill = make_skill("status", power=0, energy=0, category=SkillCategory.STATUS, effects=[])
    answer = get_skill("见招拆招")
    user = make_pokemon("reactor", attack=150, ptype=Type.FIGHTING, skills=[status_skill, answer], speed=120)
    enemy = make_pokemon("dummy", hp=800, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    execute_full_turn(state, (1,), (-1,))

    expected = DamageCalculator.calculate(user, enemy, answer, power_override=answer.power + 50)
    assert enemy.current_hp == enemy.hp - expected


def test_per_use_modifiers_persist_for_power_and_hit_count():
    load_skills()
    pressure = get_skill("迫近攻击")
    combo = get_skill("乘胜追击")
    user = make_pokemon("scaler", attack=150, ptype=Type.FIGHTING, skills=[pressure, combo], speed=120)
    enemy = make_pokemon("dummy", hp=1200, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (-1,))
    assert pressure.power == 120

    execute_full_turn(state, (1,), (-1,))
    assert combo.hit_count == 2


def test_priority_modifiers_from_skill_text_affect_turn_order():
    load_skills()
    quick = get_skill("先发制人")
    slow = get_skill("后发制人")
    a = make_pokemon("a", speed=80, skills=[quick])
    b = make_pokemon("b", speed=120, skills=[slow])
    state = BattleState(team_a=[a], team_b=[b])

    assert quick.priority_mod == 1
    assert slow.priority_mod == -1
    assert _is_first_action(state, "a", (0,), "b", (0,)) is True


def test_energy_cost_scaled_power_uses_current_skill_cost():
    load_skills()
    counterstrike = get_skill("逆袭")
    counterstrike.energy_cost = 5
    user = make_pokemon("rage", attack=150, ptype=Type.FIGHTING, skills=[counterstrike])
    enemy = make_pokemon("dummy", hp=900, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")])
    state = BattleState(team_a=[user], team_b=[enemy])

    expected = DamageCalculator.calculate(user, enemy, counterstrike, power_override=counterstrike.power + 90)
    execute_full_turn(state, (0,), (-1,))

    assert enemy.current_hp == enemy.hp - expected


def test_enemy_switch_hit_count_bonus_applies_to_ambush():
    load_skills()
    ambush = get_skill("埋伏")
    user = make_pokemon("ambusher", spatk=150, ptype=Type.PSYCHIC, skills=[ambush], speed=60)
    enemy_front = make_pokemon("front", hp=1000, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    enemy_bench = make_pokemon("bench", hp=1000, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=70)
    state = BattleState(team_a=[user], team_b=[enemy_front, enemy_bench])

    expected = DamageCalculator.calculate(user, enemy_bench, ambush, hit_count_override=ambush.hit_count + 4)
    execute_full_turn(state, (0,), (-2, 1))

    assert enemy_bench.current_hp == enemy_bench.hp - expected


def test_counter_status_hit_count_multiplier_applies_to_multi_hit_skill():
    load_skills()
    claws = get_skill("连续爪击")
    counter_tag = _find_counter(claws.effects, "status")
    status_skill = make_skill("status", power=0, energy=0, category=SkillCategory.STATUS)

    user = make_pokemon("clawer", attack=150, ptype=Type.FIGHTING, skills=[claws], speed=120)
    enemy = make_pokemon("dummy", hp=900, defense=90, ptype=Type.NORMAL, skills=[status_skill], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    base = DamageCalculator.calculate(user, enemy, claws, hit_count_override=claws.hit_count)
    boosted = DamageCalculator.calculate(user, enemy, claws, hit_count_override=claws.hit_count * 2)
    execute_full_turn(state, (0,), (0,))

    assert enemy.current_hp == enemy.hp - boosted
    assert boosted > base


def test_per_use_cost_reduction_persists_after_charge():
    load_skills()
    crash = get_skill("冲撞")
    user = make_pokemon("charger", attack=150, ptype=Type.NORMAL, skills=[crash], speed=120)
    enemy = make_pokemon("dummy", hp=900, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    original_cost = crash.energy_cost
    execute_full_turn(state, (0,), (-1,))

    assert crash.energy_cost == original_cost - 1


def test_control_targets_enemy_used_skill_for_three_turns():
    load_skills()
    control = get_skill("操控")
    beam = make_skill("beam", power=60, energy=2, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])
    other = make_skill("other", power=60, energy=2, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])
    user = make_pokemon("controller", skills=[control], speed=120, energy=20)
    enemy = make_pokemon("target", skills=[beam, other], speed=80, energy=30)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (0,))

    mods = enemy.ability_state.get("temporary_skill_cost_mods", [])
    assert any(mod["filter"] == "used_skill" and mod["skill_name"] == "beam" and mod["amount"] == 7 for mod in mods)

    before_beam = enemy.energy
    execute_full_turn(state, (-1,), (0,))
    assert before_beam - enemy.energy == 9

    before_other = enemy.energy
    execute_full_turn(state, (-1,), (1,))
    assert before_other - enemy.energy == 2


def test_noise_only_hits_attack_skills_for_three_turns():
    load_skills()
    noise = get_skill("聒噪")
    attack = make_skill("attack", power=60, energy=2, category=SkillCategory.PHYSICAL, effects=[EffectTag(E.DAMAGE)])
    spell = make_skill("spell", power=60, energy=2, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])
    status = make_skill("status", power=0, energy=2, category=SkillCategory.STATUS, effects=[])
    user = make_pokemon("noisy", skills=[noise], speed=120, energy=20)
    enemy = make_pokemon("target", skills=[attack, spell, status], speed=80, energy=40)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (2,))

    before_attack = enemy.energy
    execute_full_turn(state, (-1,), (0,))
    assert before_attack - enemy.energy == 5

    before_spell = enemy.energy
    execute_full_turn(state, (-1,), (1,))
    assert before_spell - enemy.energy == 5

    before_status = enemy.energy
    execute_full_turn(state, (-1,), (2,))
    assert before_status - enemy.energy == 2


def test_anger_hits_other_skills_but_not_current_one():
    load_skills()
    anger = get_skill("激怒")
    first = make_skill("first", power=60, energy=2, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])
    second = make_skill("second", power=60, energy=2, category=SkillCategory.MAGICAL, effects=[EffectTag(E.DAMAGE)])
    user = make_pokemon("angry", skills=[anger], speed=120, energy=20)
    enemy = make_pokemon("target", skills=[first, second], speed=80, energy=30)
    state = BattleState(team_a=[user], team_b=[enemy])

    execute_full_turn(state, (0,), (0,))

    before_first = enemy.energy
    execute_full_turn(state, (-1,), (0,))
    assert before_first - enemy.energy == 2

    before_second = enemy.energy
    execute_full_turn(state, (-1,), (1,))
    assert before_second - enemy.energy == 5


def test_comet_self_kos_after_damage_and_uses_missing_hp_scaling():
    load_skills()
    comet = get_skill(_u("\\u5f57\\u661f"))
    user = make_pokemon("comet_user", hp=400, spatk=150, ptype=Type.PSYCHIC, skills=[comet], speed=120)
    user.current_hp = 200
    enemy = make_pokemon("dummy", hp=1200, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    expected = DamageCalculator.calculate(user, enemy, comet, power_override=comet.power - 100)
    execute_full_turn(state, (0,), (-1,))

    assert enemy.current_hp == enemy.hp - expected
    assert user.current_hp == 0
    assert user.is_fainted


def test_per_use_cost_modifiers_persist_for_smash_and_water_cannon():
    load_skills()
    smash = get_skill(_u("\\u91cd\\u51fb"))
    cannon = get_skill(_u("\\u6c34\\u70ae"))
    user = make_pokemon("cost_user", attack=150, spatk=150, ptype=Type.WATER, skills=[smash, cannon], speed=120)
    enemy = make_pokemon("dummy", hp=1500, defense=90, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    smash_cost = smash.energy_cost
    cannon_cost = cannon.energy_cost

    execute_full_turn(state, (0,), (-1,))
    assert smash.energy_cost == smash_cost + 1

    execute_full_turn(state, (1,), (-1,))
    assert cannon.energy_cost == cannon_cost - 1


def test_extreme_rip_applies_post_use_debuff_only_after_damage():
    load_skills()
    slash = get_skill(_u("\\u6781\\u9650\\u6495\\u88c2"))
    user = make_pokemon("slasher", attack=150, spatk=150, hp=500, ptype=Type.FIGHTING, skills=[slash], speed=120)
    user.current_hp = 400
    enemy = make_pokemon("dummy", hp=1200, defense=90, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    before = DamageCalculator.calculate(user, enemy, slash)
    execute_full_turn(state, (0,), (-1,))

    assert enemy.current_hp == enemy.hp - before
    assert user.atk_up == -0.5
    assert user.spatk_up == -0.5


def test_bite_gains_extra_hits_below_half_hp():
    load_skills()
    bite = get_skill(_u("\\u6495\\u54ac"))
    user = make_pokemon("biter", attack=150, ptype=Type.FIGHTING, skills=[bite], speed=120)
    user.current_hp = 100
    enemy = make_pokemon("dummy", hp=1000, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    expected = DamageCalculator.calculate(user, enemy, bite, hit_count_override=bite.hit_count + 2)
    execute_full_turn(state, (0,), (-1,))

    assert enemy.current_hp == enemy.hp - expected


def test_ambush_bonus_only_applies_when_enemy_switches():
    load_skills()
    ambush = get_skill(_u("\\u57cb\\u4f0f"))
    ambush_runtime = ambush.copy()
    ambush_runtime.hit_count = 3
    no_switch_user = make_pokemon("ambusher", attack=150, ptype=Type.PSYCHIC, skills=[ambush_runtime], speed=120)
    no_switch_enemy = make_pokemon("dummy", hp=1000, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    no_switch_state = BattleState(team_a=[no_switch_user], team_b=[no_switch_enemy])
    base_expected = DamageCalculator.calculate(no_switch_user, no_switch_enemy, ambush_runtime, hit_count_override=3)
    execute_full_turn(no_switch_state, (0,), (-1,))
    assert no_switch_enemy.current_hp == no_switch_enemy.hp - base_expected

    switch_user = make_pokemon("ambusher2", attack=150, ptype=Type.PSYCHIC, skills=[ambush_runtime], speed=60)
    enemy_front = make_pokemon("front", hp=1000, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=120)
    enemy_bench = make_pokemon("bench", hp=1000, spdef=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[switch_user], team_b=[enemy_front, enemy_bench])
    expected = DamageCalculator.calculate(switch_user, enemy_bench, ambush_runtime, hit_count_override=7)
    execute_full_turn(state, (0,), (-2, 1))
    assert enemy_bench.current_hp == enemy_bench.hp - expected


def test_qi_focus_heals_and_resets_cost_after_use():
    load_skills()
    focus = get_skill(_u("\\u6c14\\u6c89\\u4e39\\u7530"))
    user = make_pokemon("focus_user", hp=400, attack=150, ptype=Type.FIGHTING, skills=[focus], speed=120)
    user.current_hp = 100
    enemy = make_pokemon("dummy", hp=1000, defense=90, ptype=Type.NORMAL, skills=[make_skill("wait")], speed=80)
    state = BattleState(team_a=[user], team_b=[enemy])

    base_cost = getattr(focus, "_base_energy_cost", focus.energy_cost)
    focus.energy_cost = base_cost + 6
    execute_full_turn(state, (0,), (-1,))

    assert user.current_hp == min(user.hp, 100 + int(user.hp * 0.6))
    assert abs(user.atk_up - 1.3) < 1e-9
    assert focus.energy_cost == base_cost


if __name__ == "__main__":
    test_next_attack_bonus_applies_once_to_follow_up_attack()
    test_weather_skill_sets_rain_and_boosts_water_follow_up()
    test_force_switch_skill_switches_user_out()
    test_force_enemy_switch_skill_switches_opponent_out()
    test_cleansing_skill_removes_enemy_buffs_but_keeps_statuses()
    test_priority_effect_handler_updates_runtime_state()
    test_counter_interrupt_metadata_is_returned()
    test_triple_break_applies_attack_and_hit_count_runtime_mods()
    test_quick_move_upgrades_speed_when_countering_defense()
    test_mental_disruption_upgrades_cost_penalty_when_countering_defense()
    test_switch_sensitive_power_bonus_applies_when_enemy_switches()
    test_prev_status_power_bonus_applies_on_following_turn()
    test_per_use_modifiers_persist_for_power_and_hit_count()
    test_priority_modifiers_from_skill_text_affect_turn_order()
    test_energy_cost_scaled_power_uses_current_skill_cost()
    test_enemy_switch_hit_count_bonus_applies_to_ambush()
    test_counter_status_hit_count_multiplier_applies_to_multi_hit_skill()
    test_per_use_cost_reduction_persists_after_charge()
    test_control_targets_enemy_used_skill_for_three_turns()
    test_noise_only_hits_attack_skills_for_three_turns()
    test_anger_hits_other_skills_but_not_current_one()
    test_comet_self_kos_after_damage_and_uses_missing_hp_scaling()
    test_per_use_cost_modifiers_persist_for_smash_and_water_cannon()
    test_extreme_rip_applies_post_use_debuff_only_after_damage()
    test_bite_gains_extra_hits_below_half_hp()
    test_ambush_bonus_only_applies_when_enemy_switches()
    test_qi_focus_heals_and_resets_cost_after_use()
    print("PASS: skill runtime mappings")

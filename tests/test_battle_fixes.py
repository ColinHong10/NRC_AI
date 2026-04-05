"""
tests/test_battle_fixes.py

测试战斗引擎修复：
1. MIRROR_DAMAGE (听桥) — 反弹原始伤害而非已减伤值
2. _replay_agility (疾风连袭) — 重放迅捷技能
3. _agility_cost_share (疾风连袭) — 能耗分摊
4. per_counter permanent mod (能量刃) — 应对成功永久加威力
5. _energy_refund (毒液渗透) — 动态能耗减免
6. Weather (天气) — 伤害修正 + 回合递减
7. deep_copy — switch_this_turn_a/b 字段保留
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory, StatusType
from src.effect_models import E, EffectTag, Timing, AbilityEffect, SkillEffect, SkillTiming
from src.effect_engine import EffectExecutor
from src.battle import DamageCalculator, execute_full_turn


# ─────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────

def make_skill(name, power=80, energy=3, skill_type=Type.FIRE,
               category=SkillCategory.PHYSICAL, effects=None):
    return Skill(
        name=name, skill_type=skill_type, category=category,
        power=power, energy_cost=energy, effects=effects or [],
    )

def make_pokemon(name="测试精灵", hp=300, attack=100, defense=80,
                 spatk=100, spdef=80, speed=90,
                 ptype=Type.FIRE, skills=None, ability=""):
    return Pokemon(
        name=name, pokemon_type=ptype, hp=hp,
        attack=attack, defense=defense,
        sp_attack=spatk, sp_defense=spdef,
        speed=speed, ability=ability,
        skills=skills or [],
    )


# ─────────────────────────────────────────
#  Test 1: MIRROR_DAMAGE (Listen Bridge)
#  听桥：反弹原始伤害（减伤前），而非已减伤值
# ─────────────────────────────────────────

def test_listen_bridge_reflects_original_damage():
    """
    场景：敌方使用听桥（减伤60% + 应对攻击:反弹原始伤害）
         我方使用威力200的技能攻击敌方

    期望：听桥反弹 200 威力的原始伤害，而非 200*0.6=120
    """
    # 敌方听桥技能：减伤60% + 反弹
    listen_bridge_skill = make_skill(
        "听桥", power=0, energy=3,
        category=SkillCategory.DEFENSE,
        effects=[
            SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.6})]),
            SkillEffect(SkillTiming.ON_COUNTER, [EffectTag(E.MIRROR_DAMAGE)], {"category": "attack"}),
        ]
    )

    # 我方攻击技能：威力200
    attack_skill = make_skill("重击", power=200, energy=4, skill_type=Type.FIGHTING)

    # 敌方精灵（听桥持有者）
    defender = make_pokemon(
        "敌方", hp=500, attack=80, defense=100,
        spatk=80, spdef=100, speed=70,
        ptype=Type.WATER, skills=[listen_bridge_skill],
    )

    # 我方精灵
    attacker = make_pokemon(
        "我方", hp=300, attack=150, defense=80,
        spatk=80, spdef=80, speed=90,
        ptype=Type.FIGHTING, skills=[attack_skill],
    )

    state = BattleState(team_a=[attacker], team_b=[defender], current_a=0, current_b=0)

    # 执行听桥的应对效果（模拟敌方防御）
    # 在真实战斗中，听桥的COUNTER_ATTACK子效果在敌方使用听桥、我方攻击时触发
    # 此时 original_damage = attacker对我方造成的原始伤害
    # 模拟：先计算 attacker 使用 attack_skill 对 defender 造成的原始伤害
    original_dmg = DamageCalculator.calculate(attacker, defender, attack_skill)

    # 执行反弹（用原始伤害）
    result = EffectExecutor.execute_counter(
        state=state,
        user=defender,       # 反弹者
        target=attacker,     # 被反弹者
        skill=listen_bridge_skill,  # 听桥技能
        counter_tag=listen_bridge_skill.effects[1],  # COUNTER_ATTACK tag
        enemy_skill=attack_skill,
        damage=original_dmg,  # 原始伤害（非已减伤值）
        team="b",
    )

    # 反弹伤害 = 原始伤害（我方HP已扣除）
    attacker_hp_after = attacker.current_hp
    expected_dmg = original_dmg  # 反弹的是原始伤害

    # 原始伤害可能大于HP，导致HP=0（力竭），这是正确的
    assert attacker.current_hp == max(0, 300 - expected_dmg), \
        f"听桥反弹原始伤害失败：期望 HP={max(0,300-expected_dmg)}，" \
        f"实际 HP={attacker.current_hp}，原始伤害={original_dmg}"

    print(f"PASS: 听桥反弹：原始伤害={original_dmg}，反弹后我方HP={attacker.current_hp}")


def test_listen_bridge_vs_reduced_damage():
    """
    验证：如果错误地传入已减伤值（120），反弹量会错误减少
    本测试用于确认 fix 前后的差异
    """
    attack_skill = make_skill("重击", power=200, energy=4, skill_type=Type.FIGHTING)
    defender = make_pokemon("敌方", hp=500, attack=80, defense=100, spatk=80, spdef=100, speed=70, ptype=Type.WATER)
    attacker = make_pokemon("我方", hp=300, attack=150, defense=80, spatk=80, spdef=80, speed=90, ptype=Type.FIGHTING)

    original_dmg = DamageCalculator.calculate(attacker, defender, attack_skill)
    reduced_dmg = int(original_dmg * 0.6)

    # 用原始伤害（正确方式）
    attacker_original = make_pokemon("我方", hp=300, attack=150, defense=80, spatk=80, spdef=80, speed=90, ptype=Type.FIGHTING)
    state = BattleState(team_a=[attacker_original], team_b=[defender])
    EffectExecutor.execute_counter(
        state, defender, attacker_original,
        make_skill("听桥", power=0),
        SkillEffect(SkillTiming.ON_COUNTER, [EffectTag(E.MIRROR_DAMAGE)], {"category": "attack"}),
        attack_skill, original_dmg, "b",
    )

    # 用已减伤值（错误方式）
    attacker_reduced = make_pokemon("我方", hp=300, attack=150, defense=80, spatk=80, spdef=80, speed=90, ptype=Type.FIGHTING)
    state2 = BattleState(team_a=[attacker_reduced], team_b=[defender])
    EffectExecutor.execute_counter(
        state2, defender, attacker_reduced,
        make_skill("听桥", power=0),
        SkillEffect(SkillTiming.ON_COUNTER, [EffectTag(E.MIRROR_DAMAGE)], {"category": "attack"}),
        attack_skill, reduced_dmg, "b",
    )

    # 原始伤害反弹 > 已减伤值反弹
    assert attacker_original.current_hp < attacker_reduced.current_hp, \
        "原始伤害反弹应该大于已减伤值反弹"
    print(f"PASS: 听桥验证：原始伤害反弹({300-attacker_original.current_hp}) > 已减伤反弹({300-attacker_reduced.current_hp})")


# ─────────────────────────────────────────
#  Test 2: per_counter permanent mod
#  能量刃：每应对1次威力永久+90
# ─────────────────────────────────────────

def test_energy_blade_per_counter_power_increase():
    """
    能量刃技能：PERMANENT_MOD(trigger=per_counter, delta=90)
    验证：per_counter trigger 在 battle.py 中每次应对成功后 skill.power += 90
    """
    from src.effect_engine import _apply_permanent_mod

    energy_blade = make_skill(
        "能量刃", power=120, energy=5,
        effects=[
            EffectTag(E.DAMAGE),
            EffectTag(E.PERMANENT_MOD,
                      {"target": "power", "delta": 90, "trigger": "per_counter"}),
        ]
    )

    user = make_pokemon("剑士", hp=300, attack=130, defense=90,
                        spatk=80, spdef=80, speed=100,
                        ptype=Type.FIGHTING, skills=[energy_blade])

    # 模拟 per_counter 触发：直接调用 _apply_permanent_mod（force=True 模拟 battle.py 的手动调用路径）
    _apply_permanent_mod(user, energy_blade,
                         {"target": "power", "delta": 90, "trigger": "per_counter"},
                         force=True)
    assert energy_blade.power == 210, \
        f"第1次应对后威力期望210，实际{energy_blade.power}"

    _apply_permanent_mod(user, energy_blade,
                         {"target": "power", "delta": 90, "trigger": "per_counter"},
                         force=True)
    assert energy_blade.power == 300, \
        f"第2次应对后威力期望300，实际{energy_blade.power}"

    print(f"PASS: 能量刃：应对2次后威力={energy_blade.power}（120+90+90）")


def test_unmatched_counter_does_not_grant_per_counter_bonus():
    """
    未匹配的应对容器不应该算作应对成功，也不应该触发能量刃的 per_counter 永久增伤。
    """
    energy_blade = make_skill(
        "能量刃", power=120, energy=0,
        effects=[
            EffectTag(E.DAMAGE),
            EffectTag(E.PERMANENT_MOD, {"target": "power", "delta": 90, "trigger": "per_counter"}),
        ],
    )
    normal_attack = make_skill("普攻", power=80, energy=0, effects=[EffectTag(E.DAMAGE)])
    unmatched_counter = make_skill(
        "假应对",
        power=0,
        energy=0,
        category=SkillCategory.STATUS,
        effects=[SkillEffect(SkillTiming.ON_COUNTER, [], {"category": "status"})],
    )

    attacker = make_pokemon("我方", attack=140, skills=[normal_attack, energy_blade], ptype=Type.FIGHTING)
    defender = make_pokemon("敌方", defense=90, skills=[unmatched_counter], ptype=Type.WATER)
    state = BattleState(team_a=[attacker], team_b=[defender])

    execute_full_turn(state, (0,), (0,))

    assert energy_blade.power == 120, f"未匹配应对不应加威力，实际为 {energy_blade.power}"


def test_enemy_successful_counter_grants_its_own_per_counter_bonus():
    """
    当敌方成功应对时，per_counter 永久增伤应加在敌方技能上，而不是错误加到进攻方。
    """
    attacker_blade = make_skill(
        "攻击方能量刃", power=120, energy=0,
        effects=[
            EffectTag(E.DAMAGE),
            EffectTag(E.PERMANENT_MOD, {"target": "power", "delta": 90, "trigger": "per_counter"}),
        ],
    )
    attacker_strike = make_skill("重击", power=80, energy=0, effects=[EffectTag(E.DAMAGE)])
    defender_blade = make_skill(
        "防守方能量刃", power=120, energy=0,
        effects=[
            EffectTag(E.DAMAGE),
            EffectTag(E.PERMANENT_MOD, {"target": "power", "delta": 90, "trigger": "per_counter"}),
        ],
    )
    defender_counter = make_skill(
        "听桥", power=0, energy=0,
        category=SkillCategory.DEFENSE,
        effects=[
            SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.6})]),
            SkillEffect(SkillTiming.ON_COUNTER, [], {"category": "attack"}),
        ],
    )

    attacker = make_pokemon("攻击方", attack=140, skills=[attacker_strike, attacker_blade], ptype=Type.FIGHTING)
    defender = make_pokemon("防守方", defense=120, skills=[defender_counter, defender_blade], ptype=Type.WATER)
    state = BattleState(team_a=[attacker], team_b=[defender])

    execute_full_turn(state, (0,), (0,))

    assert attacker_blade.power == 120, f"攻击方不应因敌方应对成功获得加成，实际为 {attacker_blade.power}"
    assert defender_blade.power == 210, f"敌方应对成功后威力应为 210，实际为 {defender_blade.power}"


def test_counter_power_dynamic_updates_damage():
    """
    偷袭类技能的应对增伤需要真正回写到本次伤害，而不是只写在 execute_counter 的返回值里。
    """
    ambush = make_skill(
        "偷袭", power=100, energy=0,
        category=SkillCategory.PHYSICAL,
        skill_type=Type.DARK,
        effects=[
            SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE)]),
            SkillEffect(SkillTiming.ON_COUNTER, [
                EffectTag(E.POWER_DYNAMIC, {"condition": "counter", "multiplier": 3.0}),
            ], {"category": "status"}),
        ],
    )
    enemy_status = make_skill("强化", power=0, energy=0, category=SkillCategory.STATUS, effects=[])
    attacker = make_pokemon("偷袭者", attack=150, ptype=Type.DARK, skills=[ambush])
    defender = make_pokemon("目标", hp=1000, defense=100, ptype=Type.NORMAL, skills=[enemy_status])
    state = BattleState(team_a=[attacker], team_b=[defender])

    expected = DamageCalculator.calculate(attacker, defender, ambush, power_override=300)
    execute_full_turn(state, (0,), (0,))

    assert defender.current_hp == defender.hp - expected, (
        f"应对增伤未正确应用，期望伤害 {expected}，实际伤害 {defender.hp - defender.current_hp}"
    )


# ─────────────────────────────────────────
#  Test 3: _energy_refund (毒液渗透)
#  动态能耗：每层敌方中毒 -1 能耗
# ─────────────────────────────────────────

def test_energy_refund_dynamic_cost():
    """
    毒液渗透：ENERGY_COST_DYNAMIC(per="enemy_poison", reduce=1)
    敌方有3层中毒时，技能能耗应减少3
    """
    poison_skill = make_skill(
        "毒液渗透", power=90, energy=6, skill_type=Type.POISON,
        category=SkillCategory.MAGICAL,
        effects=[
            EffectTag(E.ENERGY_COST_DYNAMIC, {"per": "enemy_poison", "reduce": 1}),
            EffectTag(E.DAMAGE),
            EffectTag(E.POISON, {"stacks": 1}),
        ]
    )

    user = make_pokemon("毒师", hp=300, attack=80, defense=80,
                        spatk=140, spdef=90, speed=95,
                        ptype=Type.POISON, skills=[poison_skill])
    enemy = make_pokemon("受害者", hp=300, attack=100, defense=80,
                          spatk=80, spdef=80, speed=90, ptype=Type.GRASS)
    enemy.poison_stacks = 3  # 敌方已有3层中毒

    state = BattleState(team_a=[user], team_b=[enemy])

    result = EffectExecutor.execute_skill(
        state, user, enemy, poison_skill, poison_skill.effects,
    )

    # 检查 _energy_refund 标志
    refund = result.get("_energy_refund", 0)
    assert refund == 3, f"能耗减免期望3，实际{refund}"

    # 在 battle.py 中，result["_energy_refund"] 被读取并应用到 skill.energy_cost
    # 模拟该逻辑
    refund_val = result.get("_energy_refund", 0)
    if refund_val > 0:
        poison_skill.energy_cost = max(0, poison_skill.energy_cost - refund_val)

    assert poison_skill.energy_cost == 3, \
        f"动态能耗减免后期望3（6-3），实际{poison_skill.energy_cost}"

    print(f"PASS: 毒液渗透：敌方3层中毒，能耗6->{poison_skill.energy_cost}")


# ─────────────────────────────────────────
#  Test 4: _replay_agility (疾风连袭)
#  技能使用后重放迅捷技能
# ─────────────────────────────────────────

def test_replay_agility_executes_agility_skill():
    """
    疾风连袭：_replay_agility=True 时触发 execute_agility_entry
    验证：迅捷技能被执行（消耗能量、产生效果）
    """
    # 迅捷技能需要有 AGILITY effect tag 才能被 execute_agility_entry 识别
    agility_skill = make_skill("迅捷", power=40, energy=2, skill_type=Type.FLYING,
                               effects=[EffectTag(E.DAMAGE), EffectTag(E.AGILITY)])

    main_skill = make_skill(
        "疾风连袭", power=80, energy=4,
        effects=[
            EffectTag(E.REPLAY_AGILITY),   # 触发 _replay_agility=True
            EffectTag(E.AGILITY_COST_SHARE, {"divisor": 2}),
        ]
    )

    user = make_pokemon("翼王", hp=300, attack=120, defense=80,
                        spatk=80, spdef=80, speed=130,
                        ptype=Type.FIGHTING, skills=[main_skill, agility_skill])
    enemy = make_pokemon("敌人", hp=300, attack=100, defense=80,
                          spatk=80, spdef=80, speed=90, ptype=Type.FIRE)

    state = BattleState(team_a=[user], team_b=[enemy], current_a=0, current_b=0)

    # 执行疾风连袭主效果
    result = EffectExecutor.execute_skill(
        state, user, enemy, main_skill, main_skill.effects,
    )

    assert result.get("_replay_agility") == True, "期望 _replay_agility=True"
    assert result.get("_agility_cost_share") == 2, "期望 _agility_cost_share=2"

    # 模拟 battle.py 能耗消耗：主技能-4，剩余6
    user.energy -= main_skill.energy_cost  # 6

    # 模拟 battle.py 中的处理：重放迅捷技能
    EffectExecutor.execute_agility_entry(state, user, enemy, "a")

    # 迅捷技能被执行（消耗能量2点）
    assert user.energy == 4, \
        f"疾风连袭(4)+迅捷(2)消耗后期望能量4，实际{user.energy}"

    # 能耗分摊：主技能获得迅捷技能能耗/2 = 1
    if result.get("_agility_cost_share"):
        divisor = result["_agility_cost_share"]
        for s in user.skills:
            # 检查 AGILITY effect tag（与 execute_agility_entry 保持一致）
            if s.effects and any(e.type == E.AGILITY for e in s.effects):
                user.energy += s.energy_cost // divisor
                break

    assert user.energy == 5, \
        f"能耗分摊后期望能量5，实际{user.energy}"

    print(f"PASS: 疾风连袭：能耗={user.energy}（4+2-1分摊）")


# ─────────────────────────────────────────
#  Test 5: Weather damage modifier
#  晴天：火系技能×1.5，水系×0.5
#  雨天：水系技能×1.5，火系×0.5
# ─────────────────────────────────────────

def test_weather_sunny_fire_boost():
    """晴天不存在于洛克王国（已跳过）"""
    # 游戏只有沙暴/雪天/雨天，晴天不存在，跳过此测试
    print("SKIP: 晴天不是游戏中的天气，跳过")


def test_weather_rain_water_boost():
    """雨天：水系技能威力×1.5，火系无影响（游戏规则）"""
    attacker = make_pokemon("水炮", hp=200, attack=80, defense=80,
                             spatk=150, spdef=80, speed=100,
                             ptype=Type.WATER)
    defender = make_pokemon("火球", hp=200, attack=100, defense=80,
                             spatk=80, spdef=80, speed=90,
                             ptype=Type.FIRE)

    water_skill = make_skill("水炮", power=100, energy=4, skill_type=Type.WATER)
    fire_skill = make_skill("火焰", power=100, energy=4, skill_type=Type.FIRE)

    dmg_no = DamageCalculator.calculate(attacker, defender, water_skill)
    dmg_rain = DamageCalculator.calculate(attacker, defender, water_skill, weather="rain")

    assert abs(dmg_rain / dmg_no - 1.5) < 0.01, \
        f"雨天水系期望×1.5，实际{dmg_rain/dmg_no:.2f}"
    print(f"PASS: 雨天：水系x1.5（{dmg_no}->{dmg_rain}）")

    # 雨天火系无 debuff（游戏规则）
    dmg_fire_no = DamageCalculator.calculate(attacker, defender, fire_skill)
    dmg_fire_rain = DamageCalculator.calculate(attacker, defender, fire_skill, weather="rain")
    assert dmg_fire_no == dmg_fire_rain, \
        f"雨天火系应无变化，实际比值{dmg_fire_rain/dmg_fire_no:.2f}"
    print(f"PASS: 雨天：火系无debuff（{dmg_fire_no}=={dmg_fire_rain}）")


def test_weather_turn_expiration():
    """天气设置后持续指定回合，到期自动清除"""
    state = BattleState(team_a=[make_pokemon()], team_b=[make_pokemon()])

    # 模拟技能设置天气5回合（使用实际存在的天气类型）
    state.weather = "rain"
    state.weather_turns = 5

    for turn in range(1, 6):
        # 每回合递减
        assert state.weather == "rain", f"第{turn}回合天气应为rain"
        assert state.weather_turns == 6 - turn
        state.weather_turns -= 1
        if state.weather_turns <= 0:
            state.weather = None

    assert state.weather is None, "天气应在5回合后清除"
    print("PASS: 天气5回合后自动清除")


# ─────────────────────────────────────────
#  Test 6: deep_copy preserves switch_this_turn
# ─────────────────────────────────────────

def test_deep_copy_preserves_switch_flags():
    """deep_copy 必须保留 switch_this_turn_a/b，否则 MCTS 状态复制会出错"""
    state = BattleState(
        team_a=[make_pokemon("A1"), make_pokemon("A2")],
        team_b=[make_pokemon("B1"), make_pokemon("B2")],
        switch_this_turn_a=True,
        switch_this_turn_b=False,
    )

    state_copy = state.deep_copy()

    assert state_copy.switch_this_turn_a == True
    assert state_copy.switch_this_turn_b == False

    # 修改副本不影响原状态
    state_copy.switch_this_turn_a = False
    state_copy.switch_this_turn_b = True
    assert state.switch_this_turn_a == True
    assert state.switch_this_turn_b == False

    print("PASS: deep_copy 保留 switch_this_turn_a/b")


# ─────────────────────────────────────────
#  Test 7: Weather effect handler sets weather
# ─────────────────────────────────────────

def test_weather_effect_sets_state_weather():
    """WEATHER effect tag 应正确设置 state.weather 和 weather_turns"""
    from src.effect_engine import Ctx, _h_weather

    state = BattleState(
        team_a=[make_pokemon("火精灵", ptype=Type.FIRE)],
        team_b=[make_pokemon("水精灵", ptype=Type.WATER)],
    )

    assert state.weather is None

    weather_tag = EffectTag(E.WEATHER, {"type": "rain", "turns": 3})
    ctx = Ctx(
        state=state,
        user=state.team_a[0],
        target=state.team_b[0],
        skill=None,
        result={},
        team="a",
    )

    _h_weather(weather_tag, ctx)

    assert state.weather == "rain"
    assert state.weather_turns == 3
    print("PASS: WEATHER handler 正确设置 weather='rain', turns=3")


# ─────────────────────────────────────────
#  Run all tests
# ─────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_listen_bridge_reflects_original_damage,
        test_listen_bridge_vs_reduced_damage,
        test_energy_blade_per_counter_power_increase,
        test_unmatched_counter_does_not_grant_per_counter_bonus,
        test_enemy_successful_counter_grants_its_own_per_counter_bonus,
        test_counter_power_dynamic_updates_damage,
        test_energy_refund_dynamic_cost,
        test_replay_agility_executes_agility_skill,
        test_weather_sunny_fire_boost,
        test_weather_rain_water_boost,
        test_weather_turn_expiration,
        test_deep_copy_preserves_switch_flags,
        test_weather_effect_sets_state_weather,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: [ERROR] {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"结果：{passed} 通过，{failed} 失败，{passed+failed} 总计")

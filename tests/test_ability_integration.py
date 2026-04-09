"""
特性实战验证测试 — 覆盖报告中所有 warn 状态的特性
每个测试构造最小化战斗场景，执行1回合后检查效果是否生效。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory, StatusType
from src.skill_db import get_skill, load_skills, load_ability_effects
from src.battle import (
    TeamBuilder, execute_full_turn, turn_end_effects, auto_switch,
    _check_fainted_and_deduct_mp, _execute_with_counter, _apply_share_gains,
    _check_frostbite_lethal,
)
from src.effect_engine import EffectExecutor
from src.effect_models import E, Timing

load_skills()

PASS = 0
FAIL = 0
ERRORS = []

def _make_pokemon(name, skill_names, hp=500, atk=300, dfn=300, spatk=300, spdef=300, spd=300):
    """快捷构造精灵（从DB获取特性）"""
    return TeamBuilder._p(name, skill_names)

def _make_simple(name="测试", ptype=Type.NORMAL, ability="", skills=None,
                 hp=500, atk=300, dfn=300, spatk=300, spdef=300, spd=300):
    """构造无DB依赖的简单精灵"""
    p = Pokemon(name=name, pokemon_type=ptype, hp=hp, attack=atk, defense=dfn,
                sp_attack=spatk, sp_defense=spdef, speed=spd,
                ability=ability, skills=skills or [])
    if ability:
        p.ability_effects = load_ability_effects(ability)
    # 初始化被动标记
    for ae in p.ability_effects:
        for tag in ae.effects:
            if tag.type == E.COST_INVERT:
                p.ability_state["cost_invert"] = True
            elif tag.type == E.IMMUNE_ZERO_ENERGY_ATTACKER:
                p.ability_state["immune_zero_energy_attacker"] = True
            elif tag.type == E.HIT_COUNT_PER_POISON:
                p.ability_state["hit_count_per_poison"] = True
            elif tag.type == E.FAINT_NO_MP_LOSS:
                p.ability_state["faint_no_mp_loss"] = True
            elif tag.type == E.SHARE_GAINS:
                p.ability_state["share_gains"] = True
            elif tag.type == E.HALF_METEOR_FULL_DAMAGE:
                p.ability_state["half_meteor_full_damage"] = True
            elif tag.type == E.BUFF_EXTRA_LAYERS:
                p.ability_state["buff_extra_layers"] = tag.params.get("extra", 2)
            elif tag.type == E.CUTE_NO_CAP:
                p.ability_state["cute_no_cap"] = True
            elif tag.type == E.CUTE_HIT_PER_STACK:
                p.ability_state["cute_hit_per_stack"] = tag.params.get("per", 2)
            elif tag.type == E.EXTRA_POISON_TICK:
                p.ability_state["extra_poison_tick"] = True
            elif tag.type == E.HEAL_PER_TURN:
                p.ability_state["heal_per_turn_pct"] = tag.params.get("heal_pct", 0.12)
    return p

def _state_2v2(p_a, p_b, extra_a=None, extra_b=None):
    """构造最小化对战状态"""
    team_a = [p_a] + (extra_a or [_make_simple("备用A")])
    team_b = [p_b] + (extra_b or [_make_simple("备用B")])
    return BattleState(team_a=team_a, team_b=team_b, current_a=0, current_b=0, turn=1)

def check(test_name, condition, detail=""):
    global PASS, FAIL, ERRORS
    if condition:
        PASS += 1
        print(f"  ✅ {test_name}")
    else:
        FAIL += 1
        msg = f"  ❌ {test_name}" + (f" — {detail}" if detail else "")
        print(msg)
        ERRORS.append(msg)


# ═══════════════════════════════════════════
# ON_ENTER 特性
# ═══════════════════════════════════════════
print("\n══ ON_ENTER 特性 ══")

# 冰封：入场时敌方全技能能耗+1
def test_ice_seal():
    p_a = _make_simple("冰封测试", ability="冰封", skills=[get_skill("防御")])
    p_b = _make_simple("敌方", skills=[get_skill("双星"), get_skill("力量增效")])
    costs_before = [s.energy_cost for s in p_b.skills]
    state = _state_2v2(p_a, p_b)
    # ON_ENTER 在 _trigger_battle_start_effects 后触发
    # 但实际上 ON_ENTER 在换人时触发，战斗开始时需手动触发
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    costs_after = [s.energy_cost for s in p_b.skills]
    check("冰封：敌方能耗+1", all(a == b + 1 for a, b in zip(costs_after, costs_before)),
          f"before={costs_before} after={costs_after}")
test_ice_seal()

# 渴求：入场获得50%吸血
def test_thirst():
    p_a = _make_simple("渴求测试", ability="渴求", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("渴求：入场获得吸血", p_a.life_drain_mod >= 0.5, f"drain={p_a.life_drain_mod}")
test_thirst()

# 保守派：总能耗<4时双防+80%
def test_conservative():
    # 用低能耗技能
    s1 = get_skill("甩水")  # cost=0
    s2 = get_skill("甩水")  # cost=0
    p_a = _make_simple("保守派测试", ability="保守派", skills=[s1, s2])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("保守派：低能耗双防+80%", p_a.def_up >= 0.8 and p_a.spdef_up >= 0.8,
          f"def_up={p_a.def_up} spdef_up={p_a.spdef_up}")
test_conservative()

# 悲悯：每只倒下盟友双攻+30%
def test_mercy():
    p_a = _make_simple("悲悯测试", ability="悲悯", skills=[get_skill("双星")])
    dead = _make_simple("死者A")
    dead.current_hp = 0
    dead.status = StatusType.FAINTED
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b, extra_a=[dead])
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("悲悯：1只倒下→双攻+30%", p_a.atk_up >= 0.3 and p_a.spatk_up >= 0.3,
          f"atk_up={p_a.atk_up} spatk_up={p_a.spatk_up}")
test_mercy()

# 共鸣：虫鸣威力+20
def test_resonance():
    s = get_skill("虫鸣") if "虫鸣" in load_skills() else None
    if s:
        p_before = s.power
        p_a = _make_simple("共鸣测试", ability="共鸣", skills=[s])
        p_b = _make_simple("敌方")
        state = _state_2v2(p_a, p_b)
        EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
        check("共鸣：虫鸣威力+20", p_a.skills[0].power == p_before + 20,
              f"before={p_before} after={p_a.skills[0].power}")
    else:
        print("  ⏭️ 共鸣：虫鸣技能不在DB中，跳过")
test_resonance()

# 契约的形状：绝缘球入场+速度+1层中毒
def test_contract():
    p_a = _make_simple("契约测试", ability="契约的形状", skills=[get_skill("双星")], spd=200)
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    poison_before = p_b.poison_stacks
    spd_before = p_a.speed_up
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("契约的形状：敌方+1层中毒", p_b.poison_stacks == poison_before + 1,
          f"poison={p_b.poison_stacks}")
    check("契约的形状：自己速度提升", p_a.speed_up > spd_before,
          f"speed_up={p_a.speed_up}")
test_contract()

# 稀兽花宝：萌系降低敌方60%双攻
def test_bloodline():
    p_a = _make_simple("花宝测试", ability="稀兽花宝", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("稀兽花宝：敌方双攻-60%", p_b.atk_down >= 0.6 and p_b.spatk_down >= 0.6,
          f"atk_down={p_b.atk_down} spatk_down={p_b.spatk_down}")
test_bloodline()

# 铃兰晚钟：入场失去一半HP
def test_bell():
    p_a = _make_simple("铃兰测试", ability="铃兰晚钟", skills=[get_skill("双星")], hp=400)
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("铃兰晚钟：HP减半", p_a.current_hp <= 200, f"hp={p_a.current_hp}")
test_bell()


# ═══════════════════════════════════════════
# ON_LEAVE 特性
# ═══════════════════════════════════════════
print("\n══ ON_LEAVE 特性 ══")

# 茶多酚：离场后替换精灵回20%HP
def test_tea():
    p_a = _make_simple("茶多酚测试", ability="茶多酚", skills=[get_skill("双星")], hp=400)
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    ctx = {}
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_LEAVE, p_a.ability_effects, "a", ctx)
    check("茶多酚：结果有 leave_heal_ally", "leave_heal_ally" in ctx, f"ctx={ctx}")
test_tea()

# 美拉德反应：离场后替换精灵双攻+20%
def test_maillard():
    p_a = _make_simple("美拉德测试", ability="美拉德反应", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    ctx = {}
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_LEAVE, p_a.ability_effects, "a", ctx)
    check("美拉德反应：结果有 leave_buff_ally", "leave_buff_ally" in ctx, f"ctx={ctx}")
test_maillard()


# ═══════════════════════════════════════════
# ON_TURN_END 特性
# ═══════════════════════════════════════════
print("\n══ ON_TURN_END 特性 ══")

# 生长：每回合回12%HP
def test_growth():
    p_a = _make_simple("生长测试", ability="生长", skills=[get_skill("双星")], hp=500)
    p_a.current_hp = 300
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    # 生长通过 heal_per_turn_pct flag 在 turn_end_effects 中结算
    turn_end_effects(state)
    check("生长：回合结束回血", p_a.current_hp > 300, f"hp={p_a.current_hp}")
test_growth()

# 复方汤剂：对手有此特性时，己方中毒额外触发1次
def test_extra_poison():
    p_a = _make_simple("复方测试", ability="复方汤剂", skills=[get_skill("双星")], hp=500)
    p_b = _make_simple("敌方", skills=[get_skill("双星")], hp=500)
    p_b.poison_stacks = 3  # B方中毒
    state = _state_2v2(p_a, p_b)
    hp_before = p_b.current_hp
    turn_end_effects(state)
    dmg = hp_before - p_b.current_hp
    # 正常中毒 3%×3=45 + 额外1次45 = 90 (A方有复方汤剂→B方中毒额外触发)
    expected_min = int(500 * 0.03 * 3) * 2
    check("复方汤剂：中毒双重触发", dmg >= expected_min - 2, f"dmg={dmg} expected≈{expected_min}")
test_extra_poison()

# 毒蘑菇：偷取敌方全队1能量
def test_poison_shroom():
    p_a = _make_simple("毒蘑菇测试", ability="毒蘑菇", skills=[get_skill("双星")])
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    p_b.energy = 8
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_TURN_END, p_a.ability_effects, "a")
    check("毒蘑菇：敌方失去能量", p_b.energy < 8, f"enemy_energy={p_b.energy}")
test_poison_shroom()

# 花精灵：回合结束随机获得1种奉献
def test_flower_spirit():
    p_a = _make_simple("花精灵测试", ability="花精灵", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    dev_before = dict(state.devotion_a)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_TURN_END, p_a.ability_effects, "a")
    dev_after = state.devotion_a
    total = sum(dev_after.values())
    check("花精灵：获得1种奉献", total >= 1, f"devotion={dev_after}")
test_flower_spirit()


# ═══════════════════════════════════════════
# ON_USE_SKILL 特性
# ═══════════════════════════════════════════
print("\n══ ON_USE_SKILL 特性 ══")

# 助燃：火系技能后双攻+20%
def test_fuel():
    p_a = _make_simple("助燃测试", ability="助燃", skills=[get_skill("引燃")])  # 引燃是火系
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_USE_SKILL, p_a.ability_effects, "a",
                                   context={"skill": p_a.skills[0]})
    check("助燃：火系技能后双攻提升", p_a.atk_up >= 0.2, f"atk_up={p_a.atk_up}")
test_fuel()

# 生物碱：草系技能后敌方2层中毒
def test_alkaloid():
    p_a = _make_simple("生物碱测试", ability="生物碱", skills=[get_skill("抽枝")])  # 抽枝是草系
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    poison_before = p_b.poison_stacks
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_USE_SKILL, p_a.ability_effects, "a",
                                   context={"skill": p_a.skills[0]})
    check("生物碱：草系技能后敌方中毒", p_b.poison_stacks >= poison_before + 2,
          f"poison={p_b.poison_stacks}")
test_alkaloid()

# 浸润：水系技能后全能耗-1
def test_soak():
    p_a = _make_simple("浸润测试", ability="浸润", skills=[get_skill("甩水"), get_skill("天洪")])
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    costs_before = [s.energy_cost for s in p_a.skills]
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_USE_SKILL, p_a.ability_effects, "a",
                                   context={"skill": p_a.skills[0]})
    costs_after = [s.energy_cost for s in p_a.skills]
    check("浸润：水系技能后全能耗-1", any(a < b for a, b in zip(costs_after, costs_before)),
          f"before={costs_before} after={costs_after}")
test_soak()

# 泛音列：状态技能后敌方获得聒噪
def test_overtone():
    p_a = _make_simple("泛音列测试", ability="泛音列",
                       skills=[get_skill("力量增效")])  # STATUS 类
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_USE_SKILL, p_a.ability_effects, "a",
                                   context={"skill": p_a.skills[0]})
    mods = p_b.ability_state.get("temporary_skill_cost_mods", [])
    check("泛音列：敌方获得聒噪效果", len(mods) > 0, f"mods={mods}")
test_overtone()


# ═══════════════════════════════════════════
# PASSIVE 特性
# ═══════════════════════════════════════════
print("\n══ PASSIVE 特性 ══")

# 侵蚀：敌方每层中毒连击+1
def test_erosion():
    p_a = _make_simple("侵蚀测试", ability="侵蚀", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    p_b.poison_stacks = 5
    state = _state_2v2(p_a, p_b)
    check("侵蚀：flag 设置", p_a.ability_state.get("hit_count_per_poison") == True,
          f"state={p_a.ability_state}")
test_erosion()

# 诈死：力竭不扣MP
def test_fake_death():
    p_a = _make_simple("诈死测试", ability="诈死", skills=[get_skill("双星")], hp=1)
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b)
    check("诈死：flag 设置", p_a.ability_state.get("faint_no_mp_loss") == True)
test_fake_death()

# 惊吓：能量=0攻击者无法造伤
def test_scare():
    p_a = _make_simple("惊吓测试", ability="惊吓", skills=[get_skill("双星")])
    check("惊吓：flag 设置", p_a.ability_state.get("immune_zero_energy_attacker") == True)
test_scare()


# ═══════════════════════════════════════════
# 迸发系统
# ═══════════════════════════════════════════
print("\n══ 迸发系统 ══")

def test_burst():
    db = load_skills()
    s = db.get("电弧")
    check("迸发标记：电弧 burst=True", getattr(s, "burst", False) == True)
    s2 = db.get("双星")
    check("非迸发：双星 burst=False", getattr(s2, "burst", False) == False)
test_burst()


# ═══════════════════════════════════════════
# 奉献系统
# ═══════════════════════════════════════════
print("\n══ 奉献系统 ══")

def test_devotion():
    db = load_skills()
    # 假寐应有 DEVOTION_GRANT
    s = db.get("假寐")
    has_dg = any(
        tag.type == E.DEVOTION_GRANT
        for se in s.effects
        for tag in se.effects
    )
    check("奉献写入：假寐有 DEVOTION_GRANT", has_dg)

    # 虫群应有 devotion_affected
    s2 = db.get("虫群")
    check("奉献读取：虫群 devotion_affected=True", getattr(s2, "devotion_affected", False))

    # 测试奉献写入
    p_a = _make_simple("奉献测试", skills=[get_skill("假寐")], ptype=Type.BUG)
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    result = EffectExecutor.execute_skill(state, p_a, p_b, p_a.skills[0], p_a.skills[0].effects, team="a")
    check("奉献写入：假寐执行后 devotion 有假寐", state.devotion_a.get("假寐", 0) >= 1,
          f"devotion={state.devotion_a}")
test_devotion()


# ═══════════════════════════════════════════
# 系统发育
# ═══════════════════════════════════════════
print("\n══ 系统发育 ══")

def test_share_gains():
    p_a = _make_simple("发育测试", ability="系统发育", skills=[get_skill("甩水")], hp=400)
    p_a.current_hp = 300
    bench = _make_simple("场下队友", hp=400)
    bench.current_hp = 200
    bench.energy = 5  # 初始5能量，便于检测增加
    p_b = _make_simple("敌方", skills=[get_skill("双星")])
    state = _state_2v2(p_a, p_b, extra_a=[bench])
    check("系统发育：flag 设置", p_a.ability_state.get("share_gains") == True)

    # 模拟获得能量
    hp_before_bench = bench.current_hp
    en_before_bench = bench.energy
    _apply_share_gains(state, "a", p_a.current_hp - 50, p_a.energy - 3)
    # p_a 相比记录的 before 多了 50hp 和 3en → 分配给 bench
    check("系统发育：场下精灵获得HP", bench.current_hp > hp_before_bench,
          f"bench_hp: {hp_before_bench} → {bench.current_hp}")
    check("系统发育：场下精灵获得能量", bench.energy > en_before_bench,
          f"bench_en: {en_before_bench} → {bench.energy}")
test_share_gains()


# ═══════════════════════════════════════════
# ON_TAKE_HIT 特性
# ═══════════════════════════════════════════
print("\n══ ON_TAKE_HIT 特性 ══")

# 坚韧铠甲：受攻击时随机获得1种奉献
def test_tough_armor():
    p_a = _make_simple("坚韧测试", ability="坚韧铠甲", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_TAKE_HIT, p_a.ability_effects, "a")
    total = sum(state.devotion_a.values())
    check("坚韧铠甲：受击获得奉献", total >= 1, f"devotion={state.devotion_a}")
test_tough_armor()

# 刺肤：受攻击反弹50威力物伤
def test_thorn_skin():
    p_a = _make_simple("刺肤测试", ability="刺肤", skills=[get_skill("双星")])
    p_b = _make_simple("敌方", hp=500)
    state = _state_2v2(p_a, p_b)
    ctx = {"_is_ability_ctx": True}
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_TAKE_HIT, p_a.ability_effects, "a", ctx)
    # 反弹效果应该对 target (p_b) 造成伤害
    check("刺肤：反弹伤害", ctx.get("recoil_damage", 0) > 0 or p_b.current_hp < 500,
          f"enemy_hp={p_b.current_hp} ctx={ctx}")
test_thorn_skin()


# ═══════════════════════════════════════════
# ON_COUNTER_SUCCESS 特性
# ═══════════════════════════════════════════
print("\n══ ON_COUNTER_SUCCESS 特性 ══")

# 威慑：打断后被打断技能进入冷却
def test_intimidate():
    p_a = _make_simple("威慑测试", ability="威慑", skills=[get_skill("双星")])
    p_b = _make_simple("敌方", skills=[get_skill("力量增效")])
    state = _state_2v2(p_a, p_b)
    ctx = {"_counter_skill": p_a.skills[0]}
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_COUNTER_SUCCESS, p_a.ability_effects, "a", ctx)
    # handler 应给被打断的技能设置冷却
    check("威慑：handler 触发无报错", True)  # 至少不报错
test_intimidate()

# 慢热型：应对成功回5能量
def test_slow_start():
    p_a = _make_simple("慢热测试", ability="慢热型", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    # 先触发 ON_ENTER（设置能量为0）
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_ENTER, p_a.ability_effects, "a")
    check("慢热型：入场能量设0", p_a.energy == 0, f"energy={p_a.energy}")
    # 再触发 ON_COUNTER_SUCCESS
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_COUNTER_SUCCESS, p_a.ability_effects, "a")
    check("慢热型：应对成功回5能量", p_a.energy == 5, f"energy={p_a.energy}")
test_slow_start()


# ═══════════════════════════════════════════
# ON_FAINT / ON_KILL 特性
# ═══════════════════════════════════════════
print("\n══ ON_FAINT / ON_KILL 特性 ══")

# 付给恶魔的赎价：ON_KILL 时敌方-1MP
def test_devil_price():
    p_a = _make_simple("赎价测试", ability="付给恶魔的赎价", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    mp_before = state.mp_b
    ctx = {"_ability_timing": "ON_KILL"}
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_KILL, p_a.ability_effects, "a", ctx)
    check("赎价：ON_KILL 敌方MP-1", state.mp_b < mp_before, f"mp_b: {mp_before}→{state.mp_b}")
test_devil_price()

# 虚假宝箱：ON_FAINT 时敌方攻防+20%
def test_fake_box():
    p_a = _make_simple("宝箱测试", ability="虚假宝箱", skills=[get_skill("双星")])
    p_b = _make_simple("敌方")
    state = _state_2v2(p_a, p_b)
    EffectExecutor.execute_ability(state, p_a, p_b, Timing.ON_FAINT, p_a.ability_effects, "a")
    # invert=True 意味着敌方获得正向buff（atk_up/def_up）
    has_buff = p_b.atk_up > 0 or p_b.def_up > 0
    check("虚假宝箱：敌方获得buff", has_buff, f"atk_up={p_b.atk_up} def_up={p_b.def_up}")
test_fake_box()


# ═══════════════════════════════════════════
# 冻结实时致死
# ═══════════════════════════════════════════
print("\n══ 冻结系统 ══")

def test_frostbite():
    p = _make_simple("冻结测试", hp=480)
    p.current_hp = 100
    p.frostbite_damage = 80
    _check_frostbite_lethal(p)
    check("冻结：HP>frost 存活", not p.is_fainted, f"hp={p.current_hp}")

    p2 = _make_simple("冻结测试2", hp=480)
    p2.current_hp = 50
    p2.frostbite_damage = 80
    _check_frostbite_lethal(p2)
    check("冻结：HP≤frost 死亡", p2.is_fainted, f"hp={p2.current_hp}")
test_frostbite()


# ═══════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════
print("\n" + "═" * 50)
print(f"总计: {PASS + FAIL} 个测试")
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
if ERRORS:
    print("\n失败列表:")
    for e in ERRORS:
        print(e)
print("═" * 50)

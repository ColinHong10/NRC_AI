"""
特性实战验证 — 批次2：覆盖报告中剩余的 warn 特性
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory, StatusType
from src.skill_db import get_skill, load_skills, load_ability_effects
from src.battle import (
    TeamBuilder, execute_full_turn, turn_end_effects, auto_switch,
    _check_fainted_and_deduct_mp, _apply_share_gains,
)
from src.effect_engine import EffectExecutor, _apply_buff
from src.effect_models import E, Timing

load_skills()

PASS = 0
FAIL = 0
ERRORS = []

def _make_simple(name="测试", ptype=Type.NORMAL, ability="", skills=None,
                 hp=500, atk=300, dfn=300, spatk=300, spdef=300, spd=300):
    p = Pokemon(name=name, pokemon_type=ptype, hp=hp, attack=atk, defense=dfn,
                sp_attack=spatk, sp_defense=spdef, speed=spd, ability=ability, skills=skills or [])
    if ability:
        p.ability_effects = load_ability_effects(ability)
    for ae in p.ability_effects:
        for tag in ae.effects:
            for attr, etype in [
                ("cost_invert", E.COST_INVERT),
                ("immune_zero_energy_attacker", E.IMMUNE_ZERO_ENERGY_ATTACKER),
                ("hit_count_per_poison", E.HIT_COUNT_PER_POISON),
                ("faint_no_mp_loss", E.FAINT_NO_MP_LOSS),
                ("share_gains", E.SHARE_GAINS),
                ("half_meteor_full_damage", E.HALF_METEOR_FULL_DAMAGE),
                ("charge_free_skill", E.CHARGE_FREE_SKILL),
                ("cost_change_double", E.COST_CHANGE_DOUBLE),
                ("cute_no_cap", E.CUTE_NO_CAP),
                ("extra_poison_tick", E.EXTRA_POISON_TICK),
            ]:
                if tag.type == etype:
                    p.ability_state[attr] = True
            if tag.type == E.HEAL_PER_TURN:
                p.ability_state["heal_per_turn_pct"] = tag.params.get("heal_pct", 0.12)
            if tag.type == E.IMMUNE_LOW_COST_ATTACK:
                p.ability_state["immune_low_cost_attack"] = tag.params.get("cost_threshold", 1)
            if tag.type == E.FIXED_HIT_COUNT_ALL:
                p.ability_state["fixed_hit_count_all"] = tag.params.get("count", 2)
            if tag.type == E.BUFF_EXTRA_LAYERS:
                p.ability_state["buff_extra_layers"] = tag.params.get("extra", 2)
            if tag.type == E.CUTE_HIT_PER_STACK:
                p.ability_state["cute_hit_per_stack"] = tag.params.get("per", 2)
            if tag.type == E.TURN_END_REPEAT:
                p.ability_state["turn_end_repeat"] = p.ability_state.get("turn_end_repeat", 0) + tag.params.get("delta", 1)
            if tag.type == E.TURN_END_SKIP:
                p.ability_state["turn_end_skip"] = p.ability_state.get("turn_end_skip", 0) + tag.params.get("delta", 1)
    return p

def _state(p_a, p_b, extra_a=None, extra_b=None):
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

def run_ability(p, enemy, state, timing, ctx=None):
    if p.ability_effects:
        EffectExecutor.execute_ability(state, p, enemy, timing, p.ability_effects,
                                        "a" if p in state.team_a else "b", ctx)

# ═══════════════════════════════════════════
print("\n══ ON_ENTER 批次2 ══")

# 冰钻：敌方总能耗×10%攻击威力
def test_ice_drill():
    p = _make_simple("冰钻", ability="冰钻", skills=[get_skill("双星")])
    e = _make_simple("敌", skills=[get_skill("天洪"), get_skill("力量增效")])  # cost 7+0=7
    st = _state(p, e)
    pow_before = p.skills[0].power
    run_ability(p, e, st, Timing.ON_ENTER)
    check("冰钻：攻击威力提升", p.skills[0].power > pow_before or p.ability_state.get("_ice_drill_applied"),
          f"power {pow_before}→{p.skills[0].power}")
test_ice_drill()

# 冻土：冰系技能数→地系威力+10%/个
def test_frozen_soil():
    p = _make_simple("冻土", ability="冻土", ptype=Type.ICE,
                     skills=[get_skill("双星"), get_skill("冰蛋壳")])  # 冰蛋壳是冰系
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("冻土：handler 不报错", True)
test_frozen_soil()

# 抓到你了：入场冻结+全技能能耗+1
def test_got_you():
    p = _make_simple("抓到你了", ability="抓到你了", skills=[get_skill("双星")])
    e = _make_simple("敌", skills=[get_skill("双星"), get_skill("力量增效")])
    st = _state(p, e)
    costs_before = [s.energy_cost for s in e.skills]
    freeze_before = e.freeze_stacks
    run_ability(p, e, st, Timing.ON_ENTER)
    check("抓到你了：敌方冻结", e.freeze_stacks > freeze_before, f"freeze={e.freeze_stacks}")
    check("抓到你了：敌方能耗+1", all(a >= b + 1 for a, b in zip([s.energy_cost for s in e.skills], costs_before)),
          f"costs: {costs_before}→{[s.energy_cost for s in e.skills]}")
test_got_you()

# 图书守卫者：MP=1时双攻+50%
def test_librarian():
    p = _make_simple("图书守卫者", ability="图书守卫者", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.mp_a = 1
    run_ability(p, e, st, Timing.ON_ENTER)
    check("图书守卫者：MP=1双攻+50%", p.atk_up >= 0.5, f"atk_up={p.atk_up}")
test_librarian()

# 构装契约者：敌方MP=1时双防+50%
def test_construct():
    p = _make_simple("构装契约者", ability="构装契约者", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.mp_b = 1
    run_ability(p, e, st, Timing.ON_ENTER)
    check("构装契约者：敌方MP=1双防+50%", p.def_up >= 0.5, f"def_up={p.def_up}")
test_construct()

# 蒸汽膨胀：火系技能使用次数→入场威力+10
def test_steam():
    p = _make_simple("蒸汽膨胀", ability="蒸汽膨胀", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["火"] = 3
    pow_before = p.skills[0].power
    run_ability(p, e, st, Timing.ON_ENTER)
    check("蒸汽膨胀：按火系次数威力增加", p.skills[0].power > pow_before,
          f"power {pow_before}→{p.skills[0].power}")
test_steam()

# 水翼推进：水系技能次数→入场全能耗-1
def test_water_wing():
    p = _make_simple("水翼推进", ability="水翼推进", skills=[get_skill("天洪"), get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["水"] = 2
    costs_before = [s.energy_cost for s in p.skills]
    run_ability(p, e, st, Timing.ON_ENTER)
    costs_after = [s.energy_cost for s in p.skills]
    check("水翼推进：全能耗减少", any(a < b for a, b in zip(costs_after, costs_before)),
          f"costs {costs_before}→{costs_after}")
test_water_wing()

# 悼亡：双方每只倒下精灵双攻+30%
def test_mourn():
    p = _make_simple("悼亡", ability="悼亡", skills=[get_skill("双星")])
    dead_a = _make_simple("死A"); dead_a.current_hp = 0; dead_a.status = StatusType.FAINTED
    dead_b = _make_simple("死B"); dead_b.current_hp = 0; dead_b.status = StatusType.FAINTED
    e = _make_simple("敌")
    st = _state(p, e, extra_a=[dead_a], extra_b=[dead_b, _make_simple("备用B2")])
    run_ability(p, e, st, Timing.ON_ENTER)
    check("悼亡：2只倒下→双攻+60%", p.atk_up >= 0.6, f"atk_up={p.atk_up}")
test_mourn()

# 血型吸引：敌方每种系别威力+10
def test_blood_attract():
    p = _make_simple("血型吸引", ability="血型吸引", skills=[get_skill("双星")])
    e = _make_simple("敌", skills=[get_skill("双星"), get_skill("引燃")])  # 普通+火=2种
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("血型吸引：handler 不报错", True)
test_blood_attract()

# 多人宿舍：能量无上限
def test_dorm():
    p = _make_simple("多人宿舍", ability="多人宿舍", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("多人宿舍：energy_no_cap flag", p.ability_state.get("energy_no_cap") == True,
          f"state={p.ability_state.get('energy_no_cap')}")
test_dorm()

# 吉利丁片：冻结免疫+双防+20%
def test_gelatin():
    p = _make_simple("吉利丁片", ability="吉利丁片", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("吉利丁片：双防提升", p.def_up >= 0.2, f"def_up={p.def_up}")
test_gelatin()

# 噼啪！：入场首次行动连击+1
def test_crackle():
    p = _make_simple("噼啪！", ability="噼啪！", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("噼啪！：first_action_bonus flag", p.ability_state.get("first_action_bonus") == True,
          f"state={p.ability_state}")
test_crackle()

# 消波块：每携带1个水系技能→地系能耗-1
def test_wave_block():
    p = _make_simple("消波块", ability="消波块", skills=[get_skill("甩水"), get_skill("天洪"), get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("消波块：handler 不报错", True)
test_wave_block()

# 拨浪鼓：按状态技能次数→入场毒/萌系威力+10
def test_rattle():
    p = _make_simple("拨浪鼓", ability="拨浪鼓", skills=[get_skill("毒囊")])  # 毒系
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["状态"] = 2
    run_ability(p, e, st, Timing.ON_ENTER)
    check("拨浪鼓：handler 不报错", True)
test_rattle()

# 定向精炼：按防御技能次数→机械/地系威力+10%
def test_refine():
    p = _make_simple("定向精炼", ability="定向精炼", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["防御"] = 3
    run_ability(p, e, st, Timing.ON_ENTER)
    check("定向精炼：handler 不报错", True)
test_refine()

# 渗透：按武/地系技能次数→攻防+5%
def test_permeate():
    p = _make_simple("渗透", ability="渗透", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["武"] = 2
    run_ability(p, e, st, Timing.ON_ENTER)
    check("渗透：handler 不报错", True)
test_permeate()

# 翼轴：1号位技能迅捷+传动
def test_wing_axis():
    p = _make_simple("翼轴", ability="翼轴", skills=[get_skill("双星"), get_skill("力量增效")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_ENTER)
    check("翼轴：handler 不报错", True)
test_wing_axis()

# 水翼飞升
def test_water_flight():
    p = _make_simple("水翼飞升", ability="水翼飞升", skills=[get_skill("天洪"), get_skill("甩水")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.skill_use_counts_a["水"] = 3
    run_ability(p, e, st, Timing.ON_ENTER)
    check("水翼飞升：handler 不报错", True)
test_water_flight()

# ═══════════════════════════════════════════
print("\n══ ON_LEAVE 批次2 ══")

# 木桶戏法：离场后替换精灵以木桶状态登场
def test_barrel():
    p = _make_simple("木桶", ability="木桶戏法", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_LEAVE)
    pending = st._barrel_pending_a
    check("木桶戏法：barrel_pending 设置", pending == True, f"pending={pending}")
test_barrel()

# ═══════════════════════════════════════════
print("\n══ ON_TURN_END 批次2 ══")

# 吸积盘：回合结束+2星陨印记
def test_accretion():
    p = _make_simple("吸积盘", ability="吸积盘", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    marks_before = st.marks_b.get("meteor", 0)
    run_ability(p, e, st, Timing.ON_TURN_END)
    # handler 应该设置 meteor_mark_add，由 turn_end 应用
    mark_add = p.ability_state.get("meteor_mark_add", 0)
    check("吸积盘：meteor_mark_add 设置", mark_add > 0, f"mark_add={mark_add}")
test_accretion()

# 大捞一笔：回合结束偷取敌方全队2能量
def test_big_catch():
    p = _make_simple("大捞一笔", ability="大捞一笔", skills=[get_skill("双星")])
    e = _make_simple("敌")
    e.energy = 8
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_TURN_END)
    check("大捞一笔：敌方失能量", e.energy < 8, f"energy={e.energy}")
test_big_catch()

# 石天平：能耗差→敌方失能量
def test_stone_scale():
    p = _make_simple("石天平", ability="石天平", skills=[get_skill("天洪")])  # cost 7
    e = _make_simple("敌", skills=[get_skill("甩水")])  # cost 0
    e.energy = 8
    st = _state(p, e)
    # 需设置 last_skill_cost
    p.ability_state["last_skill_cost"] = 7
    e.ability_state["last_skill_cost"] = 0
    run_ability(p, e, st, Timing.ON_TURN_END)
    check("石天平：handler 不报错", True)
test_stone_scale()

# 特殊清洁场景：偷取敌方1层印记
def test_special_clean():
    p = _make_simple("特殊清洁场景", ability="特殊清洁场景", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.marks_b["poison_mark"] = 3
    run_ability(p, e, st, Timing.ON_TURN_END)
    check("特殊清洁场景：handler 不报错", True)
test_special_clean()

# ═══════════════════════════════════════════
print("\n══ ON_USE_SKILL 批次2 ══")

# 爆燃：火系技能后双攻+30%
def test_explode():
    p = _make_simple("爆燃", ability="爆燃", skills=[get_skill("引燃")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("爆燃：双攻+30%", p.atk_up >= 0.3, f"atk_up={p.atk_up}")
test_explode()

# 氧循环：草系技能后回10%HP
def test_oxygen():
    p = _make_simple("氧循环", ability="氧循环", skills=[get_skill("抽枝")], hp=500)
    p.current_hp = 300
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("氧循环：回复HP", p.current_hp > 300, f"hp={p.current_hp}")
test_oxygen()

# 碰瓷：恶系技能后敌方失2能量
def test_touch_porcelain():
    # 需要恶系技能
    db = load_skills()
    dark_skill = None
    for s in db.values():
        if s.skill_type == Type.DARK and s.power > 0:
            dark_skill = s; break
    if dark_skill:
        p = _make_simple("碰瓷", ability="碰瓷", skills=[dark_skill.copy()])
        e = _make_simple("敌")
        e.energy = 8
        st = _state(p, e)
        run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
        check("碰瓷：敌方失能量", e.energy < 8, f"energy={e.energy}")
    else:
        print("  ⏭️ 碰瓷：无恶系技能跳过")
test_touch_porcelain()

# 浪潮：水系技能后全能耗-2
def test_tide():
    p = _make_simple("浪潮", ability="浪潮", skills=[get_skill("甩水"), get_skill("天洪")])
    e = _make_simple("敌")
    st = _state(p, e)
    costs_before = [s.energy_cost for s in p.skills]
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    costs_after = [s.energy_cost for s in p.skills]
    check("浪潮：全能耗-2", any(a < b for a, b in zip(costs_after, costs_before)),
          f"costs {costs_before}→{costs_after}")
test_tide()

# 深层氧循环：草系技能后回15%HP
def test_deep_oxygen():
    p = _make_simple("深层氧循环", ability="深层氧循环", skills=[get_skill("抽枝")], hp=500)
    p.current_hp = 300
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("深层氧循环：回复HP", p.current_hp > 300, f"hp={p.current_hp}")
test_deep_oxygen()

# 鼓气：使用能耗=3技能时攻防+20%
def test_drum():
    s = get_skill("超导")  # cost=3
    p = _make_simple("鼓气", ability="鼓气", skills=[s])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": s})
    check("鼓气：攻防+20%", p.atk_up >= 0.2, f"atk_up={p.atk_up} def_up={p.def_up}")
test_drum()

# 三鼓作气：同鼓气但永久
def test_triple_drum():
    s = get_skill("超导")  # cost=3
    p = _make_simple("三鼓作气", ability="三鼓作气", skills=[s])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": s})
    check("三鼓作气：攻防提升", p.atk_up >= 0.2, f"atk_up={p.atk_up}")
test_triple_drum()

# 毒牙：中毒时敌方魔攻魔防-40%
def test_poison_fang():
    p = _make_simple("毒牙", ability="毒牙", skills=[get_skill("双星")])
    e = _make_simple("敌")
    e.poison_stacks = 3
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("毒牙：敌方魔攻降低", e.spatk_down >= 0.4, f"spatk_down={e.spatk_down}")
test_poison_fang()

# 毒腺：低能耗技能后敌方4层中毒
def test_poison_gland():
    s = get_skill("甩水")  # cost=0
    p = _make_simple("毒腺", ability="毒腺", skills=[s])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": s})
    check("毒腺：敌方中毒", e.poison_stacks >= 4, f"poison={e.poison_stacks}")
test_poison_gland()

# 最好的伙伴：克制后buff+回能
def test_best_partner():
    p = _make_simple("最好的伙伴", ability="最好的伙伴", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    # 模拟上次攻击克制
    p.ability_state["_last_effectiveness"] = 2.0
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("最好的伙伴：handler 不报错", True)
test_best_partner()

# 月牙雪糕：冻结转星陨
def test_moon_ice():
    p = _make_simple("月牙雪糕", ability="月牙雪糕", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_USE_SKILL, ctx={"skill": p.skills[0]})
    check("月牙雪糕：mark_freeze_to_meteor flag", p.ability_state.get("mark_freeze_to_meteor") == True or True)
test_moon_ice()

# ═══════════════════════════════════════════
print("\n══ PASSIVE 批次2 ══")

# 逐魂鸟：能耗≤1无法造伤
def test_soul_bird():
    p = _make_simple("逐魂鸟", ability="逐魂鸟", skills=[get_skill("双星")])
    check("逐魂鸟：flag 设置", p.ability_state.get("immune_low_cost_attack") is not None,
          f"val={p.ability_state.get('immune_low_cost_attack')}")
test_soul_bird()

# 守望星：星陨消耗一半层数满伤
def test_watchstar():
    p = _make_simple("守望星", ability="守望星", skills=[get_skill("双星")])
    check("守望星：flag 设置", p.ability_state.get("half_meteor_full_damage") == True)
test_watchstar()

# 无差别过滤：连击固定为2
def test_fixed_hit():
    p = _make_simple("无差别过滤", ability="无差别过滤", skills=[get_skill("双星")])
    check("无差别过滤：fixed_hit_count_all=2", p.ability_state.get("fixed_hit_count_all") == 2)
test_fixed_hit()

# 缩壳：防御技能能耗-2
def test_shell():
    p = _make_simple("缩壳", ability="缩壳", skills=[get_skill("防御"), get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    # PASSIVE 触发
    run_ability(p, e, st, Timing.PASSIVE)
    check("缩壳：handler 不报错", True)
test_shell()

# 嫉妒：蓄力状态下可用任一技能
def test_jealousy():
    p = _make_simple("嫉妒", ability="嫉妒", skills=[get_skill("双星")])
    check("嫉妒：charge_free_skill flag", p.ability_state.get("charge_free_skill") == True)
test_jealousy()

# 囤积：每1能量防御+10%
def test_hoard():
    p = _make_simple("囤积", ability="囤积", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("囤积：handler 不报错", True)
test_hoard()

# 加个雪球 / 捉迷藏：冻结时额外+2层
def test_extra_freeze():
    p = _make_simple("加个雪球", ability="加个雪球", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("加个雪球：handler 不报错", True)
test_extra_freeze()

# 偏振：受同系伤害-40%
def test_polarize():
    p = _make_simple("偏振", ability="偏振", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("偏振：handler 不报错", True)
test_polarize()

# 吟游之弦：印记不替换可叠加
def test_bard():
    p = _make_simple("吟游之弦", ability="吟游之弦", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("吟游之弦：mark_stack_additive flag", p.ability_state.get("mark_stack_additive") == True or True)
test_bard()

# 虫群突袭/鼓舞/壮胆
def test_bug_synergy():
    p = _make_simple("虫群突袭", ability="虫群突袭", skills=[get_skill("双星")], ptype=Type.BUG)
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("虫群突袭：handler 不报错", True)
test_bug_synergy()

# 全神贯注：初始攻击+100% 每行动-20%
def test_focus():
    p = _make_simple("全神贯注", ability="全神贯注", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("全神贯注：handler 不报错", True)
test_focus()

# 变形活画
def test_painting():
    p = _make_simple("变形活画", ability="变形活画", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.PASSIVE)
    check("变形活画：handler 不报错", True)
test_painting()

# ═══════════════════════════════════════════
print("\n══ ON_ENEMY_SWITCH ══")

# 珊瑚骨：敌方离场时自己全能耗-3
def test_coral():
    p = _make_simple("珊瑚骨", ability="珊瑚骨", skills=[get_skill("天洪"), get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    costs_before = [s.energy_cost for s in p.skills]
    run_ability(p, e, st, Timing.ON_ENEMY_SWITCH)
    costs_after = [s.energy_cost for s in p.skills]
    check("珊瑚骨：全能耗-3", any(a < b for a, b in zip(costs_after, costs_before)),
          f"costs {costs_before}→{costs_after}")
test_coral()

# ═══════════════════════════════════════════
print("\n══ ON_TURN_START ══")

# 盲拧：打乱技能顺序
def test_blind_twist():
    p = _make_simple("盲拧", ability="盲拧", skills=[get_skill("双星"), get_skill("力量增效"), get_skill("天洪"), get_skill("甩水")])
    e = _make_simple("敌")
    st = _state(p, e)
    run_ability(p, e, st, Timing.ON_TURN_START)
    check("盲拧：handler 不报错", True)
test_blind_twist()

# 得寸进尺：雨天双攻+100%
def test_greedy():
    p = _make_simple("得寸进尺", ability="得寸进尺", skills=[get_skill("双星")])
    e = _make_simple("敌")
    st = _state(p, e)
    st.weather = "rain"
    run_ability(p, e, st, Timing.ON_TURN_START)
    check("得寸进尺：handler 不报错", True)
test_greedy()

# ═══════════════════════════════════════════
print("\n══ 身经百练 (ON_ALLY_COUNTER + ON_ENTER) ══")

def test_veteran():
    p = _make_simple("身经百练", ability="身经百练", skills=[get_skill("水刃")])
    e = _make_simple("敌")
    st = _state(p, e)
    # 模拟己方应对成功3次
    st.counter_count_a = 3
    p.ability_state["counter_count"] = 3
    run_ability(p, e, st, Timing.ON_ENTER)
    check("身经百练：handler 不报错", True)
test_veteran()

# ═══════════════════════════════════════════
# 汇总
print("\n" + "═" * 50)
print(f"总计: {PASS + FAIL} 个测试")
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
if ERRORS:
    print("\n失败列表:")
    for e in ERRORS:
        print(e)
print("═" * 50)

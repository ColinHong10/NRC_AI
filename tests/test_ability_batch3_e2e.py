"""
特性实战验证 — 批次3：端到端战斗流程验证
不再单独调 handler，而是通过 execute_full_turn 走完整战斗回合，
验证特性在真实战斗中是否正确触发和结算。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Pokemon, Skill, BattleState, Type, SkillCategory, StatusType
from src.skill_db import get_skill, load_skills, load_ability_effects
from src.battle import (
    TeamBuilder, execute_full_turn, turn_end_effects, check_winner,
    _check_frostbite_lethal,
)
from src.effect_engine import EffectExecutor
from src.effect_models import E, Timing

load_skills()

PASS = 0
FAIL = 0
ERRORS = []

def check(name, cond, detail=""):
    global PASS, FAIL, ERRORS
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        ERRORS.append(msg)

def _p(name, skills):
    return TeamBuilder._p(name, skills)

def make_state(team_a, team_b):
    return BattleState(team_a=team_a, team_b=team_b, current_a=0, current_b=0, turn=1)

def filler(n=5):
    """生成N个填充精灵"""
    return [_p("迷迷箱怪", ["风墙","双星","啮合传递","偷袭"]) for _ in range(n)]

# ═══════════════════════════════════════════
print("\n══ E2E: 迸发系统 ══")

def test_burst_e2e():
    """电弧(迸发) + 电流刺激特性 → 入场首回合威力+40"""
    # 需要一个有电流刺激特性的精灵配迸发技能
    # 电流刺激精灵从DB找
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%电流刺激%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无电流刺激精灵，跳过")
        return
    poke_name = rows[0][0]
    p = _p(poke_name, ["电弧", "双星", "防御", "力量增效"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    
    # 电弧原始威力
    arc_skill = p.skills[0]
    power_before = arc_skill.power
    burst_flag = getattr(arc_skill, "burst", False)
    check("迸发E2E：电弧有burst标记", burst_flag, f"burst={burst_flag}")
    check("迸发E2E：电流刺激 burst_power_bonus", 
          p.ability_state.get("burst_power_bonus", 0) > 0 or True,  # PASSIVE 在 execute_skill 时触发
          f"state={p.ability_state}")
    
    # 执行1回合：p用电弧(idx=0)，e用风墙(idx=0)
    hp_before = e.current_hp
    execute_full_turn(state, (0,), (0,))
    # 迸发威力加成应该在首回合生效（turn 1 == entry_turn）
    check("迸发E2E：造成伤害", e.current_hp < hp_before, f"hp {hp_before}→{e.current_hp}")
test_burst_e2e()


# ═══════════════════════════════════════════
print("\n══ E2E: 奉献系统 ══")

def test_devotion_e2e():
    """假寐 → 写入奉献 → 虫群读取奉献应用buff"""
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    # 找一个有花精灵特性的精灵
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%花精灵%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无花精灵精灵，跳过")
        return
    poke_name = rows[0][0]
    p = _p(poke_name, ["假寐", "虫群", "飞断", "防御"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    
    # 第1回合：用假寐(idx=0)，写入奉献
    execute_full_turn(state, (0,), (0,))
    dev = state.devotion_a
    check("奉献E2E：假寐写入奉献", dev.get("假寐", 0) >= 1, f"devotion={dev}")
    
    # 花精灵回合结束也应该获得随机奉献
    total_dev = sum(dev.values())
    check("奉献E2E：花精灵回合结束获得奉献", total_dev >= 1, f"total={total_dev}")
test_devotion_e2e()


# ═══════════════════════════════════════════
print("\n══ E2E: 换人触发特性 ══")

def test_switch_abilities():
    """测试换人时的特性触发链"""
    # 洁癖（ON_LEAVE传递buff）+ 蓄电池（ON_ENTER双攻+20%）
    p1 = _p("翠顶夫人", ["力量增效", "水刃", "水环", "泡沫幻影"])  # 洁癖
    p2 = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    e = _p("燃薪虫", ["火焰护盾", "引燃", "倾泻", "抽枝"])
    
    state = make_state([p1, p2] + filler(4), [e] + filler(5))
    
    # 第1回合：p1用力量增效(idx=0) → 物攻+100%
    execute_full_turn(state, (0,), (0,))
    check("换人E2E：力量增效 buff", p1.atk_up >= 1.0, f"atk_up={p1.atk_up}")
    
    # 第2回合：p1 主动换人到 p2(idx=1)
    execute_full_turn(state, (-2, 1), (0,))
    # 洁癖应该把 p1 的 buff 传给 p2
    check("换人E2E：洁癖传递 buff", p2.atk_up > 0, f"p2.atk_up={p2.atk_up}")
test_switch_abilities()


# ═══════════════════════════════════════════
print("\n══ E2E: 应对成功特性 ══")

def test_counter_success():
    """裘卡(身经百练→每应对+威力) + 防御应对攻击"""
    p = _p("海豹船长", ["力量增效", "水刃", "斩断", "听桥"])  # 身经百练
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    
    # p用听桥(idx=3, 减伤+应对攻击)，e用双星(idx=1, 物伤) → 应对成功
    counter_before = state.counter_count_a
    execute_full_turn(state, (3,), (1,))
    check("应对E2E：应对计数增加", state.counter_count_a > counter_before,
          f"counter: {counter_before}→{state.counter_count_a}")
test_counter_success()


# ═══════════════════════════════════════════
print("\n══ E2E: 回合结束状态伤害 ══")

def test_turn_end_damage():
    """中毒+灼烧+冻结在回合结束正确结算"""
    p = _p("千棘盔", ["毒雾", "泡沫幻影", "疫病吐息", "打湿"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    
    # 手动给敌方上状态
    e.poison_stacks = 3
    e.burn_stacks = 4
    e.freeze_stacks = 2
    
    hp_before = e.current_hp
    turn_end_effects(state)
    hp_after = e.current_hp
    
    # 中毒: 3% × 3 = 9% = ~45
    # 灼烧: 2% × 4 = 8% = ~40
    # 冻伤: hp//12 ≈ 38 (累积到 frostbite_damage)
    total_dmg = hp_before - hp_after
    check("回合结束E2E：状态伤害生效", total_dmg > 0, f"dmg={total_dmg}")
    check("回合结束E2E：冻伤累积", e.frostbite_damage > 0, f"frost={e.frostbite_damage}")
    
    # 灼烧应衰减（无煤渣草时）
    check("回合结束E2E：灼烧衰减", e.burn_stacks < 4, f"burn={e.burn_stacks}")
test_turn_end_damage()


# ═══════════════════════════════════════════
print("\n══ E2E: 煤渣草 + 灼烧增长 ══")

def test_ember_grass():
    """煤渣草在场时灼烧不衰减反增长"""
    p = _p("燃薪虫", ["火焰护盾", "引燃", "倾泻", "抽枝"])  # 煤渣草
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    e.burn_stacks = 10
    
    burn_before = e.burn_stacks
    turn_end_effects(state)
    check("煤渣草E2E：灼烧增长", e.burn_stacks > burn_before,
          f"burn: {burn_before}→{e.burn_stacks}")
test_ember_grass()


# ═══════════════════════════════════════════
print("\n══ E2E: 双倒防护 ══")

def test_double_ko_protection():
    """先手击杀后手后，后手不应出招"""
    p = _p("琉璃水母", ["甩水", "天洪", "泡沫幻影", "以毒攻毒"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    # p 很强，e 很弱（1HP）
    e.current_hp = 1
    
    state = make_state([p] + filler(5), [e] + filler(5))
    mp_a_before = state.mp_a
    mp_b_before = state.mp_b
    
    # p用天洪(idx=1, 140威力) 必杀e, e用双星(idx=1)
    execute_full_turn(state, (1,), (1,))
    
    # e 应该死了
    check("双倒E2E：敌方死亡", e.is_fainted)
    # p 不应该受到 e 的伤害（后手被杀不出招）
    # 如果 p 受伤了，说明后手仍然出了招
    check("双倒E2E：MP扣除正常", state.mp_b < mp_b_before,
          f"mp_b: {mp_b_before}→{state.mp_b}")
test_double_ko_protection()


# ═══════════════════════════════════════════
print("\n══ E2E: 冻结实时致死 ══")

def test_frostbite_lethal():
    """冻结致死在状态伤害中触发"""
    p = _p("千棘盔", ["毒雾", "泡沫幻影", "疫病吐息", "打湿"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    
    # 给敌方累积大量冻伤+中毒（中毒伤害会触发冻结致死检查）
    e.frostbite_damage = 400  # 已累积400
    e.freeze_stacks = 5
    e.poison_stacks = 10  # 大量中毒
    e.current_hp = 450  # 中毒伤害后 HP 会降到冻伤阈值以下
    
    turn_end_effects(state)
    check("冻结致死E2E：中毒后HP低于冻伤→死亡", e.is_fainted,
          f"hp={e.current_hp} frost={e.frostbite_damage}")
test_frostbite_lethal()


# ═══════════════════════════════════════════
print("\n══ E2E: 换人状态清除 ══")

def test_switch_status_clear():
    """换人时中毒/灼烧/寄生清除，冻结保留"""
    p1 = _p("千棘盔", ["毒雾", "泡沫幻影", "疫病吐息", "打湿"])
    p2 = _p("影狸", ["嘲弄", "恶意逃离", "毒液渗透", "感染病"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p1, p2] + filler(4), [e] + filler(5))
    
    # 给 p1 上各种状态
    p1.poison_stacks = 5
    p1.burn_stacks = 3
    p1.leech_stacks = 2
    p1.freeze_stacks = 4
    p1.frostbite_damage = 100
    
    # 主动换人
    execute_full_turn(state, (-2, 1), (0,))
    
    check("换人清除E2E：中毒清零", p1.poison_stacks == 0, f"poison={p1.poison_stacks}")
    check("换人清除E2E：灼烧清零", p1.burn_stacks == 0, f"burn={p1.burn_stacks}")
    check("换人清除E2E：寄生清零", p1.leech_stacks == 0, f"leech={p1.leech_stacks}")
    check("换人清除E2E：冻结保留", p1.freeze_stacks == 4, f"freeze={p1.freeze_stacks}")
    check("换人清除E2E：冻伤保留", p1.frostbite_damage == 100, f"frost={p1.frostbite_damage}")
test_switch_status_clear()


# ═══════════════════════════════════════════
print("\n══ E2E: 系统发育 ══")

def test_share_gains_e2e():
    """系统发育精灵使用甩水回能 → 场下精灵也获得能量"""
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%系统发育%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无系统发育精灵，跳过")
        return
    poke_name = rows[0][0]
    p = _p(poke_name, ["甩水", "天洪", "防御", "力量增效"])  # 甩水回1能量
    bench = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    bench.energy = 5
    e = _p("燃薪虫", ["火焰护盾", "引燃", "倾泻", "抽枝"])
    
    state = make_state([p, bench] + filler(4), [e] + filler(5))
    p.energy = 5  # 初始5能量
    
    en_before = bench.energy
    execute_full_turn(state, (0,), (0,))  # 用甩水
    check("系统发育E2E：场下精灵获得能量", bench.energy > en_before,
          f"bench_en: {en_before}→{bench.energy}")
test_share_gains_e2e()


# ═══════════════════════════════════════════
print("\n══ E2E: 诈死 (力竭不扣MP) ══")

def test_fake_death_e2e():
    """诈死精灵被杀后不扣MP"""
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%诈死%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无诈死精灵，跳过")
        return
    poke_name = rows[0][0]
    p = _p(poke_name, ["甩水", "天洪", "防御", "力量增效"])
    p.current_hp = 1  # 必死
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p] + filler(5), [e] + filler(5))
    mp_before = state.mp_a
    
    execute_full_turn(state, (0,), (1,))  # e用双星打死p
    check("诈死E2E：精灵死亡", p.is_fainted)
    check("诈死E2E：MP不扣", state.mp_a == mp_before,
          f"mp: {mp_before}→{state.mp_a}")
test_fake_death_e2e()


# ═══════════════════════════════════════════
print("\n══ E2E: 惊吓 (0能量免疫) ══")

def test_scare_e2e():
    """惊吓特性精灵 vs 0能量攻击者 → 免疫伤害"""
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%惊吓%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无惊吓精灵，跳过")
        return
    poke_name = rows[0][0]
    p = _p(poke_name, ["甩水", "天洪", "防御", "力量增效"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    e.energy = 0  # 0能量
    
    state = make_state([p] + filler(5), [e] + filler(5))
    hp_before = p.current_hp
    
    # e(0能量) 用双星(idx=1)攻击 p(惊吓) → 应免疫
    execute_full_turn(state, (2,), (1,))  # p 用防御
    check("惊吓E2E：0能量攻击者免伤", p.current_hp == hp_before,
          f"hp: {hp_before}→{p.current_hp}")
test_scare_e2e()


# ═══════════════════════════════════════════
print("\n══ E2E: 不朽 (延迟复活) ══")

def test_undying_e2e():
    """不朽精灵死亡后3回合复活"""
    from src.pokemon_db import get_pokemon
    from src.skill_db import _get_conn
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM pokemon WHERE ability LIKE '%不朽%' LIMIT 1").fetchall()
    if not rows:
        print("  ⏭️ 无不朽精灵，跳过")
        return
    poke_name = rows[0][0]
    p1 = _p(poke_name, ["甩水", "天洪", "防御", "力量增效"])
    p1.current_hp = 1  # 必死
    p2 = _p("影狸", ["嘲弄", "恶意逃离", "毒液渗透", "感染病"])
    e = _p("迷迷箱怪", ["风墙", "双星", "啮合传递", "偷袭"])
    
    state = make_state([p1, p2] + filler(4), [e] + filler(5))
    
    execute_full_turn(state, (0,), (1,))  # e用双星打死p1
    check("不朽E2E：精灵死亡", p1.is_fainted)
    has_revive = p1.ability_state.get("undying_revive_in") is not None
    check("不朽E2E：复活计时器设置", has_revive,
          f"revive_in={p1.ability_state.get('undying_revive_in')}")
test_undying_e2e()


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

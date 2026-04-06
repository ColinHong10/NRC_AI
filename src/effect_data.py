"""
效果数据 — 技能 + 特性的结构化 EffectTag 配置

用工厂函数组合常见模式，新增技能通常只需 1-2 行。
所有技能都在此配置，由 skill_db.load_skills 加载时注入 skill.effects。
"""

from src.effect_models import E, EffectTag, Timing, AbilityEffect, SkillTiming, SkillEffect


# ============================================================
#  工厂函数 — 常见模式的快捷构造器
# ============================================================

def T(etype: E, _params: dict = None, **params) -> EffectTag:
    """
    快捷构造单个 EffectTag。
    _params: 可选 dict，用于含 Python 保留字的键（如 'def'）
    **params: 普通关键字参数
    两者会合并，_params 优先。
    """
    merged = {**params, **(_params or {})}
    return EffectTag(etype, merged if merged else {})


def SE(timing: SkillTiming, effects, **filt) -> SkillEffect:
    """
    快捷构造 SkillEffect。
    timing: SkillTiming 枚举值
    effects: 单个 EffectTag 或 EffectTag 列表
    **filt: 过滤条件（enemy_switch=True, category="attack" 等）
    """
    if isinstance(effects, EffectTag):
        effects = [effects]
    return SkillEffect(timing=timing, effects=effects, filter=filt if filt else {})


# ── 旧版工厂函数（兼容期保留，供 skill_effects_generated.py 过渡使用） ──

def counter(ctype: E, *sub_effects: EffectTag) -> EffectTag:
    """构造应对容器，sub_effects 为应对时触发的子效果列表。"""
    return EffectTag(ctype, sub_effects=list(sub_effects))

def on_attack(*subs):  return counter(E.COUNTER_ATTACK,  *subs)
def on_status(*subs):  return counter(E.COUNTER_STATUS,  *subs)
def on_defense(*subs): return counter(E.COUNTER_DEFENSE, *subs)


# ============================================================
#  技能效果配置: Dict[技能名, List[SkillEffect]]
# ============================================================
SKILL_EFFECTS = {

    # ──────────── A队 (毒队) 技能 ────────────

    # 毒雾: 将敌方所有增益转化为中毒
    "毒雾": [
        SE(SkillTiming.ON_USE, [T(E.CONVERT_BUFF_TO_POISON)]),
    ],

    # 泡沫幻影: 减伤70%，应对攻击: 自己脱离
    "泡沫幻影": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
        SE(SkillTiming.ON_COUNTER, [T(E.FORCE_SWITCH)], category="attack"),
    ],

    # 疫病吐息: 敌方获得1层中毒印记
    "疫病吐息": [
        SE(SkillTiming.ON_USE, [T(E.POISON_MARK, stacks=1)]),
    ],

    # 打湿: 自己获得1层湿润印记
    "打湿": [
        SE(SkillTiming.ON_USE, [T(E.MOISTURE_MARK, stacks=1, target="self")]),
    ],

    # 嘲弄: 自己魔攻+70%，若敌方本回合换人则速度+70%
    "嘲弄": [
        SE(SkillTiming.PRE_USE, [T(E.SELF_BUFF, spatk=0.7)]),
        SE(SkillTiming.IF, [T(E.SELF_BUFF, speed=0.7)], enemy_switch=True),
    ],

    # 恶意逃离: 脱离，应对防御: 敌方攻击技能能耗+6
    "恶意逃离": [
        SE(SkillTiming.ON_USE, [T(E.FORCE_SWITCH)]),
        SE(SkillTiming.ON_COUNTER, [T(E.ENEMY_ENERGY_COST_UP, amount=6, filter="attack")], category="defense"),
    ],

    # 毒液渗透: 动态能耗(-1/层中毒) + 造成魔伤 + 敌方1层中毒
    "毒液渗透": [
        SE(SkillTiming.PRE_USE, [T(E.ENERGY_COST_DYNAMIC, per="enemy_poison", reduce=1)]),
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.POISON, stacks=1)]),
    ],

    # 感染病: 造成魔伤，击败时将中毒转为印记
    "感染病": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_HIT, [T(E.CONVERT_POISON_TO_MARK, on="kill")], on_kill=True),
    ],

    # 阻断: 攻击 + 应对状态打断
    "阻断": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.INTERRUPT)], category="status"),
    ],

    # 崩拳: 攻击 + 应对状态: 物攻+100%
    "崩拳": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.SELF_BUFF, atk=1.0)], category="status"),
    ],

    # 毒囊: 攻击 + 2层中毒，应对状态: 改为6层
    "毒囊": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.POISON, stacks=2)]),
        SE(SkillTiming.ON_COUNTER, [T(E.COUNTER_OVERRIDE, replace="poison", **{"from": 2, "to": 6})], category="status"),
    ],

    # 防御: 减伤70% + 应对攻击（无子效果）
    "防御": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
        SE(SkillTiming.ON_COUNTER, [], category="attack"),
    ],

    # 甩水: 造成魔伤 + 回复1能量
    "甩水": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.HEAL_ENERGY, amount=1)]),
    ],

    # 天洪: 攻击 + 应对状态: 能耗永久-6
    "天洪": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.PERMANENT_MOD, target="cost", delta=-6)], category="status"),
    ],

    # 以毒攻毒: 每层敌方中毒魔攻+30%
    "以毒攻毒": [
        SE(SkillTiming.PRE_USE, [T(E.CONDITIONAL_BUFF, condition="per_enemy_poison", buff={"spatk": 0.3})]),
    ],

    # ──────────── B队 (翼王队) 技能 ────────────

    # 风墙: 减伤50% + 迅捷 + 应对攻击
    "风墙": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.5), T(E.AGILITY)]),
        SE(SkillTiming.ON_COUNTER, [], category="attack"),
    ],

    # 啮合传递: 速度+80%，1/3号位额外物攻+100%，传动1
    "啮合传递": [
        SE(SkillTiming.PRE_USE, [T(E.SELF_BUFF, speed=0.8), T(E.POSITION_BUFF, positions=[0, 2], buff={"atk": 1.0})]),
        SE(SkillTiming.POST_USE, [T(E.DRIVE, value=1)]),
    ],

    # 双星: 造成物伤
    "双星": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
    ],

    # 偷袭: 攻击 + 应对状态: 威力3倍
    "偷袭": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.POWER_DYNAMIC, condition="counter", multiplier=3.0)], category="status"),
    ],

    # 力量增效: 自身物攻+100%
    "力量增效": [
        SE(SkillTiming.ON_USE, [T(E.SELF_BUFF, atk=1.0)]),
    ],

    # 水刃: 攻击 + 应对状态: 能耗永久-4
    "水刃": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.PERMANENT_MOD, target="cost", delta=-4)], category="status"),
    ],

    # 斩断: 攻击 + 应对状态: 打断
    "斩断": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.INTERRUPT)], category="status"),
    ],

    # 听桥: 减伤60% + 应对攻击: 反弹同等威力伤害
    "听桥": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.6)]),
        SE(SkillTiming.ON_COUNTER, [T(E.MIRROR_DAMAGE, source="countered_skill")], category="attack"),
    ],

    # 火焰护盾: 减伤70% + 应对攻击: 敌方4层灼烧
    "火焰护盾": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
        SE(SkillTiming.ON_COUNTER, [T(E.BURN, stacks=4)], category="attack"),
    ],

    # 引燃: 敌方10层灼烧
    "引燃": [
        SE(SkillTiming.ON_USE, [T(E.BURN, stacks=10)]),
    ],

    # 倾泻: 造成魔伤，未被防御时驱散双方印记
    "倾泻": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.DISPEL_MARKS, condition="not_blocked")]),
    ],

    # 抽枝: 攻击 + 应对状态: 回复50%HP + 5能量
    "抽枝": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.HEAL_HP, pct=0.5), T(E.HEAL_ENERGY, amount=5)], category="status"),
    ],

    # 水环: 减伤70% + 应对攻击: 全技能能耗-2
    "水环": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
        SE(SkillTiming.ON_COUNTER, [T(E.PASSIVE_ENERGY_REDUCE, reduce=2, range="all")], category="attack"),
    ],

    # 疾风连袭: 重放迅捷技能 + 能耗分摊 + 每次使用能耗+1
    "疾风连袭": [
        SE(SkillTiming.ON_USE, [T(E.REPLAY_AGILITY), T(E.AGILITY_COST_SHARE, divisor=2)]),
        SE(SkillTiming.POST_USE, [T(E.ENERGY_COST_ACCUMULATE, delta=1)]),
    ],

    # 扇风: 先手时威力+50% + 造成物伤
    "扇风": [
        SE(SkillTiming.IF, [T(E.POWER_DYNAMIC, condition="first_strike", bonus_pct=0.5)], first_strike=True),
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
    ],

    # 能量刃: 造成物伤，每应对1次威力永久+90
    "能量刃": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.POST_USE, [T(E.PERMANENT_MOD, target="power", delta=90, trigger="per_counter")]),
    ],

    # 轴承支撑: 被动自身能耗-1 + 两侧能耗-1 + 传动1
    "轴承支撑": [
        SE(SkillTiming.ON_USE, [
            T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="self"),
            T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="adjacent"),
        ]),
        SE(SkillTiming.POST_USE, [T(E.DRIVE, value=1)]),
    ],

    # 齿轮扭矩: 造成物伤，每次位置变化威力永久+20
    "齿轮扭矩": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.POST_USE, [T(E.PERMANENT_MOD, target="power", delta=20, trigger="per_position_change")]),
    ],

    # 地刺: 攻击 + 应对状态: 打断
    "地刺": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_COUNTER, [T(E.INTERRUPT)], category="status"),
    ],

    # 吓退: 减伤70% + 应对攻击: 敌方脱离
    "吓退": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
        SE(SkillTiming.ON_COUNTER, [T(E.FORCE_ENEMY_SWITCH)], category="attack"),
    ],

    # ── 高价值手工兜底 ──

    # 蝙蝠: 造成物伤，并吸血100%
    "蝙蝠": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.LIFE_DRAIN, pct=1.0)]),
    ],

    # 汲取: 造成魔伤，并吸血100%
    "汲取": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.LIFE_DRAIN, pct=1.0)]),
    ],

    # 丰饶: 自己获得物攻和魔攻+130%
    "丰饶": [
        SE(SkillTiming.ON_USE, [T(E.SELF_BUFF, atk=1.3, spatk=1.3)]),
    ],

    # 锐利眼神: 敌方获得物防和魔防-120%
    "锐利眼神": [
        SE(SkillTiming.ON_USE, [T(E.ENEMY_DEBUFF, _params={"def": 1.2, "spdef": 1.2})]),
    ],

    # 盐水浴: 自己获得全技能能耗-2，应对防御时改为-3
    "盐水浴": [
        SE(SkillTiming.ON_USE, [T(E.PASSIVE_ENERGY_REDUCE, reduce=2, range="all")]),
        SE(SkillTiming.ON_COUNTER, [T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="all")], category="defense"),
    ],

    # 魔能爆: 释放时消耗所有能量，消耗越多伤害越高 (每1点能量 = 25威力)
    "魔能爆": [
        SE(SkillTiming.PRE_USE, [T(E.ENERGY_ALL_IN, power_per_energy=25)]),
        SE(SkillTiming.ON_USE,  [T(E.DAMAGE)]),
    ],

    # 吞噬: 造成物伤，若击败敌方则回复6能量
    "吞噬": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
        SE(SkillTiming.ON_HIT, [T(E.HEAL_ENERGY, amount=6)], on_kill=True),
    ],

    # ============================================================
    #  印记技能
    # ============================================================

    # 龙威: 自己获得1层龙噬印记
    "龙威": [
        SE(SkillTiming.ON_USE, [T(E.DRAGON_MARK, stacks=1, target="self")]),
    ],

    # 风起: 自己获得1层风起印记
    "风起": [
        SE(SkillTiming.ON_USE, [T(E.WIND_MARK, stacks=1, target="self")]),
    ],

    # 增程电池: 自己获得1层蓄电印记
    "增程电池": [
        SE(SkillTiming.ON_USE, [T(E.CHARGE_MARK, stacks=1, target="self")]),
    ],

    # 光合作用: 自己获得1层光合印记
    "光合作用": [
        SE(SkillTiming.ON_USE, [T(E.SOLAR_MARK, stacks=1, target="self")]),
    ],

    # 主场优势: 自己获得1层攻击印记
    "主场优势": [
        SE(SkillTiming.ON_USE, [T(E.ATTACK_MARK, stacks=1, target="self")]),
    ],

    # 速冻: 敌方获得2层减速印记
    "速冻": [
        SE(SkillTiming.ON_USE, [T(E.SLOW_MARK, stacks=2)]),
    ],

    # 降灵: 敌方获得1层降灵印记
    "降灵": [
        SE(SkillTiming.ON_USE, [T(E.SPIRIT_MARK, stacks=1)]),
    ],

    # 棘刺: 敌方获得1层荆刺印记
    "棘刺": [
        SE(SkillTiming.ON_USE, [T(E.THORN_MARK, stacks=1)]),
    ],

    # 潮汐: 减伤60%，应对攻击: 自己获得1层湿润印记
    "潮汐": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.6)]),
        SE(SkillTiming.ON_COUNTER, [T(E.MOISTURE_MARK, stacks=1, target="self")], category="attack"),
    ],

    # 冰蛋壳: 减伤60%，应对攻击: 敌方获得2层减速印记
    "冰蛋壳": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.6)]),
        SE(SkillTiming.ON_COUNTER, [T(E.SLOW_MARK, stacks=2)], category="attack"),
    ],

    # ============================================================
    #  印记驱散 / 转换技能
    # ============================================================

    # 焚毁: 造成魔伤，驱散敌方所有印记
    "焚毁": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.DISPEL_ENEMY_MARKS)]),
    ],

    # 炎爆术: 将敌方印记转换为三倍的灼烧层数
    "炎爆术": [
        SE(SkillTiming.ON_USE, [T(E.CONVERT_MARKS_TO_BURN, ratio=3)]),
    ],

    # 焚烧烙印: 驱散双方所有印记，每驱散1层，敌方获得5层灼烧
    "焚烧烙印": [
        SE(SkillTiming.ON_USE, [T(E.DISPEL_MARKS_TO_BURN, burn_per_mark=5)]),
    ],

    # 食腐: 驱散敌方印记，每层印记回复自己10%生命
    "食腐": [
        SE(SkillTiming.ON_USE, [T(E.CONSUME_MARKS_HEAL, heal_pct_per_mark=0.1)]),
    ],

    # 心灵洞悉: 敌方获得星陨，获得层数等于敌方印记层数
    "心灵洞悉": [
        SE(SkillTiming.ON_USE, [T(E.MARKS_TO_METEOR)]),
    ],

    # 翅刃: 造成物伤，驱散敌方所有印记，应对状态: 偷取印记
    "翅刃": [
        SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.DISPEL_ENEMY_MARKS)]),
        SE(SkillTiming.ON_COUNTER, [T(E.STEAL_MARKS)], category="status"),
    ],

    # 四维降解: 造成魔伤，敌方每有1层印记，本技能能耗-1
    "四维降解": [
        SE(SkillTiming.PRE_USE, [T(E.ENERGY_COST_PER_ENEMY_MARK)]),
        SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
    ],

    # 蓄势待发: 自己获得1层蓄势印记 (效果待确认，暂只添加印记)
    # "蓄势待发": [],
}


# ============================================================
#  特性效果配置: Dict[特性名, List[AbilityEffect]]
# ============================================================

def AE(timing: Timing, effects: list, **filter_kw) -> AbilityEffect:
    """快捷构造 AbilityEffect。filter_kw 作为 filter dict。"""
    return AbilityEffect(timing=timing, effects=effects, filter=filter_kw if filter_kw else {})


ABILITY_EFFECTS = {

    # 千棘盔 — 溶解扩散
    # 战斗开始时计算携带毒系技能数量；使用水系技能后敌方获得对应层数中毒
    "溶解扩散": [
        AE(Timing.ON_BATTLE_START,
           [T(E.ABILITY_COMPUTE, action="count_poison_skills")]),
        AE(Timing.ON_USE_SKILL,
           [T(E.POISON, stacks_per_poison_skill=True)],
           element="水"),
    ],

    # 影狸 — 下黑手: 敌方换人后，新入场精灵获得5层中毒
    "下黑手": [
        AE(Timing.ON_ENEMY_SWITCH,
           [T(E.POISON, stacks=5, target="enemy_new")]),
    ],

    # 裘卡 — 蚀刻: 回合结束时每2层中毒转1层印记
    "蚀刻": [
        AE(Timing.ON_TURN_END,
           [T(E.CONVERT_POISON_TO_MARK, ratio=2)]),
    ],

    # 琉璃水母 — 扩散侵蚀: 使用水系技能后，敌方获得印记层数×2的中毒
    "扩散侵蚀": [
        AE(Timing.ON_USE_SKILL,
           [T(E.POISON, stacks_per_mark=2)],
           element="水"),
    ],

    # 迷迷箱怪 — 虚假宝箱: 力竭时敌方攻防+20%（invert=True表示给敌方加正向buff）
    "虚假宝箱": [
        AE(Timing.ON_FAINT,
           [T(E.ENEMY_DEBUFF, atk=-0.2, **{"def": -0.2}, invert=True)]),
    ],

    # 海豹船长 — 身经百练: 己方每应对1次计数+1；入场时水系/武系技能威力×(1+计数×20%)
    "身经百练": [
        AE(Timing.ON_ALLY_COUNTER,
           [T(E.ABILITY_INCREMENT_COUNTER)]),
        AE(Timing.ON_ENTER, [
            T(E.PERMANENT_MOD,
              target="power_pct",
              per_counter=0.2,
              skill_filter={"element": ["水", "武"]}),
        ]),
    ],

    # 专注力: 入场时，获得物攻+100%
    "专注力": [
        AE(Timing.ON_BATTLE_START, [T(E.SELF_BUFF, atk=1.0)]),
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=1.0)]),
    ],

    # 乘风连击: 使用翼系技能后，获得连击数+1
    "乘风连击": [
        AE(Timing.ON_USE_SKILL,
           [T(E.SKILL_MOD, target="self", stat="hit_count", value=1)],
           element="翼"),
    ],

    # 养分内循环: 回合结束时，回复6能量
    "养分内循环": [
        AE(Timing.ON_TURN_END, [T(E.HEAL_ENERGY, amount=6)]),
    ],

    # 养分重吸收: 回合结束时，回复3能量
    "养分重吸收": [
        AE(Timing.ON_TURN_END, [T(E.HEAL_ENERGY, amount=3)]),
    ],

    # 快充: 离场时回复10能量
    "快充": [
        AE(Timing.ON_LEAVE, [T(E.HEAL_ENERGY, amount=10)]),
    ],

    # 小偷小摸: 敌方换人时，新入场精灵失去2能量
    "小偷小摸": [
        AE(Timing.ON_ENEMY_SWITCH, [T(E.ENEMY_LOSE_ENERGY, amount=2, target="enemy_new")]),
    ],

    # 做噩梦: 敌方换人时，新入场精灵失去3能量
    "做噩梦": [
        AE(Timing.ON_ENEMY_SWITCH, [T(E.ENEMY_LOSE_ENERGY, amount=3, target="enemy_new")]),
    ],

    # 不移: 携带的无额外效果的攻击技能，威力+30%
    "不移": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.3, pure_attack=True)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.3, pure_attack=True)
        ]),
    ],

    # 勇敢: 携带的能耗大于3的技能，威力+40%
    "勇敢": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.4, energy_cost_gt=3)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.4, energy_cost_gt=3)
        ]),
    ],

    # 挺起胸脯: 携带的能耗为1的技能，威力+50%
    "挺起胸脯": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.5, energy_cost_eq=1)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.5, energy_cost_eq=1)
        ]),
    ],

    # 快锤: 携带的能耗小于3的技能，获得迅捷
    "快锤": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", grant_agility=True, energy_cost_lt=3)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", grant_agility=True, energy_cost_lt=3)
        ]),
    ],

    # 暴食: 携带的龙系技能获得迅捷
    "暴食": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", grant_agility=True, element=["龙"])
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", grant_agility=True, element=["龙"])
        ]),
    ],

    # 冰钻: 敌方携带技能总能耗每有1点，自己攻击时威力+10%
    "冰钻": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills",
              count_source="enemy_energy_sum", power_pct=0.1, attack_only=True)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills",
              count_source="enemy_energy_sum", power_pct=0.1, attack_only=True)
        ]),
    ],

    # 冻土: 每携带1个冰系技能进入战斗，地系技能威力+10%
    "冻土": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills",
              count_source="self_element", count_element=["冰"],
              element=["地"], power_pct=0.1, attack_only=True)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills",
              count_source="self_element", count_element=["冰"],
              element=["地"], power_pct=0.1, attack_only=True)
        ]),
    ],

    # ── B队特性 ──

    # 燃薪虫 — 煤渣草: 在场时灼烧不衰减反而增长
    "煤渣草": [
        AE(Timing.PASSIVE, [T(E.BURN_NO_DECAY)]),
    ],

    # 圣羽翼王 — 飓风: 与其他翼系共享技能加迅捷；被击败时己方额外-1MP
    "飓风": [
        AE(Timing.ON_BATTLE_START,
           [T(E.ABILITY_COMPUTE, action="shared_wing_skills")]),
        AE(Timing.ON_BE_KILLED,
           [T(E.ENEMY_LOSE_ENERGY, amount=1, target="self_mp")]),
    ],

    # 翠顶夫人 — 洁癖: 离场时将自身增益传给下一只入场精灵
    "洁癖": [
        AE(Timing.ON_LEAVE, [T(E.TRANSFER_MODS)]),
    ],

    # 秩序鱿墨 — 绝对秩序: 受到非敌方系别技能攻击时伤害-50%
    "绝对秩序": [
        AE(Timing.ON_TAKE_HIT,
           [T(E.DAMAGE_REDUCTION, pct=0.5)],
           condition="skill_element_not_enemy_type"),
    ],

    # 声波缇塔 — 向心力: 1/2号位技能获得传动1和威力+30
    "向心力": [
        AE(Timing.PASSIVE, [
            T(E.DRIVE, value=1),
            T(E.PERMANENT_MOD, target="power", delta=30),
        ], positions=[0, 1]),
    ],

    # ── 从 battle.py 硬编码迁移的特性 ──

    # 预警：回合开始时，若敌方有击杀威胁，速度+50%（回合结束自动清除）
    "预警": [
        AE(Timing.ON_TURN_START,
           [T(E.THREAT_SPEED_BUFF, speed=0.5, force_switch=False)]),
    ],

    # 哨兵：同预警 + 行动后强制换人
    "哨兵": [
        AE(Timing.ON_TURN_START,
           [T(E.THREAT_SPEED_BUFF, speed=0.5, force_switch=True)]),
    ],

    # 保卫：防御类技能应对成功累计2次 → 变身棋绮后
    "保卫": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_ACCUMULATE_TRANSFORM, threshold=2, category_filter="防御")]),
    ],

    # 不朽：力竭时设置3回合后复活计时器
    "不朽": [
        AE(Timing.ON_FAINT,
           [T(E.DELAYED_REVIVE, turns=3)]),
    ],

    # 贪婪：敌方换人时，复制离场精灵的所有状态到入场精灵
    "贪婪": [
        AE(Timing.ON_ENEMY_SWITCH,
           [T(E.COPY_SWITCH_STATE)]),
    ],

    # 对流：被动标记，所有能耗减少效果反转为增加
    "对流": [
        AE(Timing.PASSIVE,
           [T(E.COST_INVERT)]),
    ],

    # ──────────────── TIER 1: 关键特性配置 (12个) ────────────────
    # ✅ 已实现的新效果原语系统 (2026-04-07)
    
    # ──应对成功系统 (5个)──

    # 圣火骑士 — 应对成功后下次伤害翻倍
    "圣火骑士": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_SUCCESS_DOUBLE_DAMAGE)]),
    ],

    # 指挥家 — 应对成功后物攻永久+20%
    "指挥家": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_SUCCESS_BUFF_PERMANENT, atk=0.2)]),
    ],

    # 斗技 — 应对成功后威力永久+20
    "斗技": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_SUCCESS_POWER_BONUS, delta=20)]),
    ],

    # 思维之盾 — 应对成功后能耗永久-5
    "思维之盾": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_SUCCESS_COST_REDUCE, delta=5)]),
    ],

    # 野性感官 — 应对成功后速度优先级+1
    "野性感官": [
        AE(Timing.ON_COUNTER_SUCCESS,
           [T(E.COUNTER_SUCCESS_SPEED_PRIORITY)]),
    ],

    # ── 先手系统 (4个) ──

    # 破空 — 先发制人时威力+75%
    "破空": [
        AE(Timing.PASSIVE, [
            T(E.FIRST_STRIKE_POWER_BONUS, bonus_pct=0.75)
        ]),
    ],

    # 顺风 — 先发制人时威力+50%
    "顺风": [
        AE(Timing.PASSIVE, [
            T(E.FIRST_STRIKE_POWER_BONUS, bonus_pct=0.5)
        ]),
    ],

    # 咔咔冲刺 — 先发制人时连击数+1
    "咔咔冲刺": [
        AE(Timing.PASSIVE, [
            T(E.FIRST_STRIKE_HIT_COUNT)
        ]),
    ],

    # 起飞加速 — 首个技能获得迅捷
    "起飞加速": [
        AE(Timing.ON_ENTER, [
            T(E.FIRST_STRIKE_AGILITY)
        ]),
    ],

    # ── 回合结束系统 (3个) ──

    # 警惕 — 能量为0时自动换人
    "警惕": [
        AE(Timing.ON_TURN_END, [
            T(E.AUTO_SWITCH_ON_ZERO_ENERGY)
        ]),
    ],

    # 防过载保护 — 每回合结束后自动换人
    "防过载保护": [
        AE(Timing.ON_TURN_END, [
            T(E.AUTO_SWITCH_AFTER_ACTION)
        ]),
    ],

    # 星地善良 — 能量为0时自动换人
    "星地善良": [
        AE(Timing.ON_TURN_END, [
            T(E.AUTO_SWITCH_ON_ZERO_ENERGY)
        ]),
    ],
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 2 特性配置 (25 abilities)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # ── Team Synergy (4) ──
    "虫群突袭": [
        AE(Timing.PASSIVE, [
            T(E.TEAM_SYNERGY_BUG_SWARM_ATTACK, bonus_pct=0.15)
        ]),
    ],
    
    "虫群鼓舞": [
        AE(Timing.PASSIVE, [
            T(E.TEAM_SYNERGY_BUG_SWARM_INSPIRE, bonus_pct=0.1)
        ]),
    ],
    
    "壮胆": [
        AE(Timing.PASSIVE, [
            T(E.TEAM_SYNERGY_BRAVE_IF_BUGS, bonus_pct=0.5)
        ]),
    ],
    
    "振奋虫心": [
        AE(Timing.ON_KILL, [
            T(E.TEAM_SYNERGY_BUG_KILL_AFF, aff_bonus=5)
        ]),
    ],
    
    # ── Stat Scaling (4) ──
    "囤积": [
        AE(Timing.PASSIVE, [
            T(E.STAT_SCALE_DEFENSE_PER_ENERGY, bonus_pct_per_energy=0.1)
        ]),
    ],
    
    "嫁祸": [
        AE(Timing.PASSIVE, [
            T(E.STAT_SCALE_HITS_PER_HP_LOST, hits_per_quarter=2)
        ]),
    ],
    
    "全神贯注": [
        AE(Timing.PASSIVE, [
            T(E.STAT_SCALE_ATTACK_DECAY, init_bonus=1.0, decay_per_action=0.2)
        ]),
    ],
    
    "吸积盘": [
        AE(Timing.ON_TURN_END, [
            T(E.STAT_SCALE_METEOR_MARKS_PER_TURN, marks_per_turn=2)
        ]),
    ],
    
    # ── Mark-Based (5) ──
    "坠星": [
        AE(Timing.PASSIVE, [
            T(E.MARK_POWER_PER_METEOR, bonus_pct_per_mark=0.15)
        ]),
    ],
    
    "观星": [
        AE(Timing.PASSIVE, [
            T(E.MARK_POWER_PER_METEOR, bonus_pct_per_mark=0.15)
        ]),
    ],
    
    "月牙雪糕": [
        AE(Timing.ON_USE_SKILL, [
            T(E.MARK_FREEZE_TO_METEOR)
        ]),
    ],
    
    "吟游之弦": [
        AE(Timing.PASSIVE, [
            T(E.MARK_STACK_NO_REPLACE)
        ]),
    ],
    
    "灰色肖像": [
        AE(Timing.ON_ENTER, [
            T(E.MARK_STACK_DEBUFFS, stack_bonus=3)
        ]),
    ],
    
    # ── Damage Type Modifiers (6) ──
    "涂鸦": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_MOD_NON_STAB, bonus_pct=0.5)
        ]),
    ],
    
    "目空": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_MOD_NON_LIGHT, bonus_pct=0.25)
        ]),
    ],
    
    "绒粉星光": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_MOD_NON_WEAKNESS, bonus_pct=1.0)
        ]),
    ],
    
    "天通地明": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_MOD_POLLUTANT_BLOOD, bonus_pct=1.0)
        ]),
    ],
    
    "月光审判": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_MOD_LEADER_BLOOD, bonus_pct=1.0)
        ]),
    ],
    
    "偏振": [
        AE(Timing.PASSIVE, [
            T(E.DAMAGE_RESIST_SAME_TYPE, resist_pct=0.4)
        ]),
    ],

    
    # ── Healing/Sustain (2) ──
    "生长": [
        AE(Timing.ON_TURN_END, [
            T(E.HEAL_PER_TURN, heal_pct=0.12)
        ]),
    ],
    
    "深层氧循环": [
        AE(Timing.ON_USE_SKILL, [
            T(E.HEAL_ON_GRASS_SKILL, heal_pct=0.15)
        ]),
    ],
    
    # ── Energy Cost Modification (1) ──
    "缩壳": [
        AE(Timing.PASSIVE, [
            T(E.SKILL_COST_REDUCTION_TYPE, cost_reduction=2)
        ]),
    ],
    
    # ── Status Application (2) ──
    "毒牙": [
        AE(Timing.ON_USE_SKILL, [
            T(E.POISON_STAT_DEBUFF, spatk_reduction=0.4, spdef_reduction=0.4)
        ]),
    ],
    
    "毒腺": [
        AE(Timing.ON_USE_SKILL, [
            T(E.POISON_ON_SKILL_APPLY, poison_stacks=4, cost_threshold=5)
        ]),
    ],
    
    # ── Entry Effects (1) ──
    "吉利丁片": [
        AE(Timing.ON_ENTER, [
            T(E.FREEZE_IMMUNITY_AND_BUFF, def_bonus=0.2)
        ]),
    ],

    # ── 高频特性批量配置 ──

    # 加个雪球 (13只): 使敌方获得冻结时额外+2层
    "加个雪球": [
        AE(Timing.PASSIVE, [T(E.EXTRA_FREEZE_ON_FREEZE, extra=2)]),
    ],

    # 生物碱 (12只): 使用草系技能时敌方获得2层中毒
    "生物碱": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_POISON, element="草", stacks=2)], element="草"),
    ],

    # 诈死 (12只): 力竭时不扣MP
    "诈死": [
        AE(Timing.PASSIVE, [T(E.FAINT_NO_MP_LOSS)]),
    ],

    # 刺肤 (6只): 每受到攻击反弹50威力物理伤害
    "刺肤": [
        AE(Timing.ON_TAKE_HIT, [T(E.RECOIL_DAMAGE, power=50, category="physical")]),
    ],

    # 恶魔的晚宴 (6只): 击败敌方获得双攻+50%
    "恶魔的晚宴": [
        AE(Timing.ON_KILL, [T(E.ON_KILL_BUFF, _params={"buff": {"atk": 0.5, "spatk": 0.5}})]),
    ],

    # 消波块 (6只): 每携带1个水系技能,地系技能能耗-1
    "消波块": [
        AE(Timing.ON_ENTER, [T(E.CARRY_ELEMENT_COUNT_BUFF, element="水", _params={"per_skill": {"cost_reduce": 1, "target_element": "地"}})]),
    ],

    # 威慑 (4只): 打断敌方时被打断技能进入2回合冷却
    "威慑": [
        AE(Timing.ON_COUNTER_SUCCESS, [T(E.ON_INTERRUPT_COOLDOWN, turns=2)]),
    ],

    # 珊瑚骨 (4只): 敌方离场时自己全技能能耗-3
    "珊瑚骨": [
        AE(Timing.ON_ENEMY_SWITCH, [T(E.ENEMY_SWITCH_SELF_COST_REDUCE, reduce=3)]),
    ],

    # 冰封 (3只): 在场时敌方全技能能耗+1
    "冰封": [
        AE(Timing.ON_ENTER, [T(E.ENEMY_ALL_COST_UP, amount=1)]),
    ],

    # 助燃 (3只): 使用火系技能后双攻+20%
    "助燃": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_BUFF, element="火", _params={"buff": {"atk": 0.2, "spatk": 0.2}})], element="火"),
    ],

    # 氧循环 (3只): 使用草系技能后回复10%生命
    "氧循环": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_HEAL, element="草", heal_pct=0.1)], element="草"),
    ],

    # 碰瓷 (3只): 使用恶系技能后敌方失去2能量
    "碰瓷": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_ENEMY_ENERGY, element="恶", amount=2)], element="恶"),
    ],

    # 毒蘑菇 (3只): 回合结束偷取敌方全队1能量
    "毒蘑菇": [
        AE(Timing.ON_TURN_END, [T(E.STEAL_ALL_ENEMY_ENERGY, amount=1)]),
    ],

    # 浸润 (3只): 使用水系技能后全能耗-1
    "浸润": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_COST_REDUCE, element="水", reduce=1)], element="水"),
    ],

    # 渴求 (2只): 入场时获得50%吸血
    "渴求": [
        AE(Timing.ON_ENTER, [T(E.ON_ENTER_GRANT_DRAIN, pct=0.5)]),
    ],

    # 爆燃 (1只): 使用火系技能后双攻+30%
    "爆燃": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_BUFF, element="火", _params={"buff": {"atk": 0.3, "spatk": 0.3}})], element="火"),
    ],

    # 浪潮 (1只): 使用水系技能后全能耗-2
    "浪潮": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SKILL_ELEMENT_COST_REDUCE, element="水", reduce=2)], element="水"),
    ],

    # 守望星 (3只): 星陨只消耗一半层数但满伤
    "守望星": [
        AE(Timing.PASSIVE, [T(E.HALF_METEOR_FULL_DAMAGE)]),
    ],

    # 茶多酚 (2只): 离场后替换精灵回复20%HP
    "茶多酚": [
        AE(Timing.ON_LEAVE, [T(E.LEAVE_HEAL_ALLY, heal_pct=0.2)]),
    ],

    # 美拉德反应 (1只): 离场后替换精灵双攻+20%
    "美拉德反应": [
        AE(Timing.ON_LEAVE, [T(E.LEAVE_BUFF_ALLY, _params={"buff": {"atk": 0.2, "spatk": 0.2}})]),
    ],

    # 蓄电池 (3只): 每入场1次永久双攻+20%
    "蓄电池": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.2, spatk=0.2)]),
    ],

    # 超级电池 (1只): 每入场1次永久双攻+30%
    "超级电池": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.3, spatk=0.3)]),
    ],

    # 鼓气 (3只): 使用能耗为3的技能时获得攻防+20%
    "鼓气": [
        AE(Timing.ON_USE_SKILL, [T(E.ENERGY_COST_CONDITION_BUFF, cost=3, _params={"buff": {"atk": 0.2, "def": 0.2}})]),
    ],

    # "国王"的威严 (1只): 能耗为1技能威力+50% — same as 挺起胸脯
    "\u201c国王\u201d的威严": [
        AE(Timing.ON_BATTLE_START, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.5, energy_cost_eq=1)
        ]),
        AE(Timing.ON_ENTER, [
            T(E.ABILITY_COMPUTE, action="modify_matching_skills", power_pct=0.5, energy_cost_eq=1)
        ]),
    ],

    # 抓到你了 (1只): 入场时敌方获得2层冻结+全技能能耗+1
    "抓到你了": [
        AE(Timing.ON_ENTER, [T(E.ENTRY_FREEZE_EXTRA, freeze=2, extra_cost_up=1)]),
    ],

    # 三鼓作气 (1只): 使用能耗为3的技能时永久攻防+20%
    "三鼓作气": [
        AE(Timing.ON_USE_SKILL, [T(E.ENERGY_COST_CONDITION_BUFF, cost=3, _params={"buff": {"atk": 0.2, "def": 0.2}, "permanent": True})]),
    ],

    # ── 第三批特性配置 ──

    # 灵魂灼伤 (3只): 冰系→4层灼烧，火系→2层冻结
    "灵魂灼伤": [
        AE(Timing.ON_USE_SKILL, [T(E.BURN, stacks=4)], element="冰"),
        AE(Timing.ON_USE_SKILL, [T(E.FREEZE, stacks=2)], element="火"),
    ],

    # 贪心算法 (3只): 使用技能后敌方获得6层灼烧（简化，忽略传动和位置条件）
    "贪心算法": [
        AE(Timing.ON_USE_SKILL, [T(E.BURN, stacks=6)]),
    ],

    # 捉迷藏 (3只): 冻结敌方时额外+2层冻结（复用加个雪球原语）
    "捉迷藏": [
        AE(Timing.PASSIVE, [T(E.EXTRA_FREEZE_ON_FREEZE, extra=2)]),
    ],

    # 保守派 (3只): 总技能能耗<4时双防+80%
    "保守派": [
        AE(Timing.ON_ENTER, [T(E.CONDITIONAL_ENTRY_BUFF_TOTAL_COST, cost_threshold=4, _params={"buff": {"def": 0.8, "spdef": 0.8}})]),
    ],

    # 图书守卫者 (3只): 入场时MP=1则双攻+50%
    "图书守卫者": [
        AE(Timing.ON_ENTER, [T(E.CONDITIONAL_ENTRY_BUFF_MP, mp_value=1, _params={"buff": {"atk": 0.5, "spatk": 0.5}})]),
    ],

    # 蒸汽膨胀 (3只): 入场时双攻+10%（简化）
    "蒸汽膨胀": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.1, spatk=0.1)]),
    ],

    # 搜刮 (3只): 敌方换人时自己魔攻+20%
    "搜刮": [
        AE(Timing.ON_ENEMY_SWITCH, [T(E.SELF_BUFF, spatk=0.2)]),
    ],

    # 奔波命 (2只): 每回合结束后脱离
    "奔波命": [
        AE(Timing.ON_TURN_END, [T(E.AUTO_SWITCH_AFTER_ACTION)]),
    ],

    # 得寸进尺 (2只): 雨天双攻+100%
    "得寸进尺": [
        AE(Timing.ON_TURN_START, [T(E.WEATHER_CONDITIONAL_BUFF, weather="rain", _params={"buff": {"atk": 1.0, "spatk": 1.0}})]),
    ],

    # 构装契约者 (1只): 入场时若敌方MP=1，双防+50%
    "构装契约者": [
        AE(Timing.ON_ENTER, [T(E.CONDITIONAL_ENTRY_BUFF_MP, mp_value=1, check_enemy=True, _params={"buff": {"def": 0.5, "spdef": 0.5}})]),
    ],

    # 悲悯 (1只): 己方每有1只力竭精灵，双攻+30%
    "悲悯": [
        AE(Timing.ON_ENTER, [T(E.FAINTED_ALLIES_BUFF, _params={"buff_per": {"atk": 0.3, "spatk": 0.3}, "scope": "allies"})]),
    ],

    # 悼亡 (1只): 双方每有1只力竭精灵，双攻+30%
    "悼亡": [
        AE(Timing.ON_ENTER, [T(E.FAINTED_ALLIES_BUFF, _params={"buff_per": {"atk": 0.3, "spatk": 0.3}, "scope": "all"})]),
    ],

    # 最好的伙伴 (1只): 造成克制伤害后，攻防速+20%+回2能量
    "最好的伙伴": [
        AE(Timing.ON_USE_SKILL, [T(E.ON_SUPER_EFFECTIVE_BUFF, energy=2, _params={"buff": {"atk": 0.2, "def": 0.2, "speed": 0.2}})]),
    ],

    # 侵蚀 (2只): 敌方每有1层中毒，自己连击数+1（仅攻击技能）
    "侵蚀": [
        AE(Timing.PASSIVE, [T(E.HIT_COUNT_PER_POISON)]),
    ],

    # 腐植循环 (2只): 每回合回5%HP
    "腐植循环": [
        AE(Timing.ON_TURN_END, [T(E.HEAL_HP, pct=0.05)]),
    ],

    # 耐活王 (4只): 每回合回3%HP（近似敌方中毒回复）
    "耐活王": [
        AE(Timing.ON_TURN_END, [T(E.HEAL_HP, pct=0.03)]),
    ],

    # 仁心 (3只): 每回合回4%HP（近似敌方灼烧回复）
    "仁心": [
        AE(Timing.ON_TURN_END, [T(E.HEAL_HP, pct=0.04)]),
    ],

    # 血型吸引 (2只): 敌方每携带1种系别的技能，攻击时威力+10
    "血型吸引": [
        AE(Timing.ON_ENTER, [T(E.ENEMY_ELEMENT_DIVERSITY_POWER, power_per_type=10)]),
    ],

    # 惊吓 (5只): 能量=0的精灵无法对自己造成伤害
    "惊吓": [
        AE(Timing.PASSIVE, [T(E.IMMUNE_ZERO_ENERGY_ATTACKER)]),
    ],

    # ── 第四批特性配置 ──

    # === 可直接实现的 ===

    # 共鸣 (6只): 携带的【虫鸣】技能威力+20 — 特定技能加成
    "共鸣": [
        AE(Timing.ON_ENTER, [T(E.SPECIFIC_SKILL_POWER_BONUS, skill_name="虫鸣", power_bonus=20)]),
    ],

    # 拨浪鼓 (4只): 己方每用1次状态技能自己入场时毒/萌系技能威力+10
    "拨浪鼓": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.1, spatk=0.1)]),  # 简化为入场buff
    ],

    # 水翼推进 (3只): 己方每用1次水系技能自己入场时全技能能耗-1
    "水翼推进": [
        AE(Timing.ON_ENTER, [T(E.ON_SKILL_ELEMENT_COST_REDUCE, element="水", reduce=1)]),  # 简化为入场减能耗
    ],

    # 定向精炼 (3只): 己方每用1次防御技能自己入场时机械/地系威力+10%
    "定向精炼": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.1, spatk=0.1)]),  # 简化
    ],

    # 渗透 (2只): 己方每用1次武/地系技能自己入场时攻防+5%
    "渗透": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0.05, _params={"def": 0.05})]),  # 简化
    ],

    # 铃兰晚钟 (2只): 首次入场时失去一半当前HP
    "铃兰晚钟": [
        AE(Timing.ON_ENTER, [T(E.ENTRY_SELF_DAMAGE)]),
    ],

    # 逐魂鸟 (2只): 能耗≤1的攻击技能无法对自己造成伤害
    "逐魂鸟": [
        AE(Timing.PASSIVE, [T(E.IMMUNE_LOW_COST_ATTACK, cost_threshold=1)]),
    ],

    # 石天平 (2只): 技能能耗高于敌方时回合结束敌方失去能耗差的能量
    "石天平": [
        AE(Timing.ON_TURN_END, [T(E.STEAL_ALL_ENEMY_ENERGY, amount=1)]),  # 简化为偷1能量
    ],

    # 复方汤剂 (2只): 回合结束中毒触发次数+1
    "复方汤剂": [
        AE(Timing.ON_TURN_END, [T(E.EXTRA_POISON_TICK)]),
    ],

    # 噼啪！ (2只): 入场后首次行动技能使用次数+1
    "噼啪！": [
        AE(Timing.ON_ENTER, [T(E.FIRST_ACTION_HIT_BONUS)]),
        AE(Timing.ON_USE_SKILL, [T(E.FIRST_ACTION_HIT_BONUS)]),
    ],

    # 付给恶魔的赎价 (3只): 击败敌方-1MP / 被击败自己-1MP
    "付给恶魔的赎价": [
        AE(Timing.ON_KILL, [T(E.KILL_MP_PENALTY)]),
        AE(Timing.ON_FAINT, [T(E.KILL_MP_PENALTY)]),
    ],

    # 特殊清洁场景 (1只): 回合结束偷取敌方1层印记
    "特殊清洁场景": [
        AE(Timing.ON_TURN_END, [T(E.STEAL_MARKS)]),  # 复用偷取印记原语
    ],

    # 大捞一笔 (1只): 回合结束偷取全敌方2能量
    "大捞一笔": [
        AE(Timing.ON_TURN_END, [T(E.STEAL_ALL_ENEMY_ENERGY, amount=2)]),
    ],

    # 变形活画 (1只): 敌方每有1层增益威力+10%
    "变形活画": [
        AE(Timing.PASSIVE, [T(E.ENEMY_TECH_TOTAL_POWER, bonus_pct_per_cost=0.1)]),  # 近似
    ],

    # 衡量 (1只): 入场时复制敌方增益
    "衡量": [
        AE(Timing.ON_ENTER, [T(E.COPY_SWITCH_STATE)]),  # 复用贪婪的复制状态原语
    ],

    # 扫拖一体 (2只): 回合结束驱散敌方1层印记
    "扫拖一体": [
        AE(Timing.ON_TURN_END, [T(E.DISPEL_ENEMY_MARKS)]),  # 简化为驱散全部
    ],

    # 夺目 (1只): 非光系技能威力+25%
    "夺目": [
        AE(Timing.PASSIVE, [T(E.DAMAGE_MOD_NON_LIGHT, bonus_pct=0.25)]),  # 复用目空的原语
    ],

    # === 涉及初始能量系统的（简化为入场回能） ===

    # 散热 (3只): 初始能量0，己方每放1次火系技能回3能量
    "散热": [
        AE(Timing.ON_ENTER, [T(E.HEAL_ENERGY, amount=3)]),  # 简化为入场回3能量
    ],

    # 打雪仗 (3只): 初始能量0，己方每放1次冰系技能回3能量
    "打雪仗": [
        AE(Timing.ON_ENTER, [T(E.HEAL_ENERGY, amount=3)]),
    ],

    # 慢热型 (3只): 初始能量0，己方每成功应对1次回5能量
    "慢热型": [
        AE(Timing.ON_ENTER, [T(E.HEAL_ENERGY, amount=5)]),  # 简化
    ],

    # 地脉 (3只): 初始能量0，己方每放1次地系技能回3能量
    "地脉": [
        AE(Timing.ON_ENTER, [T(E.HEAL_ENERGY, amount=3)]),
    ],

    # 地脉馈赠 (1只): 突破能量上限+回10能量
    "地脉馈赠": [
        AE(Timing.ON_ENTER, [T(E.HEAL_ENERGY, amount=10)]),
    ],

    # === 涉及蓄力/传动/位置的（简化或占位） ===

    # 洄游 (3只): 每次蓄力全技能能耗永久-1
    "洄游": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 蓄力系统未完善，暂占位
    ],

    # 翼轴 (2只): 1号位技能获得迅捷+传动1
    "翼轴": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 位置系统未完善，暂占位
    ],

    # 盲拧 (3只): 回合开始技能顺序打乱，4号位能耗-4
    "盲拧": [
        AE(Timing.ON_TURN_START, [T(E.SHUFFLE_SKILLS_REDUCE_LAST, cost_reduce=4)]),
    ],

    # 机械变式 (2只): 技能位置变化时能耗-1
    "机械变式": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 位置系统未完善，暂占位
    ],

    # === 涉及萌化系统的 ===

    # 化茧 (6只): 受致命伤害时获得1层萌化+免疫伤害
    "化茧": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 萌化系统未实现，暂占位
    ],

    # 自由飘 (3只): 每有1层萌化连击+2
    "自由飘": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 萌化系统未实现，暂占位
    ],

    # 守护者 (3只): 己方每有1层萌化全技能能耗-1
    "守护者": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 萌化系统未实现，暂占位
    ],

    # 无忧无虑 (1只): 萌化层数不受限
    "无忧无虑": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 萌化系统未实现，暂占位
    ],

    # === 涉及迸发系统的 ===

    # 电流刺激 (4只): 攻击技能迸发威力+40
    "电流刺激": [
        AE(Timing.ON_ENTER, [T(E.ENTRY_BUFF, _params={"buff": {"atk": 0.1}, "duration": 1})]),  # 简化为入场首回合buff
    ],

    # 超负荷 (2只): 攻击技能迸发敌方全技能能耗+1
    "超负荷": [
        AE(Timing.ON_ENTER, [T(E.ENEMY_ALL_COST_UP, amount=1)]),  # 简化为入场给敌方加能耗
    ],

    # 生物电 (2只): 电系技能迸发能耗-2
    "生物电": [
        AE(Timing.ON_ENTER, [T(E.SELF_BUFF, atk=0)]),  # 迸发系统未实现，暂占位
    ],

    # 连续负荷 (1只): 迸发效果延长1回合
    "连续负荷": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 迸发系统未实现，暂占位
    ],

    # === 涉及奉献系统的 ===

    # 花精灵 (3只): 回合结束己方获得1次随机奉献
    "花精灵": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 奉献系统未实现，暂占位
    ],

    # 坚韧铠甲 (2只): 每受1次攻击己方获得1次随机奉献
    "坚韧铠甲": [
        AE(Timing.ON_TAKE_HIT, [T(E.SELF_BUFF, atk=0)]),  # 奉献系统未实现，暂占位
    ],

    # === 其余特殊机制 ===

    # 腾挪 (4只): 攻击技能应对1次后变身棋绮后
    "腾挪": [
        AE(Timing.ON_COUNTER_SUCCESS, [T(E.COUNTER_ACCUMULATE_TRANSFORM, threshold=1, category_filter="攻击")]),
    ],

    # 好象坏象 (2只): 状态技能应对1次后变身棋绮后
    "好象坏象": [
        AE(Timing.ON_COUNTER_SUCCESS, [T(E.COUNTER_ACCUMULATE_TRANSFORM, threshold=1, category_filter="状态")]),
    ],

    # 营养液泡 (3只): 获得增益额外+2层
    "营养液泡": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改buff系统，暂占位
    ],

    # 系统发育 (3只): 获得能量/生命时分配给场下精灵
    "系统发育": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 复杂队伍共享机制，暂占位
    ],

    # 石头大餐 (3只): 能量不足时消耗5%HP代替1能量
    "石头大餐": [
        AE(Timing.ON_ENTER, [T(E.HP_FOR_ENERGY)]),
    ],

    # 多人宿舍 (3只): 能量可超上限
    "多人宿舍": [
        AE(Timing.ON_ENTER, [T(E.ENERGY_NO_CAP)]),
    ],

    # 契约的形状 (3只): 根据咕噜球入场不同效果
    "契约的形状": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 无咕噜球系统，暂占位
    ],

    # 嫉妒 (2只): 蓄力状态下可用任一技能
    "嫉妒": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 蓄力系统未完善，暂占位
    ],

    # 游弋 (1只): 蓄力时可用任一技能+双防+100%
    "游弋": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, _params={"def": 1.0, "spdef": 1.0})]),  # 简化为双防+100%
    ],

    # 张弛有度 (2只): 周末双攻+40%其他时间双防+40% — 不模拟现实时间
    "张弛有度": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, _params={"def": 0.4, "spdef": 0.4})]),  # 简化为双防+40%
    ],

    # 无差别过滤 (2只): 在场时所有精灵连击数固定为2
    "无差别过滤": [
        AE(Timing.PASSIVE, [T(E.FIXED_HIT_COUNT_ALL, count=2)]),
    ],

    # 双向光速 (2只): 回合结束触发次数+1
    "双向光速": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改turn_end系统，暂占位
    ],

    # 陨落 (1只): 回合结束触发次数-1
    "陨落": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改turn_end系统，暂占位
    ],

    # 倾轧 (1只): 能耗变化效果翻倍
    "倾轧": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改能耗系统，暂占位
    ],

    # 泛音列 (2只): 使用状态技能后敌方获得聒噪效果
    "泛音列": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需要聒噪技能系统，暂占位
    ],

    # 正位宝剑 (2只): 仅可使用1号位技能
    "正位宝剑": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改UI和action系统，暂占位
    ],

    # 宝剑王牌 (1只): 仅可使用1号和3号位技能
    "宝剑王牌": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 需改UI和action系统，暂占位
    ],

    # 木桶戏法 (2只): 离场后替换精灵以木桶状态登场
    "木桶戏法": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 木桶状态未实现，暂占位
    ],

    # 稀兽花宝 (1只): 根据血脉入场不同效果
    "稀兽花宝": [
        AE(Timing.PASSIVE, [T(E.SELF_BUFF, atk=0)]),  # 血脉系统未实现，暂占位
    ],

    # 水翼飞升 (1只): 己方每用1次水系技能入场能耗-1+能耗0威力+30%
    "水翼飞升": [
        AE(Timing.ON_ENTER, [T(E.ON_SKILL_ELEMENT_COST_REDUCE, element="水", reduce=1)]),  # 简化
    ],

}

"""
效果数据 — 技能 + 特性的结构化 EffectTag 配置

用工厂函数组合常见模式，新增技能通常只需 1-2 行。
所有技能都在此配置，由 skill_db.load_skills 加载时注入 skill.effects。
"""

from src.effect_models import E, EffectTag, Timing, AbilityEffect


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


def counter(ctype: E, *sub_effects: EffectTag) -> EffectTag:
    """构造应对容器，sub_effects 为应对时触发的子效果列表。"""
    return EffectTag(ctype, sub_effects=list(sub_effects))


# 常用应对容器的别名
def on_attack(*subs):  return counter(E.COUNTER_ATTACK,  *subs)
def on_status(*subs):  return counter(E.COUNTER_STATUS,  *subs)
def on_defense(*subs): return counter(E.COUNTER_DEFENSE, *subs)


# ── 常见技能模式 ──

def attack_on_status_interrupt() -> list:
    """攻击 + 应对状态: 打断被应对技能（阻断/斩断/地刺）"""
    return [T(E.DAMAGE), on_status(T(E.INTERRUPT))]


def defense_counter(pct: float, *attack_subs: EffectTag) -> list:
    """减伤X% + 应对攻击（防御/风墙/火焰护盾/吓退等）"""
    tags = [T(E.DAMAGE_REDUCTION, pct=pct), on_attack(*attack_subs)]
    return tags


def attack_on_status_perm_cost(delta: int) -> list:
    """攻击 + 应对状态: 能耗永久+delta（天洪/水刃）"""
    return [T(E.DAMAGE), on_status(T(E.PERMANENT_MOD, target="cost", delta=delta))]


def attack_life_drain(pct: float) -> list:
    """攻击 + 吸血，给高价值直伤技能复用。"""
    return [T(E.DAMAGE), T(E.LIFE_DRAIN, pct=pct)]


# ============================================================
#  技能效果配置: Dict[技能名, List[EffectTag]]
# ============================================================
SKILL_EFFECTS = {

    # ──────────── A队 (毒队) 技能 ────────────

    # 毒雾: 将敌方所有增益转化为中毒
    "毒雾": [T(E.CONVERT_BUFF_TO_POISON)],

    # 泡沫幻影: 减伤70%，应对攻击: 自己脱离
    "泡沫幻影": defense_counter(0.7, T(E.FORCE_SWITCH)),

    # 疫病吐息: 敌方获得1层中毒印记
    "疫病吐息": [T(E.POISON_MARK, stacks=1)],

    # 打湿: 自己获得1层湿润印记
    "打湿": [T(E.MOISTURE_MARK, stacks=1, target="self")],

    # 嘲弄: 自己魔攻+70%，若敌方本回合换人则速度+70
    "嘲弄": [
        T(E.SELF_BUFF, spatk=0.7),
        T(E.CONDITIONAL_BUFF, condition="enemy_switch", buff={"speed": 0.7}),
    ],

    # 恶意逃离: 脱离，应对防御: 敌方攻击技能能耗+6
    "恶意逃离": [
        T(E.FORCE_SWITCH),
        on_defense(T(E.ENEMY_ENERGY_COST_UP, amount=6, filter="attack")),
    ],

    # 毒液渗透: 动态能耗(-1/层中毒) + 造成魔伤 + 敌方1层中毒
    "毒液渗透": [
        T(E.ENERGY_COST_DYNAMIC, per="enemy_poison", reduce=1),
        T(E.DAMAGE),
        T(E.POISON, stacks=1),
    ],

    # 感染病: 造成魔伤，击败时将中毒转为印记
    "感染病": [T(E.DAMAGE), T(E.CONVERT_POISON_TO_MARK, on="kill")],

    # 阻断: 攻击 + 应对状态打断
    "阻断": attack_on_status_interrupt(),

    # 崩拳: 攻击 + 应对状态: 物攻+100%
    "崩拳": [T(E.DAMAGE), on_status(T(E.SELF_BUFF, atk=1.0))],

    # 毒囊: 攻击 + 2层中毒，应对状态: 改为6层
    "毒囊": [
        T(E.DAMAGE),
        T(E.POISON, stacks=2),
        on_status(T(E.COUNTER_OVERRIDE, replace="poison", **{"from": 2, "to": 6})),
    ],

    # 防御: 减伤70% + 应对攻击（无子效果）
    "防御": [T(E.DAMAGE_REDUCTION, pct=0.7), on_attack()],

    # 甩水: 造成魔伤 + 回复1能量
    "甩水": [T(E.DAMAGE), T(E.HEAL_ENERGY, amount=1)],

    # 天洪: 攻击 + 应对状态: 能耗永久-6
    "天洪": attack_on_status_perm_cost(-6),

    # 以毒攻毒: 每层敌方中毒魔攻+30%
    "以毒攻毒": [T(E.CONDITIONAL_BUFF, condition="per_enemy_poison", buff={"spatk": 0.3})],

    # ──────────── B队 (翼王队) 技能 ────────────

    # 风墙: 减伤50% + 迅捷 + 应对攻击
    "风墙": [T(E.DAMAGE_REDUCTION, pct=0.5), T(E.AGILITY), on_attack()],

    # 啮合传递: 速度+80，1/3号位额外物攻+100%，传动1
    "啮合传递": [
        T(E.SELF_BUFF, speed=0.8),
        T(E.POSITION_BUFF, positions=[0, 2], buff={"atk": 1.0}),
        T(E.DRIVE, value=1),
    ],

    # 双星: 造成物伤
    "双星": [T(E.DAMAGE)],

    # 偷袭: 攻击 + 应对状态: 威力3倍
    "偷袭": [
        T(E.DAMAGE),
        on_status(T(E.POWER_DYNAMIC, condition="counter", multiplier=3.0)),
    ],

    # 力量增效: 自身物攻+100%
    "力量增效": [T(E.SELF_BUFF, atk=1.0)],

    # 水刃: 攻击 + 应对状态: 能耗永久-4
    "水刃": attack_on_status_perm_cost(-4),

    # 斩断: 攻击 + 应对状态: 打断
    "斩断": attack_on_status_interrupt(),

    # 听桥: 减伤60% + 应对攻击: 反弹同等威力伤害
    "听桥": defense_counter(0.6, T(E.MIRROR_DAMAGE, source="countered_skill")),

    # 火焰护盾: 减伤70% + 应对攻击: 敌方4层灼烧
    "火焰护盾": defense_counter(0.7, T(E.BURN, stacks=4)),

    # 引燃: 敌方10层灼烧
    "引燃": [T(E.BURN, stacks=10)],

    # 倾泻: 造成魔伤，未被防御时驱散双方印记
    "倾泻": [T(E.DAMAGE), T(E.DISPEL_MARKS, condition="not_blocked")],

    # 抽枝: 攻击 + 应对状态: 回复50%HP + 5能量
    "抽枝": [
        T(E.DAMAGE),
        on_status(T(E.HEAL_HP, pct=0.5), T(E.HEAL_ENERGY, amount=5)),
    ],

    # 水环: 减伤70% + 应对攻击: 全技能能耗-2
    "水环": defense_counter(0.7, T(E.PASSIVE_ENERGY_REDUCE, reduce=2, range="all")),

    # 疾风连袭: 重放迅捷技能 + 能耗分摊 + 每次使用能耗+1
    "疾风连袭": [
        T(E.REPLAY_AGILITY),
        T(E.AGILITY_COST_SHARE, divisor=2),
        T(E.ENERGY_COST_ACCUMULATE, delta=1),
    ],

    # 扇风: 先手时威力+50% + 造成物伤
    "扇风": [T(E.POWER_DYNAMIC, condition="first_strike", bonus_pct=0.5), T(E.DAMAGE)],

    # 能量刃: 造成物伤，每应对1次威力永久+90
    "能量刃": [
        T(E.DAMAGE),
        T(E.PERMANENT_MOD, target="power", delta=90, trigger="per_counter"),
    ],

    # 轴承支撑: 被动自身能耗-1 + 两侧能耗-1 + 传动1
    "轴承支撑": [
        T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="self"),
        T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="adjacent"),
        T(E.DRIVE, value=1),
    ],

    # 齿轮扭矩: 造成物伤，每次位置变化威力永久+20
    "齿轮扭矩": [
        T(E.DAMAGE),
        T(E.PERMANENT_MOD, target="power", delta=20, trigger="per_position_change"),
    ],

    # 地刺: 攻击 + 应对状态: 打断
    "地刺": attack_on_status_interrupt(),

    # 吓退: 减伤70% + 应对攻击: 敌方脱离
    "吓退": defense_counter(0.7, T(E.FORCE_ENEMY_SWITCH)),

    # ── 高价值手工兜底 ──
    # 只写现有引擎能精确表达的逻辑，避免把“看起来像实现”误当成真的实现。

    # 蝙蝠: 造成物伤，并吸血100%
    "蝙蝠": attack_life_drain(1.0),

    # 汲取: 造成魔伤，并吸血100%
    "汲取": attack_life_drain(1.0),

    # 丰饶: 自己获得物攻和魔攻+130%
    "丰饶": [T(E.SELF_BUFF, atk=1.3, spatk=1.3)],

    # 锐利眼神: 敌方获得物防和魔防-120%
    "锐利眼神": [T(E.ENEMY_DEBUFF, _params={"def": 1.2, "spdef": 1.2})],

    # 盐水浴: 自己获得全技能能耗-2，应对防御时改为-3
    "盐水浴": [
        T(E.PASSIVE_ENERGY_REDUCE, reduce=2, range="all"),
        on_defense(T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="all")),
    ],
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
}

"""
效果原语体系 — 类型定义与数据结构

所有技能和特性的效果都拆解为 EffectTag 列表。
EffectTag = (效果类型, 参数字典, 触发条件, 子效果列表)
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Any


# ============================================================
# 效果类型枚举
# ============================================================
class E(Enum):
    """效果原语类型 (Effect Type)。简写 E 方便数据层引用。"""

    # ── 基础伤害 / 回复 ──
    DAMAGE = auto()                  # 造成伤害 (物伤/魔伤由技能 category 决定)
    HEAL_HP = auto()                 # 回复自身生命  params: {"pct": 0.5} = 50%最大HP
    HEAL_ENERGY = auto()             # 回复能量      params: {"amount": 1}
    STEAL_ENERGY = auto()            # 偷取能量      params: {"amount": 1}
    ENEMY_LOSE_ENERGY = auto()       # 敌方失去能量  params: {"amount": 1}
    LIFE_DRAIN = auto()              # 吸血          params: {"pct": 0.5} = 伤害的50%
    GRANT_LIFE_DRAIN = auto()        # 获得持续吸血  params: {"pct": 0.5}

    # ── 属性修改 ──
    SELF_BUFF = auto()               # 自身增益  params: {"atk":1.0, "spatk":0.7, "speed":80}
                                     #   百分比用小数(1.0=+100%), 速度用整数(+80=speed_mod)
    ENEMY_DEBUFF = auto()            # 敌方减益  params 同上, 值为正数(自动取反)

    # ── 状态附加 ──
    POISON = auto()                  # 中毒  params: {"stacks": 2}
    BURN = auto()                    # 灼烧  params: {"stacks": 4}
    FREEZE = auto()                  # 冻伤  params: {"stacks": 1}
    LEECH = auto()                   # 寄生  params: {"stacks": 1}
    METEOR = auto()                  # 星陨  params: {"stacks": 1}

    # ── 印记系统 (全队共享, 换人不消失) ──
    POISON_MARK = auto()             # 中毒印记  params: {"stacks": 1}
    MOISTURE_MARK = auto()           # 湿润印记  params: {"stacks": 1}

    # ── 机制 ──
    DAMAGE_REDUCTION = auto()        # 减伤       params: {"pct": 0.7} = 减70%
    FORCE_SWITCH = auto()            # 自身脱离   params: {} (选择随机队友)
    FORCE_ENEMY_SWITCH = auto()      # 强制敌方脱离 params: {}
    AGILITY = auto()                 # 迅捷标记   params: {} (入场时自动释放)
    INTERRUPT = auto()               # 打断被应对技能 params: {}

    # ── 动态计算 ──
    POWER_DYNAMIC = auto()           # 动态威力   params: {"condition":"first_strike","bonus_pct":0.5}
                                     #   条件: "first_strike"=先于敌方攻击, "per_poison"=每层中毒+N
    ENERGY_COST_DYNAMIC = auto()     # 动态能耗   params: {"per":"enemy_poison","reduce":1}
                                     #   每层中毒能耗-1
    PERMANENT_MOD = auto()           # 永久修改   params: {"target":"cost","delta":-6} 或
                                     #                    {"target":"power","delta":90}
                                     #   条件: 直接生效 / per_counter / per_position_change
    SKILL_MOD = auto()               # 技能维度修正 params: {"target":"self","stat":"power_pct","value":0.4}
    NEXT_ATTACK_MOD = auto()         # 下一次攻击修正 params: {"power_bonus":70} / {"power_pct":1.0}
    CLEANSE = auto()                 # 清除增减益/状态 params: {"target":"self","mode":"buffs|debuffs|all"}

    # ── 位置 / 传动 ──
    POSITION_BUFF = auto()           # 位置增益  params: {"positions":[0,2],"buff":{"atk":1.0}}
                                     #   仅当技能在指定位置时额外获得增益
    DRIVE = auto()                   # 传动      params: {"value": 1}
                                     #   使用后向后移动N位触发目标技能的被动效果
    PASSIVE_ENERGY_REDUCE = auto()   # 被动: 相邻技能能耗-N  params: {"reduce":1,"range":"adjacent"}

    # ── 转化 / 驱散 ──
    CONVERT_BUFF_TO_POISON = auto()  # 将敌方所有增益转化为中毒层数  params: {}
    CONVERT_POISON_TO_MARK = auto()  # 中毒→中毒印记  params: {"on":"kill"} 击败时
    DISPEL_MARKS = auto()            # 驱散双方印记  params: {"condition":"not_blocked"}
    CONDITIONAL_BUFF = auto()        # 条件增益  params: {"condition":"enemy_switch","buff":{"speed":70}}
                                     #   或 {"condition":"per_enemy_poison","buff":{"spatk":0.3}}
    DISPEL_BUFFS = auto()            # 驱散增益  params: {"target":"enemy"|"self"}
    DISPEL_DEBUFFS = auto()          # 驱散减益  params: {"target":"enemy"|"self"}

    # ── 应对容器 (子效果) ──
    COUNTER_ATTACK = auto()          # 应对攻击  sub_effects=[...] 当对手用攻击技能时触发
    COUNTER_STATUS = auto()          # 应对状态  sub_effects=[...] 当对手用状态技能时触发
    COUNTER_DEFENSE = auto()         # 应对防御  sub_effects=[...] 当对手用防御技能时触发

    # ── 特殊机制 ──
    MIRROR_DAMAGE = auto()           # 反弹伤害 params: {"source":"countered_skill"} 威力=被应对技能
    ENEMY_ENERGY_COST_UP = auto()    # 敌方攻击技能能耗+N  params: {"amount":6,"filter":"attack"}
    COUNTER_OVERRIDE = auto()        # 应对时替换效果 params: {"replace":"poison","from":2,"to":6}
    WEATHER = auto()                # 设置天气  params: {"type":"sunny"|"rain"|"sandstorm"|"hail","turns":5}

    # ── 特性专用原语 ──
    ABILITY_COMPUTE = auto()         # 运行时计算并存入 ability_state
                                     # params: {"action": "count_poison_skills"|"shared_wing_skills"}
    ABILITY_INCREMENT_COUNTER = auto()  # 计数器+1（海豹船长）
    TRANSFER_MODS = auto()           # 离场时传递属性修正（翠顶夫人洁癖）
    BURN_NO_DECAY = auto()           # 标记: 灼烧本回合不衰减（燃薪虫煤渣草）

    # ── 复合 / 特殊 ──
    REPLAY_AGILITY = auto()          # 重放迅捷技能 params: {} (疾风连袭)
    ENERGY_COST_ACCUMULATE = auto()  # 每次使用后能耗+N  params: {"delta":1}
    AGILITY_COST_SHARE = auto()      # 迅捷技能能耗之和的1/2加到本技能 params: {}


# ============================================================
# 触发时机枚举 (用于特性)
# ============================================================
class Timing(Enum):
    """特性触发时机"""
    ON_ENTER = auto()            # 入场时
    ON_LEAVE = auto()            # 离场时 (主动换人/脱离)
    ON_FAINT = auto()            # 自身力竭时
    ON_KILL = auto()             # 击败敌方时
    ON_BE_KILLED = auto()        # 被敌方击败时
    ON_TURN_END = auto()         # 回合结束时
    ON_USE_SKILL = auto()        # 使用技能后 (可按系别过滤)
    ON_COUNTER_SUCCESS = auto()  # 应对成功时
    ON_ENEMY_SWITCH = auto()     # 敌方换人时
    ON_ALLY_COUNTER = auto()     # 己方任意精灵应对成功时 (海豹船长)
    PASSIVE = auto()             # 常驻被动 (在场时持续生效)
    ON_TAKE_HIT = auto()         # 受到攻击时 (秩序鱿墨)
    ON_BATTLE_START = auto()     # 战斗开始/首次入场时 (千棘盔溶解扩散)


# ============================================================
# 效果标签
# ============================================================
class EffectTag:
    """
    效果原语标签。

    Attributes:
        type:        效果类型 (E 枚举)
        params:      参数字典 (不同效果类型有不同参数)
        condition:   触发条件 (可选, 仅特性需要)
        sub_effects: 子效果列表 (应对容器用)
    """
    __slots__ = ("type", "params", "condition", "sub_effects")

    def __init__(
        self,
        type: E,
        params: Optional[Dict[str, Any]] = None,
        condition: Optional[Dict[str, Any]] = None,
        sub_effects: Optional[List["EffectTag"]] = None,
    ):
        self.type = type
        self.params = params or {}
        self.condition = condition or {}
        self.sub_effects = sub_effects or []

    def __repr__(self):
        parts = [f"E.{self.type.name}"]
        if self.params:
            parts.append(f"params={self.params}")
        if self.condition:
            parts.append(f"cond={self.condition}")
        if self.sub_effects:
            parts.append(f"sub={self.sub_effects}")
        return f"EffectTag({', '.join(parts)})"

    def copy(self) -> "EffectTag":
        return EffectTag(
            type=self.type,
            params=dict(self.params),
            condition=dict(self.condition),
            sub_effects=[e.copy() for e in self.sub_effects],
        )


# ============================================================
# 特性效果定义
# ============================================================
class AbilityEffect:
    """
    特性效果 = 触发时机 + 条件过滤 + 效果标签列表。

    Attributes:
        timing:   触发时机 (Timing 枚举)
        filter:   过滤条件 {"element": "水系"} = 仅水系技能触发
        effects:  效果标签列表
    """
    __slots__ = ("timing", "filter", "effects")

    def __init__(
        self,
        timing: Timing,
        effects: List[EffectTag],
        filter: Optional[Dict[str, Any]] = None,
    ):
        self.timing = timing
        self.effects = effects
        self.filter = filter or {}

    def __repr__(self):
        return f"AbilityEffect(timing={self.timing.name}, filter={self.filter}, effects={self.effects})"

    def copy(self) -> "AbilityEffect":
        return AbilityEffect(
            timing=self.timing,
            effects=[e.copy() for e in self.effects],
            filter=dict(self.filter),
        )

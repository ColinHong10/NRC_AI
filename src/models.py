"""
洛克王国战斗模拟系统 - 数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class StatusType(Enum):
    NORMAL = "normal"
    FAINTED = "fainted"


class StatType(Enum):
    HP = "hp"
    ATTACK = "attack"
    DEFENSE = "defense"
    SP_ATTACK = "sp_attack"
    SP_DEFENSE = "sp_defense"
    SPEED = "speed"


class Type(Enum):
    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    ELECTRIC = "electric"
    GRASS = "grass"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"
    LIGHT = "light"


class SkillCategory(Enum):
    PHYSICAL = "物攻"
    MAGICAL = "魔攻"
    DEFENSE = "防御"
    STATUS = "状态"


# 属性克制表（洛克王国真实数据，来自游戏内克制图表）
TYPE_CHART: Dict[str, Dict[str, float]] = {
    "normal":   {"ground": 0.5, "ghost": 0.5, "steel": 0.5},
    "grass":    {"fire": 0.5, "water": 2, "light": 2, "ground": 2, "dragon": 0.5, "poison": 0.5, "bug": 0.5, "flying": 0.5, "steel": 0.5},
    "fire":     {"grass": 2, "water": 0.5, "ground": 0.5, "ice": 2, "dragon": 0.5, "bug": 2, "steel": 2},
    "water":    {"grass": 0.5, "fire": 2, "ground": 2, "ice": 0.5, "dragon": 0.5, "steel": 2},
    "light":    {"grass": 0.5, "ice": 0.5, "ghost": 2, "dark": 2},
    "ground":   {"grass": 0.5, "fire": 2, "ice": 2, "electric": 2, "poison": 2, "fighting": 0.5},
    "ice":      {"grass": 2, "fire": 0.5, "ground": 2, "ice": 0.5, "dragon": 2, "flying": 2, "steel": 0.5},
    "dragon":   {"dragon": 2, "steel": 0.5},
    "electric": {"grass": 0.5, "water": 2, "ground": 0.5, "dragon": 0.5, "electric": 0.5, "flying": 2},
    "poison":   {"grass": 2, "ground": 0.5, "poison": 0.5, "fairy": 2, "ghost": 0.5, "steel": 0.5},
    "bug":      {"grass": 2, "fire": 0.5, "poison": 0.5, "fighting": 0.5, "flying": 0.5, "fairy": 0.5, "ghost": 0.5, "dark": 2, "steel": 0.5, "psychic": 2},
    "fighting": {"normal": 2, "ground": 2, "ice": 2, "poison": 0.5, "bug": 0.5, "flying": 0.5, "fairy": 0.5, "ghost": 0.5, "dark": 2, "steel": 2, "psychic": 0.5},
    "flying":   {"grass": 2, "ground": 0.5, "dragon": 0.5, "electric": 0.5, "bug": 2, "fighting": 2, "steel": 0.5},
    "fairy":    {"fire": 0.5, "dragon": 2, "poison": 0.5, "fighting": 2, "dark": 2, "steel": 0.5},
    "ghost":    {"normal": 0.5, "light": 2, "ghost": 2, "dark": 0.5, "psychic": 2},
    "dark":     {"light": 0.5, "poison": 2, "fighting": 0.5, "fairy": 2, "ghost": 2, "dark": 0.5},
    "steel":    {"fire": 0.5, "water": 0.5, "ground": 2, "ice": 2, "electric": 0.5, "fairy": 2, "steel": 0.5},
    "psychic":  {"light": 0.5, "poison": 2, "fighting": 2, "steel": 0.5, "psychic": 0.5},
}

# 属性映射（中文 -> Type enum）
TYPE_NAME_MAP = {
    "普通系": Type.NORMAL, "火系": Type.FIRE, "水系": Type.WATER,
    "电系": Type.ELECTRIC, "草系": Type.GRASS, "冰系": Type.ICE,
    "武系": Type.FIGHTING, "毒系": Type.POISON, "地系": Type.GROUND,
    "翼系": Type.FLYING, "幻系": Type.PSYCHIC, "虫系": Type.BUG,
    "机械系": Type.STEEL, "幽系": Type.GHOST, "龙系": Type.DRAGON,
    "恶系": Type.DARK, "萌系": Type.FAIRY, "光系": Type.LIGHT,
}

CATEGORY_NAME_MAP = {
    "物攻": SkillCategory.PHYSICAL, "魔攻": SkillCategory.MAGICAL,
    "防御": SkillCategory.DEFENSE, "变化": SkillCategory.STATUS, "状态": SkillCategory.STATUS,
}


def get_type_effectiveness(attack_type: Type, defense_type: Type) -> float:
    a, d = attack_type.value, defense_type.value
    if a in TYPE_CHART and d in TYPE_CHART[a]:
        return TYPE_CHART[a][d]
    return 1.0


@dataclass
class Skill:
    """技能 - 完整数据模型"""
    name: str
    skill_type: Type
    category: SkillCategory
    power: int
    energy_cost: int
    hit_count: int = 1

    # 效果标记
    life_drain: float = 0          # 吸血比例 (0.5 = 50%)
    damage_reduction: float = 0    # 减伤比例 (0.7 = 减70%)
    self_heal_hp: float = 0        # 回复HP比例
    self_heal_energy: int = 0      # 回复能量
    steal_energy: int = 0          # 偷取能量
    enemy_lose_energy: int = 0     # 敌方失去能量
    enemy_energy_cost_up: int = 0  # 敌方技能能耗+X
    priority_mod: int = 0          # 先手修正
    force_switch: bool = False     # 折返/脱离
    agility: bool = False          # 迅捷：主动换人入场时自动释放
    charge: bool = False           # 蓄力：本回合蓄力，下回合释放
    leech_stacks: int = 0          # 寄生层数 (每层8%/回合)
    meteor_stacks: int = 0         # 星陨层数 (3回合后每层30威力魔攻伤害)
    is_mark: bool = False          # True=印记(同位置各1正1负), False=个体Buff(换人消失)

    # 自身属性修改 (加法叠加, 1.0表示+100%)
    self_atk: float = 0
    self_def: float = 0
    self_spatk: float = 0
    self_spdef: float = 0
    self_speed: float = 0
    self_all_atk: float = 0       # 双攻
    self_all_def: float = 0       # 双防

    # 敌方属性修改
    enemy_atk: float = 0
    enemy_def: float = 0
    enemy_spatk: float = 0
    enemy_spdef: float = 0
    enemy_speed: float = 0
    enemy_all_atk: float = 0
    enemy_all_def: float = 0

    # 状态层数
    poison_stacks: int = 0
    burn_stacks: int = 0
    freeze_stacks: int = 0

    # 应对效果 (防御/状态技能对特定类型对手时的额外效果)
    counter_physical_drain: float = 0    # 应对攻击时吸血
    counter_physical_energy_drain: int = 0
    counter_physical_self_atk: float = 0
    counter_physical_enemy_def: float = 0
    counter_physical_enemy_atk: float = 0
    counter_physical_power_mult: float = 0  # 应对状态时威力倍率
    counter_defense_self_atk: float = 0
    counter_defense_self_def: float = 0
    counter_defense_enemy_def: float = 0
    counter_defense_enemy_atk: float = 0
    counter_defense_enemy_energy_cost: int = 0
    counter_defense_power_mult: float = 0
    counter_status_power_mult: float = 0
    counter_status_enemy_lose_energy: int = 0
    counter_status_poison_stacks: int = 0
    counter_status_burn_stacks: int = 0
    counter_status_freeze_stacks: int = 0
    counter_skill_cooldown: int = 0       # 被应对技能冷却
    counter_damage_reflect: float = 0    # 反弹伤害比例

    # ── 新引擎字段 ──
    effects: List[Any] = field(default_factory=list)  # List[EffectTag], 有值则走新引擎

    def copy(self):
        s = Skill(
            name=self.name, skill_type=self.skill_type, category=self.category,
            power=self.power, energy_cost=self.energy_cost, hit_count=self.hit_count,
            life_drain=self.life_drain, damage_reduction=self.damage_reduction,
            self_heal_hp=self.self_heal_hp, self_heal_energy=self.self_heal_energy,
            steal_energy=self.steal_energy, enemy_lose_energy=self.enemy_lose_energy,
            enemy_energy_cost_up=self.enemy_energy_cost_up, priority_mod=self.priority_mod,
            force_switch=self.force_switch, agility=self.agility, charge=self.charge,
            leech_stacks=self.leech_stacks, meteor_stacks=self.meteor_stacks,
            is_mark=self.is_mark,
            self_atk=self.self_atk, self_def=self.self_def, self_spatk=self.self_spatk,
            self_spdef=self.self_spdef, self_speed=self.self_speed,
            self_all_atk=self.self_all_atk, self_all_def=self.self_all_def,
            enemy_atk=self.enemy_atk, enemy_def=self.enemy_def,
            enemy_spatk=self.enemy_spatk, enemy_spdef=self.enemy_spdef,
            enemy_speed=self.enemy_speed, enemy_all_atk=self.enemy_all_atk,
            enemy_all_def=self.enemy_all_def,
            poison_stacks=self.poison_stacks, burn_stacks=self.burn_stacks,
            freeze_stacks=self.freeze_stacks,
            counter_physical_drain=self.counter_physical_drain,
            counter_physical_energy_drain=self.counter_physical_energy_drain,
            counter_physical_self_atk=self.counter_physical_self_atk,
            counter_physical_enemy_def=self.counter_physical_enemy_def,
            counter_physical_enemy_atk=self.counter_physical_enemy_atk,
            counter_physical_power_mult=self.counter_physical_power_mult,
            counter_defense_self_atk=self.counter_defense_self_atk,
            counter_defense_self_def=self.counter_defense_self_def,
            counter_defense_enemy_def=self.counter_defense_enemy_def,
            counter_defense_enemy_atk=self.counter_defense_enemy_atk,
            counter_defense_enemy_energy_cost=self.counter_defense_enemy_energy_cost,
            counter_defense_power_mult=self.counter_defense_power_mult,
            counter_status_power_mult=self.counter_status_power_mult,
            counter_status_enemy_lose_energy=self.counter_status_enemy_lose_energy,
            counter_status_poison_stacks=self.counter_status_poison_stacks,
            counter_status_burn_stacks=self.counter_status_burn_stacks,
            counter_status_freeze_stacks=self.counter_status_freeze_stacks,
            counter_skill_cooldown=self.counter_skill_cooldown,
            counter_damage_reflect=self.counter_damage_reflect,
        )
        s.effects = [e.copy() for e in self.effects] if self.effects else []
        if hasattr(self, "_base_energy_cost"):
            s._base_energy_cost = self._base_energy_cost
        return s


@dataclass
class Pokemon:
    """精灵"""
    name: str
    pokemon_type: Type
    hp: int
    attack: int
    defense: int
    sp_attack: int
    sp_defense: int
    speed: int
    ability: str = ""
    skills: List[Skill] = field(default_factory=list)

    current_hp: int = 0
    energy: int = 10  # 登场时满能量，上限10
    status: StatusType = StatusType.NORMAL

    # 属性修正：拆分为4个方向（up=提升量, down=降低量，均为正值）
    # 能力等级 = (1 + 我方up + 敌方down) / (1 + 我方down + 敌方up)
    atk_up: float = 0.0      # 我方物攻提升
    atk_down: float = 0.0    # 我方物攻降低（来自敌方减益）
    def_up: float = 0.0      # 我方物防提升
    def_down: float = 0.0    # 我方物防降低
    spatk_up: float = 0.0
    spatk_down: float = 0.0
    spdef_up: float = 0.0
    spdef_down: float = 0.0
    speed_up: float = 0.0
    speed_down: float = 0.0

    # 独立威力提升乘法层（技能特效/特性触发，站场持续，下场重置为1.0）
    power_multiplier: float = 1.0

    life_drain_mod: float = 0.0
    skill_power_bonus: int = 0
    skill_power_pct_mod: float = 0.0
    skill_cost_mod: int = 0
    hit_count_mod: int = 0
    priority_stage: int = 0
    next_attack_power_bonus: int = 0
    next_attack_power_pct: float = 0.0

    # 状态层数
    poison_stacks: int = 0          # 中毒层数 (每层3%/回合, 换人清除)
    burn_stacks: int = 0            # 燃烧层数 (每层4%/回合, 每回合减半min1, 换人清除)
    frostbite_damage: int = 0       # 冻伤累计不可恢复伤害 (每回合+hp//12, 换人不清除)
    leech_stacks: int = 0           # 寄生层数 (每层8%/回合, 换人清除)
    meteor_stacks: int = 0          # 星陨层数 (延迟爆炸)
    meteor_countdown: int = 0       # 星陨倒计时 (>0时每回合-1, =0时引爆)

    # 蓄力状态
    charging_skill_idx: int = -1    # 正在蓄力的技能index (-1=没有蓄力)

    # 技能冷却 (index -> cooldown turns remaining)
    cooldowns: Dict[int, int] = field(default_factory=dict)

    # 旧字段保留兼容
    freeze_stacks: int = 0


    # ── 新引擎字段 ──
    ability_effects: List[Any] = field(default_factory=list)  # List[AbilityEffect]
    ability_state: Dict[str, Any] = field(default_factory=dict)  # 特性运行时状态

    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.hp

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0 or self.status == StatusType.FAINTED

    @property
    def effective_max_hp(self) -> int:
        """冻伤后的有效最大HP (从左侧侵蚀)"""
        return max(0, self.hp - self.frostbite_damage)

    def gain_energy(self, amount: int) -> None:
        """增加能量，不超过上限10（除非有 energy_no_cap 特性）"""
        if self.ability_state.get("energy_no_cap"):
            self.energy = self.energy + amount
        else:
            self.energy = min(10, self.energy + amount)

    @staticmethod
    def _clamp_up(val: float) -> float:
        """正向修正上界 [0.0, 4.0]"""
        return max(0.0, min(4.0, val))

    @staticmethod
    def _clamp_down(val: float) -> float:
        """降低量上界 [0.0, 0.9]，防止防御/攻击降低超过90%"""
        return max(0.0, min(0.9, val))

    def effective_atk(self) -> float:
        return self.attack * (1.0 + self._clamp_up(self.atk_up)) / max(0.1, 1.0 + self._clamp_down(self.atk_down))

    def effective_def(self) -> float:
        return self.defense * (1.0 + self._clamp_up(self.def_up)) / max(0.1, 1.0 + self._clamp_down(self.def_down))

    def effective_spatk(self) -> float:
        return self.sp_attack * (1.0 + self._clamp_up(self.spatk_up)) / max(0.1, 1.0 + self._clamp_down(self.spatk_down))

    def effective_spdef(self) -> float:
        return self.sp_defense * (1.0 + self._clamp_up(self.spdef_up)) / max(0.1, 1.0 + self._clamp_down(self.spdef_down))

    def effective_speed(self) -> float:
        return self.speed * (1.0 + self._clamp_up(self.speed_up)) / max(0.1, 1.0 + self._clamp_down(self.speed_down))

    def apply_self_buff(self, skill: Skill) -> None:
        """应用技能的自身增益（写入 *_up 字段）"""
        self.atk_up += skill.self_atk + skill.self_all_atk
        self.def_up += skill.self_def + skill.self_all_def
        self.spatk_up += skill.self_spatk + skill.self_all_atk
        self.spdef_up += skill.self_spdef + skill.self_all_def
        self.speed_up += skill.self_speed

    def apply_enemy_debuff(self, skill: Skill) -> None:
        """应用技能的敌方减益（写入 *_down 字段，参数值为正）"""
        self.atk_down += skill.enemy_atk + skill.enemy_all_atk
        self.def_down += skill.enemy_def + skill.enemy_all_def
        self.spatk_down += skill.enemy_spatk + skill.enemy_all_atk
        self.spdef_down += skill.enemy_spdef + skill.enemy_all_def
        self.speed_down += skill.enemy_speed

    def on_switch_out(self) -> None:
        """下场时清除：个体Buff（含方向mod）+ 威力乘数 + 中毒 + 燃烧 + 寄生 + 蓄力。冻伤和星陨保留。"""
        self.atk_up = self.atk_down = 0.0
        self.def_up = self.def_down = 0.0
        self.spatk_up = self.spatk_down = 0.0
        self.spdef_up = self.spdef_down = 0.0
        self.speed_up = self.speed_down = 0.0
        self.power_multiplier = 1.0
        self.life_drain_mod = 0.0
        self.skill_power_bonus = 0
        self.skill_cost_mod = 0
        self.hit_count_mod = 0
        self.priority_stage = 0
        self.skill_power_pct_mod = 0.0
        self.next_attack_power_bonus = 0
        self.next_attack_power_pct = 0.0
        self.poison_stacks = 0
        self.burn_stacks = 0
        self.leech_stacks = 0
        self.freeze_stacks = 0
        self.charging_skill_idx = -1

    def reset_mods(self) -> None:
        """重置所有方向修正（用于变身等特殊场景）"""
        self.atk_up = self.atk_down = 0.0
        self.def_up = self.def_down = 0.0
        self.spatk_up = self.spatk_down = 0.0
        self.spdef_up = self.spdef_down = 0.0
        self.speed_up = self.speed_down = 0.0

    def copy_state(self):
        """复制状态（用于MCTS模拟）"""
        p = Pokemon(
            name=self.name, pokemon_type=self.pokemon_type,
            hp=self.hp, attack=self.attack, defense=self.defense,
            sp_attack=self.sp_attack, sp_defense=self.sp_defense,
            speed=self.speed, ability=self.ability,
            skills=[s.copy() for s in self.skills],
            current_hp=self.current_hp, energy=self.energy,
            status=self.status,
        )
        p.atk_up = self.atk_up
        p.atk_down = self.atk_down
        p.def_up = self.def_up
        p.def_down = self.def_down
        p.spatk_up = self.spatk_up
        p.spatk_down = self.spatk_down
        p.spdef_up = self.spdef_up
        p.spdef_down = self.spdef_down
        p.speed_up = self.speed_up
        p.speed_down = self.speed_down
        p.power_multiplier = self.power_multiplier
        p.life_drain_mod = self.life_drain_mod
        p.skill_power_bonus = self.skill_power_bonus
        p.skill_power_pct_mod = self.skill_power_pct_mod
        p.skill_cost_mod = self.skill_cost_mod
        p.hit_count_mod = self.hit_count_mod
        p.priority_stage = self.priority_stage
        p.next_attack_power_bonus = self.next_attack_power_bonus
        p.next_attack_power_pct = self.next_attack_power_pct
        p.poison_stacks = self.poison_stacks
        p.burn_stacks = self.burn_stacks
        p.frostbite_damage = self.frostbite_damage
        p.leech_stacks = self.leech_stacks
        p.meteor_stacks = self.meteor_stacks
        p.meteor_countdown = self.meteor_countdown
        p.charging_skill_idx = self.charging_skill_idx
        p.freeze_stacks = self.freeze_stacks
        p.cooldowns = dict(self.cooldowns)
        # 新引擎字段
        p.ability_effects = [ae.copy() for ae in self.ability_effects] if self.ability_effects else []
        p.ability_state = dict(self.ability_state)
        return p


@dataclass
class BattleState:
    """战斗状态"""
    team_a: List[Pokemon]
    team_b: List[Pokemon]
    current_a: int = 0
    current_b: int = 0
    turn: int = 1
    weather: Optional[str] = None

    # 魔法值：初始4，精灵倒下-1，降到0则败北
    mp_a: int = 4
    mp_b: int = 4

    # 印记/场效 (全队共享Buff, 不随换人消失)
    # 结构: {"atk": 0.3, "def": 0.2, "poison_mark": 3, ...}
    marks_a: Dict[str, float] = field(default_factory=dict)
    marks_b: Dict[str, float] = field(default_factory=dict)

    # 全队应对计数 (海豹船长特性需要)
    counter_count_a: int = 0
    counter_count_b: int = 0

    # 本回合敌方是否换人 (嘲弄条件增益用)
    switch_this_turn_a: bool = False
    switch_this_turn_b: bool = False
    battle_start_effects_triggered: bool = False

    # 天气持续回合 (由 _h_weather 设置)
    weather_turns: int = 0

    # 沙暴天气下的原始技能能耗备份 (id(skill) -> original_cost)
    sandstorm_original_costs: Dict[int, int] = field(default_factory=dict)

    # 聚能事件日志 (供 server.py 战斗播报使用)
    energy_recharge_log: list = field(default_factory=list)

    # 待处理的换人请求 (脱离/强制换人时暂存，由 server.py 让玩家选择)
    pending_switch_requests: list = field(default_factory=list)

    # 全局技能使用计数 (按队伍分开)
    # 结构: {"a": {"水": 3, "火": 1, "状态": 5, "防御": 2, ...}, "b": {...}}
    skill_use_counts_a: Dict[str, int] = field(default_factory=dict)
    skill_use_counts_b: Dict[str, int] = field(default_factory=dict)

    # 奉献系统 (全队共享、换人保留、无法被清除、buff不被消耗)
    # 结构: {"假寐": 2, "飞断": 1, ...}  值为层数
    devotion_a: Dict[str, int] = field(default_factory=dict)
    devotion_b: Dict[str, int] = field(default_factory=dict)

    # 木桶状态待生效标记
    _barrel_pending_a: bool = False
    _barrel_pending_b: bool = False

    # 迸发系统：记录每只精灵入场后是否已过第一回合
    # key=精灵name, value=入场回合号
    burst_entry_turn_a: Dict[str, int] = field(default_factory=dict)
    burst_entry_turn_b: Dict[str, int] = field(default_factory=dict)

    def _get_devotion(self, team: str) -> Dict[str, int]:
        return self.devotion_a if team == "a" else self.devotion_b

    def get_current(self, team: str) -> Pokemon:
        if team == "a":
            return self.team_a[self.current_a]
        return self.team_b[self.current_b]

    def deep_copy(self) -> 'BattleState':
        bs = BattleState(
            team_a=[p.copy_state() for p in self.team_a],
            team_b=[p.copy_state() for p in self.team_b],
            current_a=self.current_a, current_b=self.current_b,
            turn=self.turn, weather=self.weather,
            mp_a=self.mp_a, mp_b=self.mp_b,
            marks_a=dict(self.marks_a), marks_b=dict(self.marks_b),
            counter_count_a=self.counter_count_a,
            counter_count_b=self.counter_count_b,
            switch_this_turn_a=self.switch_this_turn_a,
            switch_this_turn_b=self.switch_this_turn_b,
            battle_start_effects_triggered=self.battle_start_effects_triggered,
            weather_turns=self.weather_turns,
            sandstorm_original_costs=dict(self.sandstorm_original_costs),
            energy_recharge_log=[],
            pending_switch_requests=[],
            skill_use_counts_a=dict(self.skill_use_counts_a),
            skill_use_counts_b=dict(self.skill_use_counts_b),
            devotion_a=dict(self.devotion_a),
            devotion_b=dict(self.devotion_b),
            _barrel_pending_a=self._barrel_pending_a,
            _barrel_pending_b=self._barrel_pending_b,
            burst_entry_turn_a=dict(self.burst_entry_turn_a),
            burst_entry_turn_b=dict(self.burst_entry_turn_b),
        )
        return bs

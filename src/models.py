"""
洛克王国战斗模拟系统 - 数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum


class StatusType(Enum):
    NORMAL = "normal"
    POISONED = "poisoned"
    BURNED = "burned"
    PARALYZED = "paralyzed"
    FROZEN = "frozen"
    SLEEP = "sleep"
    CONFUSED = "confused"
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
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"


class SkillCategory(Enum):
    PHYSICAL = "物攻"
    MAGICAL = "魔攻"
    DEFENSE = "防御"
    STATUS = "状态"


# 属性克制表
TYPE_CHART: Dict[str, Dict[str, float]] = {
    "normal": {"rock": 0.5, "ghost": 0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 2, "bug": 2, "rock": 0.5, "dragon": 0.5, "steel": 2},
    "water": {"fire": 2, "water": 0.5, "grass": 0.5, "ground": 2, "rock": 2, "dragon": 0.5},
    "electric": {"water": 2, "electric": 0.5, "grass": 0.5, "ground": 0, "flying": 2, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2, "grass": 0.5, "poison": 0.5, "ground": 2, "flying": 0.5, "bug": 0.5, "rock": 2, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 0.5, "ground": 2, "flying": 2, "dragon": 2, "steel": 0.5},
    "fighting": {"normal": 2, "ice": 2, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2, "ghost": 0, "dark": 2, "steel": 2, "fairy": 0.5},
    "poison": {"grass": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0, "fairy": 2},
    "ground": {"fire": 2, "electric": 2, "grass": 0.5, "poison": 2, "flying": 0, "bug": 0.5, "rock": 2, "steel": 2},
    "flying": {"electric": 0.5, "grass": 2, "fighting": 2, "bug": 2, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2, "poison": 2, "psychic": 0.5, "dark": 0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "ghost": 0.5, "psychic": 2, "dark": 2, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2, "ice": 2, "fighting": 0.5, "ground": 0.5, "flying": 2, "bug": 2, "steel": 0.5},
    "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": 0.5},
    "dragon": {"dragon": 2, "steel": 0.5, "fairy": 0},
    "dark": {"fighting": 0.5, "psychic": 2, "ghost": 2, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2, "rock": 2, "steel": 0.5, "fairy": 2},
    "fairy": {"fire": 0.5, "fighting": 2, "poison": 0.5, "dragon": 2, "dark": 2, "steel": 0.5},
}

# 属性映射（中文 -> Type enum）
TYPE_NAME_MAP = {
    "普通系": Type.NORMAL, "火系": Type.FIRE, "水系": Type.WATER,
    "电系": Type.ELECTRIC, "草系": Type.GRASS, "冰系": Type.ICE,
    "武系": Type.FIGHTING, "毒系": Type.POISON, "地系": Type.GROUND,
    "翼系": Type.FLYING, "幻系": Type.PSYCHIC, "虫系": Type.BUG,
    "机械系": Type.STEEL, "幽系": Type.GHOST, "龙系": Type.DRAGON,
    "恶系": Type.DARK, "萌系": Type.FAIRY, "光系": Type.PSYCHIC,
    "岩系": Type.ROCK,
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
    force_switch: bool = False     # 脱离
    agility: bool = False          # 迅捷
    charge: bool = False           # 蓄力

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

    def copy(self):
        return Skill(
            name=self.name, skill_type=self.skill_type, category=self.category,
            power=self.power, energy_cost=self.energy_cost, hit_count=self.hit_count,
            life_drain=self.life_drain, damage_reduction=self.damage_reduction,
            self_heal_hp=self.self_heal_hp, self_heal_energy=self.self_heal_energy,
            steal_energy=self.steal_energy, enemy_lose_energy=self.enemy_lose_energy,
            enemy_energy_cost_up=self.enemy_energy_cost_up, priority_mod=self.priority_mod,
            force_switch=self.force_switch, agility=self.agility, charge=self.charge,
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

    # 百分比属性修正器 (1.0 = +100%, -0.5 = -50%)
    atk_mod: float = 0.0
    def_mod: float = 0.0
    spatk_mod: float = 0.0
    spdef_mod: float = 0.0
    speed_mod: float = 0.0

    # 状态层数
    poison_stacks: int = 0
    burn_stacks: int = 0
    freeze_stacks: int = 0

    # 技能冷却 (index -> cooldown turns remaining)
    cooldowns: Dict[int, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.hp

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0 or self.status == StatusType.FAINTED

    @property
    def can_attack(self) -> bool:
        if self.is_fainted:
            return False
        if self.status in (StatusType.SLEEP, StatusType.FROZEN):
            return False
        return True

    def gain_energy(self, amount: int) -> None:
        """增加能量，不超过上限10"""
        self.energy = min(10, self.energy + amount)

    def effective_atk(self) -> float:
        return self.attack * max(0.1, 1.0 + self.atk_mod)

    def effective_def(self) -> float:
        return self.defense * max(0.1, 1.0 + self.def_mod)

    def effective_spatk(self) -> float:
        return self.sp_attack * max(0.1, 1.0 + self.spatk_mod)

    def effective_spdef(self) -> float:
        return self.sp_defense * max(0.1, 1.0 + self.spdef_mod)

    def effective_speed(self) -> float:
        return self.speed * max(0.1, 1.0 + self.speed_mod)

    def apply_self_buff(self, skill: Skill) -> None:
        """应用技能的自身增益"""
        self.atk_mod += skill.self_atk + skill.self_all_atk
        self.def_mod += skill.self_def + skill.self_all_def
        self.spatk_mod += skill.self_spatk + skill.self_all_atk
        self.spdef_mod += skill.self_spdef + skill.self_all_def
        self.speed_mod += skill.self_speed

    def apply_enemy_debuff(self, skill: Skill) -> None:
        """应用技能的敌方减益"""
        self.atk_mod -= skill.enemy_atk + skill.enemy_all_atk
        self.def_mod -= skill.enemy_def + skill.enemy_all_def
        self.spatk_mod -= skill.enemy_spatk + skill.enemy_all_atk
        self.spdef_mod -= skill.enemy_spdef + skill.enemy_all_def
        self.speed_mod -= skill.enemy_speed

    def reset_mods(self) -> None:
        """重置所有修正"""
        self.atk_mod = self.def_mod = self.spatk_mod = self.spdef_mod = self.speed_mod = 0.0

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
        p.atk_mod = self.atk_mod
        p.def_mod = self.def_mod
        p.spatk_mod = self.spatk_mod
        p.spdef_mod = self.spdef_mod
        p.speed_mod = self.speed_mod
        p.poison_stacks = self.poison_stacks
        p.burn_stacks = self.burn_stacks
        p.freeze_stacks = self.freeze_stacks
        p.cooldowns = dict(self.cooldowns)
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

    def get_current(self, team: str) -> Pokemon:
        if team == "a":
            return self.team_a[self.current_a]
        return self.team_b[self.current_b]

    def deep_copy(self) -> 'BattleState':
        return BattleState(
            team_a=[p.copy_state() for p in self.team_a],
            team_b=[p.copy_state() for p in self.team_b],
            current_a=self.current_a, current_b=self.current_b,
            turn=self.turn, weather=self.weather,
        )

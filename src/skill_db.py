"""
技能数据库 — 从 SQLite 加载技能，效果由 EffectTag 系统驱动

加载优先级（高→低）:
  1. effect_data.SKILL_EFFECTS          (手动精确配置，35 个)
  2. skill_effects_generated.SKILL_EFFECTS_GENERATED  (自动转换，387 个)
  3. 空列表 (无效果，仅数值)
"""
import os
import re
import sqlite3
from typing import Optional, List

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.models import Skill, Type, SkillCategory, TYPE_NAME_MAP, CATEGORY_NAME_MAP

# 魔攻属性类型
SPECIAL_TYPES = {Type.FIRE, Type.WATER, Type.GRASS, Type.ELECTRIC, Type.ICE,
                 Type.PSYCHIC, Type.DRAGON, Type.DARK, Type.FAIRY}

_conn: Optional[sqlite3.Connection] = None
_skill_db: dict = {}
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "nrc.db")

# 属性中文名→Type（含短名）
_TYPE_MAP = {
    "普通": Type.NORMAL, "火": Type.FIRE, "水": Type.WATER, "草": Type.GRASS,
    "电": Type.ELECTRIC, "冰": Type.ICE, "武": Type.FIGHTING, "毒": Type.POISON,
    "地": Type.GROUND, "翼": Type.FLYING, "幻": Type.PSYCHIC, "虫": Type.BUG,
    "幽": Type.GHOST, "龙": Type.DRAGON, "恶": Type.DARK,
    "机械": Type.STEEL, "萌": Type.FAIRY, "光": Type.LIGHT,
    "未知": Type.NORMAL, "—": Type.NORMAL,
}
_TYPE_MAP.update(TYPE_NAME_MAP)

# 分类中文名→SkillCategory
_CAT_MAP = {
    "物理": SkillCategory.PHYSICAL, "魔法": SkillCategory.MAGICAL,
    "防御": SkillCategory.DEFENSE, "状态": SkillCategory.STATUS,
    "物攻": SkillCategory.PHYSICAL, "魔攻": SkillCategory.MAGICAL,
    "变化": SkillCategory.STATUS, "—": SkillCategory.STATUS,
}
_CAT_MAP.update(CATEGORY_NAME_MAP)


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        if not os.path.exists(_DB_PATH):
            raise FileNotFoundError(f"Database not found: {_DB_PATH}")
        _conn = sqlite3.connect(_DB_PATH)
        _conn.row_factory = sqlite3.Row
    return _conn


def load_skills(csv_path: str = None) -> dict:
    """从 SQLite 加载技能数据库，效果由 EffectTag 系统注入。"""
    global _skill_db
    if _skill_db:
        return _skill_db

    # 加载效果配置（手动优先，生成文件兜底）
    try:
        from src.effect_data import SKILL_EFFECTS as MANUAL
    except ImportError:
        MANUAL = {}

    try:
        from src.skill_effects_generated import SKILL_EFFECTS_GENERATED as GENERATED
    except ImportError:
        GENERATED = {}

    # 合并：手动配置覆盖生成配置，过滤生成文件中的空列表
    all_effects = {k: v for k, v in GENERATED.items() if v}
    all_effects.update(MANUAL)

    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM skill")

    for row in c.fetchall():
        name = row["name"]
        element = _TYPE_MAP.get(row["element"], Type.NORMAL)
        category = _CAT_MAP.get(row["category"], SkillCategory.STATUS)
        power = row["power"] or 0
        energy = row["energy_cost"] or 0

        # hit_count 字段（如果DB有）
        try:
            hit_count = int(row["hit_count"] or 1)
        except (IndexError, KeyError):
            hit_count = 1

        # agility 字段（如果DB有）
        try:
            agility = bool(row["agility"])
        except (IndexError, KeyError):
            agility = False

        description = row["description"] or ""
        priority_mod = 0
        match = re.search(r"先手([+-]\d+)", description)
        if match:
            priority_mod = int(match.group(1))

        skill = Skill(
            name=name, skill_type=element, category=category,
            power=power, energy_cost=energy,
            hit_count=hit_count, agility=agility, priority_mod=priority_mod,
        )
        skill._base_energy_cost = energy
        skill.effects = all_effects.get(name, [])

        # 迸发标记：description 中包含"迸发"的技能
        skill.burst = "迸发" in description
        # 奉献标记：description 中包含"受奉献影响"的技能
        skill.devotion_affected = "受奉献影响" in description

        _skill_db[name] = skill

    total = len(_skill_db)
    covered = sum(1 for s in _skill_db.values() if s.effects)
    print(f"[OK] Loaded {total} skills ({covered} with effects, "
          f"{len(MANUAL)} manual + {len(GENERATED)} generated)")
    return _skill_db


def get_skill(name: str) -> Skill:
    """获取技能副本"""
    load_skills()
    if name in _skill_db:
        return _skill_db[name].copy()
    return Skill(name=name, skill_type=Type.NORMAL, category=SkillCategory.PHYSICAL,
                 power=40, energy_cost=2)


def get_all_skills() -> dict:
    """获取所有技能"""
    load_skills()
    return dict(_skill_db)


def get_all_skill_names() -> list:
    """获取所有技能名列表"""
    load_skills()
    return list(_skill_db.keys())


def get_skill_learners(skill_name: str) -> List[str]:
    """获取能学习某技能的精灵列表"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT p.name FROM pokemon p
        JOIN pokemon_skill ps ON ps.pokemon_id = p.id
        JOIN skill s ON ps.skill_id = s.id
        WHERE s.name = ?
    """, (skill_name,))
    return [r[0] for r in c.fetchall()]


def load_ability_effects(ability_str: str) -> list:
    """
    根据精灵的特性字符串返回 AbilityEffect 列表。
    格式: '特性名:描述' 或 '特性名'
    """
    try:
        from src.effect_data import ABILITY_EFFECTS
    except ImportError:
        return []

    name = ability_str.split(":")[0].split("：")[0].strip()
    effects = ABILITY_EFFECTS.get(name, [])

    # 检测空占位特性（SELF_BUFF(atk=0) 等静默无效的配置）
    if effects:
        from src.effect_models import E
        all_noop = all(
            len(ae.effects) == 1
            and ae.effects[0].type == E.SELF_BUFF
            and ae.effects[0].params.get("atk", None) == 0
            and len(ae.effects[0].params) == 1
            for ae in effects
        )
        if all_noop:
            import sys
            print(f"[WARN] 特性 '{name}' 是空占位 (SELF_BUFF atk=0)，对战时无实际效果", file=sys.stderr)

    return effects

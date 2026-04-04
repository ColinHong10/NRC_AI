"""
scripts/generate_skill_effects.py

自动转换器：从数据库 description 字段解析技能效果，批量生成 EffectTag 配置。
已在 effect_data.SKILL_EFFECTS 中手动配置的技能自动跳过。

运行方式:
    python3 scripts/generate_skill_effects.py
"""

import os
import re
import sys
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.models import Skill, Type, SkillCategory, TYPE_NAME_MAP, CATEGORY_NAME_MAP
from src.effect_data import SKILL_EFFECTS as MANUAL_EFFECTS

# Python 保留字（不能作为关键字参数）
_RESERVED = {
    "def", "class", "type", "return", "import", "from", "pass",
    "for", "if", "else", "while", "with", "as", "in", "not",
    "and", "or", "is", "del", "try", "raise", "except", "finally",
    "yield", "lambda", "global", "nonlocal", "assert", "break",
    "continue", "True", "False", "None"
}

_TYPE_MAP = {
    "普通": Type.NORMAL, "火": Type.FIRE, "水": Type.WATER, "草": Type.GRASS,
    "电": Type.ELECTRIC, "冰": Type.ICE, "武": Type.FIGHTING, "毒": Type.POISON,
    "地": Type.GROUND, "翼": Type.FLYING, "幻": Type.PSYCHIC, "虫": Type.BUG,
    "岩": Type.ROCK, "幽": Type.GHOST, "龙": Type.DRAGON, "恶": Type.DARK,
    "机械": Type.STEEL, "萌": Type.FAIRY, "光": Type.PSYCHIC,
    "未知": Type.NORMAL, "—": Type.NORMAL,
}
_TYPE_MAP.update(TYPE_NAME_MAP)

_CAT_MAP = {
    "物理": SkillCategory.PHYSICAL, "魔法": SkillCategory.MAGICAL,
    "防御": SkillCategory.DEFENSE, "状态": SkillCategory.STATUS,
    "物攻": SkillCategory.PHYSICAL, "魔攻": SkillCategory.MAGICAL,
    "变化": SkillCategory.STATUS, "—": SkillCategory.STATUS,
}
_CAT_MAP.update(CATEGORY_NAME_MAP)

SPECIAL_TYPES = {Type.FIRE, Type.WATER, Type.GRASS, Type.ELECTRIC, Type.ICE,
                 Type.PSYCHIC, Type.DRAGON, Type.DARK, Type.FAIRY}


# ── 旧版 parse_effect（仅在此脚本使用）──
def _parse_effect(skill: Skill, desc: str) -> Skill:
    d = desc.replace("，", ",").replace("。", "").replace("：", ":")

    m = re.search(r'(\d+)连击', d)
    if m: skill.hit_count = int(m.group(1))
    m = re.search(r'吸血(\d+)%', d)
    if m: skill.life_drain = int(m.group(1)) / 100.0
    m = re.search(r'减伤(\d+)%', d)
    if m: skill.damage_reduction = int(m.group(1)) / 100.0

    for pattern in [r'回复(\d+)%生命', r'自己回复(\d+)%生命']:
        m = re.search(pattern, d)
        if m: skill.self_heal_hp = int(m.group(1)) / 100.0

    m = re.search(r'回复(\d+)能量', d)
    if m: skill.self_heal_energy = int(m.group(1))
    m = re.search(r'偷取敌方?(\d+)能量', d)
    if m: skill.steal_energy = int(m.group(1))
    m = re.search(r'敌方失去(\d+)能量', d)
    if m: skill.enemy_lose_energy = int(m.group(1))

    if '折返' in d or '脱离' in d: skill.force_switch = True
    if '迅捷' in d: skill.agility = True
    if '蓄力' in d: skill.charge = True

    m = re.search(r'(\d+)层寄生', d)
    if m: skill.leech_stacks = int(m.group(1))
    elif '寄生' in d: skill.leech_stacks = 1

    m = re.search(r'(\d+)层星陨', d)
    if m: skill.meteor_stacks = int(m.group(1))
    elif '星陨' in d: skill.meteor_stacks = 1

    def parse_self_stat(pattern, field):
        mm = re.search(pattern, d)
        if mm: setattr(skill, field, int(mm.group(1)) / 100.0)

    parse_self_stat(r'获得物攻\+(\d+)%', 'self_atk')
    parse_self_stat(r'获得魔攻\+(\d+)%', 'self_spatk')
    parse_self_stat(r'获得物防\+(\d+)%', 'self_def')
    parse_self_stat(r'获得魔防\+(\d+)%', 'self_spdef')

    m = re.search(r'获得速度\+(\d+)', d)
    if m: skill.self_speed = int(m.group(1)) / 100.0
    m = re.search(r'获得速度-(\d+)', d)
    if m: skill.self_speed = -int(m.group(1)) / 100.0

    m = re.search(r'双攻\+(\d+)%', d)
    if m:
        v = int(m.group(1)) / 100.0
        skill.self_atk += v; skill.self_spatk += v
    m = re.search(r'双防\+(\d+)%', d)
    if m:
        v = int(m.group(1)) / 100.0
        skill.self_def += v; skill.self_spdef += v

    def parse_enemy_stat(pattern, field):
        mm = re.search(pattern, d)
        if mm: setattr(skill, field, int(mm.group(1)) / 100.0)

    parse_enemy_stat(r'敌方获得物攻-(\d+)%', 'enemy_atk')
    parse_enemy_stat(r'敌方获得魔攻-(\d+)%', 'enemy_spatk')
    parse_enemy_stat(r'敌方获得物防-(\d+)%', 'enemy_def')
    parse_enemy_stat(r'敌方获得魔防-(\d+)%', 'enemy_spdef')
    parse_enemy_stat(r'敌方获得双攻-(\d+)%', 'enemy_all_atk')
    parse_enemy_stat(r'敌方获得双防-(\d+)%', 'enemy_all_def')

    m = re.search(r'(\d+)层中毒', d)
    if m: skill.poison_stacks = int(m.group(1))
    m = re.search(r'(\d+)层灼烧', d)
    if m: skill.burn_stacks = int(m.group(1))
    m = re.search(r'(\d+)层冻结', d)
    if m: skill.freeze_stacks = int(m.group(1))

    m = re.search(r'敌方获得全技能能耗\+(\d+)', d)
    if m: skill.enemy_energy_cost_up = int(m.group(1))
    m = re.search(r'技能能耗\+(\d+)', d)
    if m and skill.enemy_energy_cost_up == 0:
        skill.enemy_energy_cost_up = int(m.group(1))

    if '应对攻击' in d:
        m = re.search(r'应对攻击.*?吸血(\d+)%', d)
        if m: skill.counter_physical_drain = int(m.group(1)) / 100.0
        m = re.search(r'应对攻击.*?失去(\d+)能量', d)
        if m: skill.counter_physical_energy_drain = int(m.group(1))

    if '应对状态' in d:
        m = re.search(r'应对状态.*?威力.*?(\d+)倍', d)
        if m: skill.counter_status_power_mult = int(m.group(1))
        m = re.search(r'应对状态.*?翻倍', d)
        if m and skill.counter_status_power_mult == 0:
            skill.counter_status_power_mult = 2

    if '应对防御' in d:
        m = re.search(r'应对防御.*?物攻\+(\d+)%', d)
        if m: skill.counter_defense_self_atk = int(m.group(1)) / 100.0

    return skill


def _fmt_T(etype_str: str, parts: dict) -> str:
    """格式化 T(E.XXX, ...) 字符串，自动处理含保留字的键。"""
    reserved = {k: v for k, v in parts.items() if k in _RESERVED}
    normal   = {k: v for k, v in parts.items() if k not in _RESERVED}
    args = [etype_str]
    if reserved:
        dict_repr = "{" + ", ".join(f'"{k}": {v}' for k, v in reserved.items()) + "}"
        args.append(dict_repr)
    for k, v in normal.items():
        args.append(f"{k}={v}")
    return "T(" + ", ".join(args) + ")"


def skill_to_tags(skill) -> list:
    lines = []
    if skill.agility:
        lines.append("T(E.AGILITY)")
    if skill.damage_reduction > 0:
        lines.append(f"T(E.DAMAGE_REDUCTION, pct={round(skill.damage_reduction, 2)})")
    if skill.power > 0:
        lines.append("T(E.DAMAGE)")

    buff = {}
    if skill.self_atk:     buff["atk"]    = round(skill.self_atk,   2)
    if skill.self_def:     buff["def"]    = round(skill.self_def,   2)
    if skill.self_spatk:   buff["spatk"]  = round(skill.self_spatk, 2)
    if skill.self_spdef:   buff["spdef"]  = round(skill.self_spdef, 2)
    if skill.self_speed:   buff["speed"]  = round(skill.self_speed, 2)
    if skill.self_all_atk: buff["all_atk"] = round(skill.self_all_atk, 2)
    if skill.self_all_def: buff["all_def"] = round(skill.self_all_def, 2)
    if buff:
        lines.append(_fmt_T("E.SELF_BUFF", buff))

    debuff = {}
    if skill.enemy_atk:    debuff["atk"]    = round(skill.enemy_atk,   2)
    if skill.enemy_def:    debuff["def"]     = round(skill.enemy_def,   2)
    if skill.enemy_spatk:  debuff["spatk"]   = round(skill.enemy_spatk, 2)
    if skill.enemy_spdef:  debuff["spdef"]   = round(skill.enemy_spdef, 2)
    if skill.enemy_speed:  debuff["speed"]   = round(skill.enemy_speed, 2)
    if skill.enemy_all_atk: debuff["all_atk"] = round(skill.enemy_all_atk, 2)
    if skill.enemy_all_def: debuff["all_def"] = round(skill.enemy_all_def, 2)
    if debuff:
        lines.append(_fmt_T("E.ENEMY_DEBUFF", debuff))

    if skill.self_heal_energy > 0:
        lines.append(f"T(E.HEAL_ENERGY, amount={skill.self_heal_energy})")
    if skill.steal_energy > 0:
        lines.append(f"T(E.STEAL_ENERGY, amount={skill.steal_energy})")
    if skill.enemy_lose_energy > 0:
        lines.append(f"T(E.ENEMY_LOSE_ENERGY, amount={skill.enemy_lose_energy})")
    if skill.self_heal_hp > 0:
        lines.append(f"T(E.HEAL_HP, pct={round(skill.self_heal_hp, 2)})")
    if skill.poison_stacks > 0:
        lines.append(f"T(E.POISON, stacks={skill.poison_stacks})")
    if skill.burn_stacks > 0:
        lines.append(f"T(E.BURN, stacks={skill.burn_stacks})")
    if skill.freeze_stacks > 0:
        lines.append(f"T(E.FREEZE, stacks={skill.freeze_stacks})")
    if skill.leech_stacks > 0:
        lines.append(f"T(E.LEECH, stacks={skill.leech_stacks})")
    if skill.meteor_stacks > 0:
        lines.append(f"T(E.METEOR, stacks={skill.meteor_stacks})")
    if skill.force_switch:
        lines.append("T(E.FORCE_SWITCH)")
    if skill.life_drain > 0:
        lines.append(f"T(E.LIFE_DRAIN, pct={round(skill.life_drain, 2)})")
    if skill.enemy_energy_cost_up > 0:
        lines.append(f"T(E.ENEMY_ENERGY_COST_UP, amount={skill.enemy_energy_cost_up})")

    ca_subs = []
    if skill.counter_physical_drain > 0:
        ca_subs.append(f"T(E.LIFE_DRAIN, pct={round(skill.counter_physical_drain, 2)})")
    if skill.counter_physical_energy_drain > 0:
        ca_subs.append(f"T(E.ENEMY_LOSE_ENERGY, amount={skill.counter_physical_energy_drain})")
    if skill.counter_physical_self_atk > 0:
        ca_subs.append(f"T(E.SELF_BUFF, atk={round(skill.counter_physical_self_atk, 2)})")
    if skill.counter_damage_reflect > 0:
        ca_subs.append("T(E.MIRROR_DAMAGE, source='countered_skill')")
    if ca_subs:
        lines.append(f"on_attack({', '.join(ca_subs)})")

    cs_subs = []
    if skill.counter_status_power_mult > 1:
        cs_subs.append(
            f"T(E.POWER_DYNAMIC, condition='counter', multiplier={skill.counter_status_power_mult}.0)"
        )
    if skill.counter_status_enemy_lose_energy > 0:
        cs_subs.append(
            f"T(E.ENEMY_LOSE_ENERGY, amount={skill.counter_status_enemy_lose_energy})"
        )
    if skill.counter_status_poison_stacks > 0:
        cs_subs.append(f"T(E.POISON, stacks={skill.counter_status_poison_stacks})")
    if cs_subs:
        lines.append(f"on_status({', '.join(cs_subs)})")

    cd_subs = []
    if skill.counter_defense_self_atk > 0:
        cd_subs.append(f"T(E.SELF_BUFF, atk={round(skill.counter_defense_self_atk, 2)})")
    if cd_subs:
        lines.append(f"on_defense({', '.join(cd_subs)})")

    return lines


def main():
    db_path = os.path.join(ROOT, "data", "nrc.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM skill")
    rows = c.fetchall()
    conn.close()

    skip = set(MANUAL_EFFECTS.keys())
    print(f"数据库技能数: {len(rows)}，手动配置跳过: {len(skip)}")

    output_lines = [
        '"""',
        "skill_effects_generated.py — 自动生成，请勿手动编辑",
        "",
        "由 scripts/generate_skill_effects.py 从数据库描述批量转换。",
        '"""',
        "",
        "from src.effect_models import E, EffectTag",
        "from src.effect_data import T, on_attack, on_status, on_defense",
        "",
        "SKILL_EFFECTS_GENERATED = {",
    ]

    converted = 0
    empty = 0

    for row in sorted(rows, key=lambda r: r["name"]):
        name = row["name"]
        if name in skip:
            continue

        element = _TYPE_MAP.get(row["element"], Type.NORMAL)
        category = _CAT_MAP.get(row["category"], SkillCategory.STATUS)
        power = row["power"] or 0
        energy = row["energy_cost"] or 0
        desc = row["description"] or ""

        skill = Skill(
            name=name, skill_type=element, category=category,
            power=power, energy_cost=energy,
        )
        if desc:
            _parse_effect(skill, desc)

        tags = skill_to_tags(skill)
        escaped = name.replace('"', '\\"')

        if not tags:
            output_lines.append(f'    "{escaped}": [],')
            empty += 1
            continue

        if len(tags) == 1:
            output_lines.append(f'    "{escaped}": [{tags[0]}],')
        else:
            output_lines.append(f'    "{escaped}": [')
            for t in tags:
                output_lines.append(f'        {t},')
            output_lines.append(f'    ],')

        converted += 1

    output_lines.append("}")

    out_path = os.path.join(ROOT, "src", "skill_effects_generated.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"\n✓ 生成完毕: {out_path}")
    print(f"  转换: {converted}  空配置: {empty}  跳过(手动): {len(skip)}")
    print(f"  总: {len(rows)}")


if __name__ == "__main__":
    main()

"""
批量根据数据库中的技能 description 生成 EffectTag 映射。

用法:
    py -X utf8 scripts/generate_skill_effects.py
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.effect_data import SKILL_EFFECTS as MANUAL_EFFECTS
from src.models import CATEGORY_NAME_MAP, TYPE_NAME_MAP, Skill, SkillCategory, Type


_RESERVED = {
    "def",
    "class",
    "type",
    "return",
    "import",
    "from",
    "pass",
    "for",
    "if",
    "else",
    "while",
    "with",
    "as",
    "in",
    "not",
    "and",
    "or",
    "is",
    "del",
    "try",
    "raise",
    "except",
    "finally",
    "yield",
    "lambda",
    "global",
    "nonlocal",
    "assert",
    "break",
    "continue",
    "True",
    "False",
    "None",
}

_TYPE_MAP = {
    "普通": Type.NORMAL,
    "火": Type.FIRE,
    "水": Type.WATER,
    "草": Type.GRASS,
    "电": Type.ELECTRIC,
    "冰": Type.ICE,
    "武": Type.FIGHTING,
    "毒": Type.POISON,
    "地": Type.GROUND,
    "翼": Type.FLYING,
    "幻": Type.PSYCHIC,
    "虫": Type.BUG,
    "岩": Type.ROCK,
    "幽": Type.GHOST,
    "龙": Type.DRAGON,
    "恶": Type.DARK,
    "机械": Type.STEEL,
    "萌": Type.FAIRY,
    "光": Type.PSYCHIC,
    "未知": Type.NORMAL,
    "—": Type.NORMAL,
}
_TYPE_MAP.update(TYPE_NAME_MAP)

_CAT_MAP = {
    "物理": SkillCategory.PHYSICAL,
    "魔法": SkillCategory.MAGICAL,
    "防御": SkillCategory.DEFENSE,
    "状态": SkillCategory.STATUS,
    "变化": SkillCategory.STATUS,
    "物攻": SkillCategory.PHYSICAL,
    "魔攻": SkillCategory.MAGICAL,
    "—": SkillCategory.STATUS,
}
_CAT_MAP.update(CATEGORY_NAME_MAP)

_COUNTER_MARKERS = {
    "应对攻击": "on_attack",
    "应对状态": "on_status",
    "应对防御": "on_defense",
}

_STAT_FIELD_MAP = {
    "物攻": "atk",
    "物防": "def",
    "魔攻": "spatk",
    "魔防": "spdef",
    "速度": "speed",
}

_FLOAT_SKILL_FIELDS = {
    "life_drain",
    "damage_reduction",
    "self_heal_hp",
    "self_atk",
    "self_def",
    "self_spatk",
    "self_spdef",
    "self_speed",
    "self_all_atk",
    "self_all_def",
    "enemy_atk",
    "enemy_def",
    "enemy_spatk",
    "enemy_spdef",
    "enemy_speed",
    "enemy_all_atk",
    "enemy_all_def",
}


def _normalize_desc(desc: str) -> str:
    return (
        (desc or "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("：", ":")
        .replace("；", ";")
        .replace("，", ",")
        .replace("。", ".")
        .replace("％", "%")
        .replace("　", "")
        .replace("\n", "")
        .replace("\r", "")
        .replace(" ", "")
        .strip()
    )


def _pct(text: str) -> float:
    return round(int(text) / 100.0, 2)


def _fmt_T(etype_str: str, parts: Dict[str, object] | None = None, **kwargs: object) -> str:
    params = dict(parts or {})
    params.update(kwargs)
    reserved = {k: v for k, v in params.items() if k in _RESERVED}
    normal = {k: v for k, v in params.items() if k not in _RESERVED}
    args = [etype_str]
    if reserved:
        dict_repr = "{" + ", ".join(f'"{k}": {repr(v)}' for k, v in reserved.items()) + "}"
        args.append(dict_repr)
    for key, value in normal.items():
        args.append(f"{key}={repr(value)}")
    return "T(" + ", ".join(args) + ")"


def _add_unique(tags: List[str], tag: str) -> None:
    if tag and tag not in tags:
        tags.append(tag)


def _set_skill_field(skill: Skill, field: str, value: float | int) -> None:
    current = getattr(skill, field)
    if field in _FLOAT_SKILL_FIELDS:
        candidate = round(float(value), 2)
        if current == 0 or abs(candidate) > abs(float(current)):
            setattr(skill, field, candidate)
    else:
        candidate = int(value)
        if current == 0 or abs(candidate) > abs(int(current)):
            setattr(skill, field, candidate)


def _apply_combined_stat(skill: Skill, fields: Sequence[str], value: float) -> None:
    for field in fields:
        _set_skill_field(skill, field, value)


def _extract_counter_clauses(raw_desc: str) -> List[tuple[str, str]]:
    text = raw_desc or ""
    pattern = re.compile(r"(应对攻击|应对状态|应对防御)[:：]")
    matches = list(pattern.finditer(text))
    clauses: List[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        clause = text[start:end].strip("，。；; ")
        if clause:
            clauses.append((match.group(1), clause))
    return clauses


def _parse_basic_skill_fields(skill: Skill, raw_desc: str) -> None:
    desc = _normalize_desc(raw_desc)
    if not desc:
        return

    match = re.search(r"(\d+)连击", desc)
    if match:
        skill.hit_count = int(match.group(1))

    match = re.search(r"(?:并|且)?吸血(\d+)%", desc)
    if (
        match
        and skill.power > 0
        and "获得" not in desc[max(0, match.start() - 3): match.start() + 1]
        and "本次攻击吸血" not in desc
        and "下一次攻击吸血" not in desc
    ):
        skill.life_drain = max(skill.life_drain, _pct(match.group(1)))

    match = re.search(r"减伤(\d+)%", desc)
    if not match:
        match = re.search(r"减免(\d+)%", desc)
    if match:
        skill.damage_reduction = _pct(match.group(1))

    for pattern in (
        r"(?:自己|自身)?恢复(\d+)%生命",
        r"恢复(\d+)%生命",
    ):
        match = re.search(pattern, desc)
        if match:
            skill.self_heal_hp = max(skill.self_heal_hp, _pct(match.group(1)))

    match = re.search(r"(?:自己|自身)?恢复(\d+)能量", desc)
    if not match:
        match = re.search(r"恢复(\d+)能量", desc)
    if match:
        skill.self_heal_energy = max(skill.self_heal_energy, int(match.group(1)))

    match = re.search(r"偷取(?:敌方)?(\d+)点?能量", desc)
    if match:
        skill.steal_energy = max(skill.steal_energy, int(match.group(1)))

    match = re.search(r"敌方失去(\d+)点?能量", desc)
    if match:
        skill.enemy_lose_energy = max(skill.enemy_lose_energy, int(match.group(1)))

    if re.search(r"(?:自己|自身)(?:返场|脱离)", desc) and "回合结束时" not in desc:
        skill.force_switch = True
    if "迅捷" in desc:
        skill.agility = True
    if "蓄力" in desc:
        skill.charge = True

    for status_name, field in (
        ("中毒", "poison_stacks"),
        ("灼烧", "burn_stacks"),
        ("冻结", "freeze_stacks"),
    ):
        match = re.search(rf"(\d+)层{status_name}", desc)
        if match:
            setattr(skill, field, max(getattr(skill, field), int(match.group(1))))

    match = re.search(r"(\d+)层寄生", desc)
    if match:
        skill.leech_stacks = max(skill.leech_stacks, int(match.group(1)))
    elif "寄生" in desc and "寄生种子" not in desc:
        skill.leech_stacks = max(skill.leech_stacks, 1)

    match = re.search(r"(\d+)层星陨", desc)
    if match:
        skill.meteor_stacks = max(skill.meteor_stacks, int(match.group(1)))
    elif "星陨" in desc:
        skill.meteor_stacks = max(skill.meteor_stacks, 1)

    for cn_name, field in (
        ("物攻", "self_atk"),
        ("物防", "self_def"),
        ("魔攻", "self_spatk"),
        ("魔防", "self_spdef"),
    ):
        for pattern in (
            rf"(?:自己|自身)?获得{cn_name}\+(\d+)%",
            rf"提升(?:自己|自身)?(\d+)%{cn_name}",
        ):
            match = re.search(pattern, desc)
            if match:
                _set_skill_field(skill, field, _pct(match.group(1)))

    for cn_name, field in (
        ("物攻", "enemy_atk"),
        ("物防", "enemy_def"),
        ("魔攻", "enemy_spatk"),
        ("魔防", "enemy_spdef"),
        ("速度", "enemy_speed"),
    ):
        for pattern in (
            rf"敌方获得{cn_name}-(\d+)%",
            rf"敌方{cn_name}-(\d+)%",
            rf"降低敌方(\d+)%{cn_name}",
        ):
            match = re.search(pattern, desc)
            if match:
                _set_skill_field(skill, field, _pct(match.group(1)))

    for pattern in (r"(?:自己|自身)?获得速度\+(\d+)", r"(?:自己|自身)?速度\+(\d+)"):
        match = re.search(pattern, desc)
        if match:
            _set_skill_field(skill, "self_speed", _pct(match.group(1)))

    for pattern, fields in (
        (r"(?:自己|自身)?获得(?:物攻和魔攻|双攻)\+(\d+)%", ("self_atk", "self_spatk")),
        (r"(?:自己|自身)?获得(?:物防和魔防|双防)\+(\d+)%", ("self_def", "self_spdef")),
        (r"(?:自己|自身)?获得物攻和物防\+(\d+)%", ("self_atk", "self_def")),
        (r"敌方获得(?:物攻和魔攻|双攻)-(\d+)%", ("enemy_atk", "enemy_spatk")),
        (r"敌方获得(?:物防和魔防|双防)-(\d+)%", ("enemy_def", "enemy_spdef")),
        (r"降低敌方(\d+)%物攻和物防", ("enemy_atk", "enemy_def")),
    ):
        match = re.search(pattern, desc)
        if match:
            _apply_combined_stat(skill, fields, _pct(match.group(1)))

    match = re.search(r"敌方获得全技能能耗\+(\d+)", desc)
    if match:
        skill.enemy_energy_cost_up = max(skill.enemy_energy_cost_up, int(match.group(1)))


def _parse_counter_clause_effects(clause: str) -> List[str]:
    desc = _normalize_desc(clause)
    tags: List[str] = []

    if "打断被应对技能" in desc or "额外造成打断" in desc:
        _add_unique(tags, "T(E.INTERRUPT)")

    match = re.search(r"自己获得(\d+)%吸血", desc)
    if match:
        _add_unique(tags, _fmt_T("E.GRANT_LIFE_DRAIN", pct=_pct(match.group(1))))

    match = re.search(r"本次攻击吸血(\d+)%", desc)
    if match:
        _add_unique(tags, _fmt_T("E.LIFE_DRAIN", pct=_pct(match.group(1))))

    match = re.search(r"(?:自己|自身)?获得全技能能耗-(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="cost", value=-int(match.group(1))))

    match = re.search(r"敌方获得全技能能耗\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="cost", value=int(match.group(1))))

    match = re.search(r"(?:自己|自身)?获得全技能威力\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="power_pct", value=_pct(match.group(1))))

    match = re.search(r"敌方先手-([0-9]+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="priority", value=-int(match.group(1))))

    return tags


def _extra_desc_tags(skill: Skill, raw_desc: str) -> List[str]:
    desc = _normalize_desc(raw_desc)
    tags: List[str] = []

    match = re.search(r"获得(\d+)%吸血", desc)
    if match and "奉献" not in desc and "本次攻击吸血" not in desc:
        _add_unique(tags, _fmt_T("E.GRANT_LIFE_DRAIN", pct=_pct(match.group(1))))

    match = re.search(r"下一次(?:行动|攻击)时.*?(?:攻击技能)?威力\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.NEXT_ATTACK_MOD", power_bonus=int(match.group(1))))
    elif re.search(r"下一次(?:行动|攻击)时.*?威力(?:翻倍|变为2倍)", desc):
        _add_unique(tags, _fmt_T("E.NEXT_ATTACK_MOD", power_pct=1.0))
    else:
        match = re.search(r"下一次(?:行动|攻击)时.*?威力变为(\d+)倍", desc)
        if match:
            _add_unique(tags, _fmt_T("E.NEXT_ATTACK_MOD", power_pct=float(max(0, int(match.group(1)) - 1))))

    match = re.search(r"(?:自己|自身)?获得全技能威力\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="power_pct", value=_pct(match.group(1))))

    match = re.search(r"敌方获得全技能威力-(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="power_pct", value=-_pct(match.group(1))))

    match = re.search(r"(?:自己|自身)?获得全技能能耗-(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="cost", value=-int(match.group(1))))

    match = re.search(r"敌方获得全技能能耗\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="cost", value=int(match.group(1))))

    match = re.search(r"(?:自己|自身)?获得连击数\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="hit_count", value=int(match.group(1))))

    match = re.search(r"敌方获得连击数-(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="hit_count", value=-int(match.group(1))))

    if "驱散敌方所有增益" in desc:
        _add_unique(tags, _fmt_T("E.CLEANSE", target="enemy", mode="buffs"))
    if "驱散自己的减益" in desc or "驱散自身的减益" in desc:
        _add_unique(tags, _fmt_T("E.CLEANSE", target="self", mode="debuffs"))
    if "驱散自己的增益" in desc or "驱散自身的增益" in desc:
        _add_unique(tags, _fmt_T("E.CLEANSE", target="self", mode="buffs"))
    if "驱散敌方所有减益" in desc:
        _add_unique(tags, _fmt_T("E.CLEANSE", target="enemy", mode="debuffs"))

    if (
        re.search(r"(?:自己|自身)(?:返场|脱离)", desc)
        or "随后脱离" in desc
        or "紧急脱离" in desc
    ) and "回合结束时" not in desc:
        _add_unique(tags, "T(E.FORCE_SWITCH)")

    if (
        re.search(r"(?:使)?敌方(?:精灵)?(?:返场|脱离)", desc)
        or "使敌方精灵返场" in desc
    ) and "回合结束时" not in desc:
        _add_unique(tags, "T(E.FORCE_ENEMY_SWITCH)")

    if skill.category == SkillCategory.STATUS and "下一次行动" not in desc:
        match = re.search(r"敌方先手-([0-9]+)", desc)
        if match:
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="priority", value=-int(match.group(1))))
        match = re.search(r"(?:自己|自身)获得先手\+([0-9]+)", desc)
        if match:
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="priority", value=int(match.group(1))))

    for marker, wrapper in _COUNTER_MARKERS.items():
        for current_marker, clause in _extract_counter_clauses(raw_desc):
            if current_marker != marker:
                continue
            for sub_tag in _parse_counter_clause_effects(clause):
                _add_unique(tags, f"{wrapper}({sub_tag})")

    return tags


def skill_to_tags(skill: Skill, raw_desc: str) -> List[str]:
    tags: List[str] = []

    if skill.agility:
        _add_unique(tags, "T(E.AGILITY)")
    if skill.damage_reduction > 0:
        _add_unique(tags, _fmt_T("E.DAMAGE_REDUCTION", pct=round(skill.damage_reduction, 2)))
    if skill.power > 0:
        _add_unique(tags, "T(E.DAMAGE)")

    buff: Dict[str, float] = {}
    if skill.self_atk:
        buff["atk"] = round(skill.self_atk, 2)
    if skill.self_def:
        buff["def"] = round(skill.self_def, 2)
    if skill.self_spatk:
        buff["spatk"] = round(skill.self_spatk, 2)
    if skill.self_spdef:
        buff["spdef"] = round(skill.self_spdef, 2)
    if skill.self_speed:
        buff["speed"] = round(skill.self_speed, 2)
    if skill.self_all_atk:
        buff["all_atk"] = round(skill.self_all_atk, 2)
    if skill.self_all_def:
        buff["all_def"] = round(skill.self_all_def, 2)
    if buff:
        _add_unique(tags, _fmt_T("E.SELF_BUFF", buff))

    debuff: Dict[str, float] = {}
    if skill.enemy_atk:
        debuff["atk"] = round(skill.enemy_atk, 2)
    if skill.enemy_def:
        debuff["def"] = round(skill.enemy_def, 2)
    if skill.enemy_spatk:
        debuff["spatk"] = round(skill.enemy_spatk, 2)
    if skill.enemy_spdef:
        debuff["spdef"] = round(skill.enemy_spdef, 2)
    if skill.enemy_speed:
        debuff["speed"] = round(skill.enemy_speed, 2)
    if skill.enemy_all_atk:
        debuff["all_atk"] = round(skill.enemy_all_atk, 2)
    if skill.enemy_all_def:
        debuff["all_def"] = round(skill.enemy_all_def, 2)
    if debuff:
        _add_unique(tags, _fmt_T("E.ENEMY_DEBUFF", debuff))

    if skill.self_heal_energy > 0:
        _add_unique(tags, _fmt_T("E.HEAL_ENERGY", amount=skill.self_heal_energy))
    if skill.steal_energy > 0:
        _add_unique(tags, _fmt_T("E.STEAL_ENERGY", amount=skill.steal_energy))
    if skill.enemy_lose_energy > 0:
        _add_unique(tags, _fmt_T("E.ENEMY_LOSE_ENERGY", amount=skill.enemy_lose_energy))
    if skill.self_heal_hp > 0:
        _add_unique(tags, _fmt_T("E.HEAL_HP", pct=round(skill.self_heal_hp, 2)))
    if skill.poison_stacks > 0:
        _add_unique(tags, _fmt_T("E.POISON", stacks=skill.poison_stacks))
    if skill.burn_stacks > 0:
        _add_unique(tags, _fmt_T("E.BURN", stacks=skill.burn_stacks))
    if skill.freeze_stacks > 0:
        _add_unique(tags, _fmt_T("E.FREEZE", stacks=skill.freeze_stacks))
    if skill.leech_stacks > 0:
        _add_unique(tags, _fmt_T("E.LEECH", stacks=skill.leech_stacks))
    if skill.meteor_stacks > 0:
        _add_unique(tags, _fmt_T("E.METEOR", stacks=skill.meteor_stacks))
    if skill.force_switch:
        _add_unique(tags, "T(E.FORCE_SWITCH)")
    if skill.life_drain > 0:
        _add_unique(tags, _fmt_T("E.LIFE_DRAIN", pct=round(skill.life_drain, 2)))
    if skill.enemy_energy_cost_up > 0:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="cost", value=skill.enemy_energy_cost_up))

    for tag in _extra_desc_tags(skill, raw_desc):
        _add_unique(tags, tag)

    return tags


def build_skill_from_row(row: sqlite3.Row) -> Skill:
    skill = Skill(
        name=row["name"],
        skill_type=_TYPE_MAP.get(row["element"], Type.NORMAL),
        category=_CAT_MAP.get(row["category"], SkillCategory.STATUS),
        power=row["power"] or 0,
        energy_cost=row["energy_cost"] or 0,
    )
    _parse_basic_skill_fields(skill, row["description"] or "")
    return skill


def tags_for_row(row: sqlite3.Row) -> List[str]:
    skill = build_skill_from_row(row)
    return skill_to_tags(skill, row["description"] or "")


@dataclass
class CoverageStats:
    db_total: int
    manual_in_db: int
    generated_total: int
    generated_nonempty: int
    generated_empty: int
    covered_total: int
    uncovered_total: int


def generate_mapping(rows: Iterable[sqlite3.Row]) -> tuple[Dict[str, List[str]], CoverageStats]:
    rows = list(rows)
    all_names = {row["name"] for row in rows}
    manual_in_db = {name for name in MANUAL_EFFECTS if name in all_names}
    base_mapping = load_committed_generated_mapping()
    mapping: Dict[str, List[str]] = {}

    for row in sorted(rows, key=lambda item: item["name"]):
        name = row["name"]
        if name in manual_in_db:
            continue
        base_tags = list(base_mapping.get(name, []))
        mapping[name] = base_tags if base_tags else tags_for_row(row)

    generated_nonempty = {name for name, tags in mapping.items() if tags}
    covered_total = len(manual_in_db | generated_nonempty)
    stats = CoverageStats(
        db_total=len(all_names),
        manual_in_db=len(manual_in_db),
        generated_total=len(mapping),
        generated_nonempty=len(generated_nonempty),
        generated_empty=len(mapping) - len(generated_nonempty),
        covered_total=covered_total,
        uncovered_total=len(all_names) - covered_total,
    )
    return mapping, stats


def render_generated_file(mapping: Dict[str, List[str]]) -> str:
    lines = [
        '"""',
        "skill_effects_generated.py - 自动生成，请勿手动编辑。",
        "",
        "由 scripts/generate_skill_effects.py 从数据库 description 批量生成。",
        '"""',
        "",
        "from src.effect_models import E, EffectTag",
        "from src.effect_data import T, on_attack, on_status, on_defense",
        "",
        "SKILL_EFFECTS_GENERATED = {",
    ]

    for name in sorted(mapping):
        tags = mapping[name]
        escaped = name.replace('"', '\\"')
        if not tags:
            lines.append(f'    "{escaped}": [],')
            continue
        if len(tags) == 1:
            lines.append(f'    "{escaped}": [{tags[0]}],')
            continue
        lines.append(f'    "{escaped}": [')
        for tag in tags:
            lines.append(f"        {tag},")
        lines.append("    ],")

    lines.append("}")
    return "\n".join(lines) + "\n"


def load_rows() -> List[sqlite3.Row]:
    db_path = os.path.join(ROOT, "data", "nrc.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM skill").fetchall()
    conn.close()
    return rows


def load_committed_generated_mapping() -> Dict[str, List[str]]:
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:src/skill_effects_generated.py"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
    except Exception:
        return {}

    lines = result.stdout.splitlines()
    mapping: Dict[str, List[str]] = {}
    current_name: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        single = re.match(r'^\s+"(?P<name>.*)": \[(?P<body>.*)\],$', line)
        if single:
            name = single.group("name").replace('\\"', '"')
            body = single.group("body").strip()
            mapping[name] = [] if not body else [body]
            current_name = None
            continue

        start = re.match(r'^\s+"(?P<name>.*)": \[$', line)
        if start:
            current_name = start.group("name").replace('\\"', '"')
            mapping[current_name] = []
            continue

        if current_name is not None:
            if re.match(r"^\s+\],$", line):
                current_name = None
                continue
            tag_line = line.strip().rstrip(",")
            if tag_line:
                mapping[current_name].append(tag_line)

    return mapping


def main() -> None:
    rows = load_rows()
    mapping, stats = generate_mapping(rows)
    out_path = os.path.join(ROOT, "src", "skill_effects_generated.py")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(render_generated_file(mapping))

    print(f"[OK] Generated: {out_path}")
    print(
        "coverage "
        f"db_total={stats.db_total} "
        f"manual={stats.manual_in_db} "
        f"generated_nonempty={stats.generated_nonempty} "
        f"generated_empty={stats.generated_empty} "
        f"covered_total={stats.covered_total} "
        f"uncovered_total={stats.uncovered_total}"
    )


if __name__ == "__main__":
    main()

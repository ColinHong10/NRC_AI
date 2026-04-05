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
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

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
    "幽": Type.GHOST,
    "龙": Type.DRAGON,
    "恶": Type.DARK,
    "机械": Type.STEEL,
    "萌": Type.FAIRY,
    "光": Type.LIGHT,
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

_COUNTER_CATEGORY_MAP = {
    "应对攻击": "attack",
    "应对状态": "status",
    "应对防御": "defense",
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

_TIMING_ORDER = ["PRE_USE", "ON_USE", "ON_HIT", "ON_COUNTER", "IF", "POST_USE"]
_TIMING_INDEX = {t: i for i, t in enumerate(_TIMING_ORDER)}

_POST_USE_TYPES = {
    "SELF_KO",
    "PERMANENT_MOD",
    "ENERGY_COST_ACCUMULATE",
    "RESET_SKILL_COST",
    "DRIVE",
    "REPLAY_AGILITY",
    "AGILITY_COST_SHARE",
}


@dataclass
class SEEntry:
    """Intermediate representation of an SE() call in the generated output."""

    timing: str  # "PRE_USE", "ON_USE", "ON_HIT", "ON_COUNTER", "IF", "POST_USE"
    tags: List[str]  # The T(...) strings for this timing
    kwargs: Dict[str, Any] = field(default_factory=dict)


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


def _tag_signature(tag: str) -> str:
    """返回一个用于去重的粗粒度语义签名。"""
    compact = tag.replace(" ", "")

    if "E.WEATHER" in compact:
        weather = None
        m = re.search(r'(?:type[:=]\s*|\"type\":\s*|\{[^\}]*\"type\":\s*)[\'"]?([a-z]+)[\'"]?', compact)
        if m:
            weather = m.group(1)
        turns = None
        m = re.search(r"turns=(\d+)", compact)
        if m:
            turns = m.group(1)
        return f"weather:{weather}:{turns}"

    if "E.ENEMY_ENERGY_COST_UP" in compact:
        m = re.search(r"amount=(\d+)", compact)
        m_filter = re.search(r"filter='([^']+)'", compact)
        m_duration = re.search(r"duration=(\d+)", compact)
        return (
            f"skill_cost_mod:enemy:{m.group(1) if m else None}:"
            f"{m_filter.group(1) if m_filter else 'all'}:"
            f"{m_duration.group(1) if m_duration else 0}"
        )

    if "E.SKILL_MOD" in compact and "stat='cost'" in compact:
        m_target = re.search(r"target='([^']+)'", compact)
        m_value = re.search(r"value=(-?\d+)", compact)
        target = m_target.group(1) if m_target else None
        value = m_value.group(1) if m_value else None
        return f"skill_cost_mod:{target}:{value}"

    return compact


# ---------------------------------------------------------------------------
# Timing classification helpers
# ---------------------------------------------------------------------------

def _get_timing(tag: str) -> str:
    """Determine the SkillTiming bucket for a flat T(...) tag string."""
    m = re.match(r"T\(E\.(\w+)", tag)
    if not m:
        return "ON_USE"
    etype = m.group(1)

    # PRE_USE
    if etype == "ENERGY_COST_DYNAMIC":
        return "PRE_USE"
    if etype in ("SELF_BUFF", "SELF_DEBUFF", "ENEMY_DEBUFF"):
        return "PRE_USE"

    # ON_HIT
    if etype == "LIFE_DRAIN":
        return "ON_HIT"
    if etype == "CONVERT_POISON_TO_MARK" and "on='kill'" in tag:
        return "ON_HIT"

    # POWER_DYNAMIC — some conditions are IF, others stay ON_USE
    if etype == "POWER_DYNAMIC":
        for cond in (
            "first_strike",
            "enemy_switch",
            "prev_status",
            "prev_counter_success",
            "energy_zero_after_use",
        ):
            if f"condition='{cond}'" in tag:
                return "IF"
        # per_poison, enemy_energy_leq, self_missing_hp_step,
        # energy_cost_above_base, counter → stay in ON_USE (or ON_COUNTER)
        return "ON_USE"

    # CONDITIONAL_BUFF
    if etype == "CONDITIONAL_BUFF":
        if "after_use_hp_gt_half" in tag:
            return "POST_USE"
        if "enemy_switch" in tag:
            return "IF"
        return "ON_USE"

    # SKILL_MOD — conditional variants go to IF
    if etype == "SKILL_MOD":
        if "condition='enemy_switch'" in tag:
            return "IF"
        if "condition='self_hp_below'" in tag:
            return "IF"
        return "ON_USE"

    # ENEMY_ENERGY_COST_UP — with duration → POST_USE, else ON_USE
    if etype == "ENEMY_ENERGY_COST_UP":
        if "duration=" in tag:
            return "POST_USE"
        return "ON_USE"

    # Explicit POST_USE types
    if etype in _POST_USE_TYPES:
        return "POST_USE"

    # Default — ON_USE covers DAMAGE, DAMAGE_REDUCTION, AGILITY, statuses, etc.
    return "ON_USE"


def _get_se_kwargs(tag: str, timing: str) -> Dict[str, Any]:
    """Extract SE filter kwargs for tags that need them (IF / certain POST_USE)."""
    if timing not in ("IF", "POST_USE"):
        return {}

    if "condition='first_strike'" in tag:
        return {"first_strike": True}
    if "condition='enemy_switch'" in tag:
        return {"enemy_switch": True}
    if "condition='prev_status'" in tag:
        return {"prev_status": True}
    if "condition='prev_counter_success'" in tag:
        return {"prev_counter_success": True}
    if "condition='energy_zero_after_use'" in tag:
        return {"energy_zero_after": True}
    if "condition='after_use_hp_gt_half'" in tag:
        return {"self_hp_gt": 0.5}
    if "condition='self_hp_below'" in tag:
        m = re.search(r"threshold=([\d.]+)", tag)
        return {"self_hp_below": float(m.group(1)) if m else 0.5}

    return {}


def _transform_tag_for_se(tag: str) -> str:
    """Transform tags that need modification for SE format.

    E.CONDITIONAL_BUFF → unwrap into E.SELF_BUFF with the buff dict expanded
    as keyword arguments.
    """
    if "E.CONDITIONAL_BUFF" not in tag:
        return tag

    m = re.search(r"buff=(\{[^}]+\})", tag)
    if not m:
        return tag

    buff_dict: Dict[str, float] = {}
    for pair in re.finditer(r"'(\w+)':\s*([-\d.]+)", m.group(1)):
        buff_dict[pair.group(1)] = float(pair.group(2))
    if buff_dict:
        return _fmt_T("E.SELF_BUFF", buff_dict)
    return tag


def _categorize_tags(flat_tags: List[str]) -> List[SEEntry]:
    """Bin flat T(...) tag strings into SEEntry groups by timing."""
    bins: Dict[str, List[str]] = {t: [] for t in _TIMING_ORDER}
    special_entries: List[SEEntry] = []

    for tag in flat_tags:
        timing = _get_timing(tag)
        kwargs = _get_se_kwargs(tag, timing)
        transformed = _transform_tag_for_se(tag)

        if kwargs:
            special_entries.append(SEEntry(timing, [transformed], kwargs))
        else:
            bins[timing].append(transformed)

    result: List[SEEntry] = []
    for timing in _TIMING_ORDER:
        if timing == "ON_COUNTER":
            continue  # counter entries handled separately in skill_to_tags
        if bins[timing]:
            result.append(SEEntry(timing, bins[timing], {}))

    # Merge special entries that share the same (timing, kwargs)
    merged: Dict[tuple, SEEntry] = {}
    for entry in special_entries:
        key = (entry.timing, tuple(sorted(entry.kwargs.items())))
        if key in merged:
            for t in entry.tags:
                if t not in merged[key].tags:
                    merged[key].tags.append(t)
        else:
            merged[key] = SEEntry(entry.timing, list(entry.tags), dict(entry.kwargs))
    result.extend(merged.values())

    # Sort by canonical timing order
    result.sort(key=lambda e: _TIMING_INDEX.get(e.timing, 99))
    return result


def _render_se(entry: SEEntry) -> str:
    """Render an SEEntry into an ``SE(SkillTiming.XXX, [...], ...)`` string."""
    tags_str = ", ".join(entry.tags)
    parts = [f"SkillTiming.{entry.timing}", f"[{tags_str}]"]
    for k, v in sorted(entry.kwargs.items()):
        parts.append(f"{k}={repr(v)}")
    return "SE(" + ", ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Skill field helpers (unchanged)
# ---------------------------------------------------------------------------

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


def _strip_counter_clauses(raw_desc: str) -> str:
    text = raw_desc or ""
    pattern = re.compile(r"(应对攻击|应对状态|应对防御)[:：]")
    match = pattern.search(text)
    return text[:match.start()] if match else text


def _parse_basic_skill_fields(skill: Skill, raw_desc: str) -> None:
    desc = _normalize_desc(_strip_counter_clauses(raw_desc))
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
    match = re.search(r"先手([+-]\d+)", desc)
    if match:
        skill.priority_mod = int(match.group(1))

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


def _parse_counter_clause_effects(skill: Skill, clause: str) -> List[str]:
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

    for cn_name, field in (
        ("物攻", "atk"),
        ("物防", "def"),
        ("魔攻", "spatk"),
        ("魔防", "spdef"),
        ("速度", "speed"),
    ):
        for pattern in (
            rf"(?:自己|自身)?获得{cn_name}\+(\d+)%",
            rf"提升(?:自己|自身)?(\d+)%{cn_name}",
        ):
            match = re.search(pattern, desc)
            if match:
                _add_unique(tags, _fmt_T("E.SELF_BUFF", **{field: _pct(match.group(1))}))

    for pattern, params in (
        (r"(?:自己|自身)?获得(?:物攻和魔攻|双攻)\+(\d+)%", ("atk", "spatk")),
        (r"(?:自己|自身)?获得(?:物防和魔防|双防)\+(\d+)%", ("def", "spdef")),
    ):
        match = re.search(pattern, desc)
        if match:
            pct = _pct(match.group(1))
            _add_unique(tags, _fmt_T("E.SELF_BUFF", **{params[0]: pct, params[1]: pct}))

    for cn_name, field in (
        ("物攻", "atk"),
        ("物防", "def"),
        ("魔攻", "spatk"),
        ("魔防", "spdef"),
        ("速度", "speed"),
    ):
        for pattern in (
            rf"敌方获得{cn_name}-(\d+)%",
            rf"敌方{cn_name}-(\d+)%",
            rf"降低敌方(\d+)%{cn_name}",
        ):
            match = re.search(pattern, desc)
            if match:
                _add_unique(tags, _fmt_T("E.ENEMY_DEBUFF", **{field: _pct(match.group(1))}))

    for pattern, params in (
        (r"敌方获得(?:物攻和魔攻|双攻)-(\d+)%", ("atk", "spatk")),
        (r"敌方获得(?:物防和魔防|双防)-(\d+)%", ("def", "spdef")),
        (r"降低敌方(\d+)%物攻和物防", ("atk", "def")),
    ):
        match = re.search(pattern, desc)
        if match:
            pct = _pct(match.group(1))
            _add_unique(tags, _fmt_T("E.ENEMY_DEBUFF", **{params[0]: pct, params[1]: pct}))

    match = re.search(r"(?:自己|自身)?恢复(\d+)%生命", desc) or re.search(r"恢复(\d+)%生命", desc)
    if match:
        _add_unique(tags, _fmt_T("E.HEAL_HP", pct=_pct(match.group(1))))
    elif "恢复" in desc and "%生命" in desc:
        start = desc.find("恢复")
        end = desc.find("%生命", start)
        if start >= 0 and end > start:
            value = desc[start + 2:end]
            if value.isdigit():
                _add_unique(tags, _fmt_T("E.HEAL_HP", pct=_pct(value)))

    match = re.search(r"(?:自己|自身)?恢复(\d+)能量", desc) or re.search(r"恢复(\d+)能量", desc)
    if match:
        _add_unique(tags, _fmt_T("E.HEAL_ENERGY", amount=int(match.group(1))))

    if (
        re.search(r"(?:自己|自身)(?:返场|脱离)", desc)
        or "随后脱离" in desc
        or "紧急脱离" in desc
    ) and "回合结束" not in desc:
        _add_unique(tags, "T(E.FORCE_SWITCH)")

    if (
        re.search(r"(?:使)?敌方(?:精灵)?(?:返场|脱离)", desc)
        or "使敌方精灵返场" in desc
    ) and "回合结束" not in desc:
        _add_unique(tags, "T(E.FORCE_ENEMY_SWITCH)")

    match = re.search(r"敌方获得全攻击技能能耗\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.ENEMY_ENERGY_COST_UP", amount=int(match.group(1)), filter="attack"))

    match = re.search(r"敌方获得全技能能耗\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.ENEMY_ENERGY_COST_UP", amount=int(match.group(1)), filter="all"))

    if re.search(r"本次技能威力(?:翻倍|变为2倍)", desc):
        _add_unique(tags, _fmt_T("E.POWER_DYNAMIC", condition="counter", multiplier=2.0))
    else:
        match = re.search(r"本次技能威力变为(\d+)倍", desc)
        if match:
            _add_unique(tags, _fmt_T("E.POWER_DYNAMIC", condition="counter", multiplier=float(match.group(1))))

    if "若敌方本回合替换精灵" not in desc:
        match = re.search(r"本次技能连击数\+(\d+)", desc)
        if match:
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count", value=int(match.group(1))))
        elif re.search(r"本次技能连击数翻倍", desc):
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count_mult", value=2.0))
        else:
            match = re.search(r"本次技能连击数变为(\d+)倍", desc)
            if match:
                _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count_mult", value=float(match.group(1))))

    if "若敌方本回合替换精灵" in desc and "3连击" in desc:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count", value=2))

    match = re.search(r"改为速度\+(\d+)", desc)
    if match:
        desired = _pct(match.group(1))
        delta = round(desired - skill.self_speed, 2)
        if delta > 0:
            _add_unique(tags, _fmt_T("E.SELF_BUFF", speed=delta))

    match = re.search(r"改为(?:能耗|全技能能耗)\+(\d+)", desc)
    if match:
        desired = int(match.group(1))
        delta = desired - skill.enemy_energy_cost_up
        if delta > 0:
            _add_unique(tags, _fmt_T("E.ENEMY_ENERGY_COST_UP", amount=delta, filter="all"))

    return tags


def _parse_weather_tags(desc: str) -> List[str]:
    tags: List[str] = []
    if "放晴" in desc:
        return tags

    weather_rules = (
        (r"(?:将|使|令|把)?天气(?:变为|改为|设置为|设为)?(?:雨天|下雨)", ("rain", 8)),
        (r"(?:将|使|令|把)?天气(?:变为|改为|设置为|设为)?(?:沙暴|沙尘暴|风沙)", ("sandstorm", 8)),
        (r"(?:将|使|令|把)?天气(?:变为|改为|设置为|设为)?(?:暴风雪|雪天|下雪)", ("snow", 8)),
    )
    for pattern, (weather_type, turns) in weather_rules:
        if re.search(pattern, desc):
            _add_unique(tags, _fmt_T("E.WEATHER", type=weather_type, turns=turns))
            break
    return tags


def _extra_desc_tags(skill: Skill, raw_desc: str) -> List[str]:
    """Return flat T(...) tag strings from the skill description.

    NOTE: counter-clause effects (应对攻击/应对状态/应对防御) are **not** included
    here.  They are handled separately in ``skill_to_tags()`` as ``SEEntry``
    objects with ``timing="ON_COUNTER"``.
    """
    desc = _normalize_desc(_strip_counter_clauses(raw_desc))
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

    for pattern, target, stat, value_sign in (
        (r"(?:自己|自身)?获得技能威力\+(\d+)", "self", "power", 1),
        (r"敌方获得技能威力-(\d+)", "enemy", "power", -1),
        (r"(?:自己|自身)?获得技能能耗-(\d+)", "self", "cost", -1),
        (r"敌方获得技能能耗\+(\d+)", "enemy", "cost", 1),
    ):
        match = re.search(pattern, desc)
        if match:
            value = int(match.group(1)) * value_sign
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target=target, stat=stat, value=value))

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

    for pattern, params in (
        (
            r"敌方本回合使用的技能能耗\+(\d+),?持续(\d+)回合",
            {"filter": "used_skill"},
        ),
        (
            r"敌方获得全攻击技能能耗\+(\d+),?持续(\d+)回合",
            {"filter": "attack"},
        ),
        (
            r"敌方除本回合使用的技能,?其他技能能耗\+(\d+),?持续(\d+)回合",
            {"filter": "other_skills"},
        ),
    ):
        match = re.search(pattern, desc)
        if match:
            _add_unique(
                tags,
                _fmt_T(
                    "E.ENEMY_ENERGY_COST_UP",
                    amount=int(match.group(1)),
                    duration=int(match.group(2)),
                    filter=params["filter"],
                ),
            )

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
    ) and "回合结束" not in desc:
        _add_unique(tags, "T(E.FORCE_SWITCH)")

    if (
        re.search(r"(?:使)?敌方(?:精灵)?(?:返场|脱离)", desc)
        or "使敌方精灵返场" in desc
    ) and "回合结束" not in desc:
        _add_unique(tags, "T(E.FORCE_ENEMY_SWITCH)")

    for weather_tag in _parse_weather_tags(desc):
        _add_unique(tags, weather_tag)

    if skill.category == SkillCategory.STATUS and "下一次行动" not in desc:
        match = re.search(r"敌方先手-([0-9]+)", desc)
        if match:
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="enemy", stat="priority", value=-int(match.group(1))))
        match = re.search(r"(?:自己|自身)获得先手\+([0-9]+)", desc)
        if match:
            _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="priority", value=int(match.group(1))))

    for pattern, kwargs in (
        (r"若敌方本回合替换精灵,?本次技能威力\+(\d+)", {"condition": "enemy_switch", "bonus_key": "bonus"}),
        (r"若上回合使用状态技能,?本次技能威力\+(\d+)", {"condition": "prev_status", "bonus_key": "bonus"}),
        (r"若上回合应对成功,?本次技能威力\+(\d+)", {"condition": "prev_counter_success", "bonus_key": "bonus"}),
        (r"释放后若能量耗尽,?本次攻击威力\+(\d+)", {"condition": "energy_zero_after_use", "bonus_key": "bonus"}),
    ):
        match = re.search(pattern, desc)
        if match:
            _add_unique(tags, _fmt_T("E.POWER_DYNAMIC", condition=kwargs["condition"], **{kwargs["bonus_key"]: int(match.group(1))}))

    match = re.search(r"若敌方本回合替换精灵,?本次技能连击数\+(\d+)", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count", value=int(match.group(1)), condition="enemy_switch"))

    match = re.search(r"若敌方本回合替换精灵,?本次技能连击数翻倍", desc)
    if match:
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="current_hit_count_mult", value=2.0, condition="enemy_switch"))

    match = re.search(r"若敌方能量小于等于(\d+),?造成(\d+)倍伤害", desc)
    if match:
        _add_unique(
            tags,
            _fmt_T(
                "E.POWER_DYNAMIC",
                condition="enemy_energy_leq",
                threshold=int(match.group(1)),
                multiplier=float(match.group(2)),
            ),
        )

    match = re.search(r"本技能能耗每\+1,?威力\+(\d+)", desc)
    if match:
        _add_unique(
            tags,
            _fmt_T(
                "E.POWER_DYNAMIC",
                condition="energy_cost_above_base",
                base_cost=skill.energy_cost,
                bonus_per_step=int(match.group(1)),
            ),
        )

    match = re.search(r"(?:自己)?每失去(\d+)%生命,?本次技能威力([+-])(\d+)", desc)
    if match:
        step_pct = _pct(match.group(1))
        sign = -1 if match.group(2) == "-" else 1
        bonus_per_step = sign * int(match.group(3))
        _add_unique(
            tags,
            _fmt_T(
                "E.POWER_DYNAMIC",
                condition="self_missing_hp_step",
                step_pct=step_pct,
                bonus_per_step=bonus_per_step,
            ),
        )

    match = re.search(r"若生命高于(\d+)%.*?使用后自己获得双攻([+-])(\d+)%", desc)
    if match:
        sign = -1 if match.group(2) == "-" else 1
        pct = sign * _pct(match.group(3))
        _add_unique(
            tags,
            _fmt_T(
                "E.CONDITIONAL_BUFF",
                condition="after_use_hp_gt_half",
                buff={"atk": pct, "spatk": pct},
            ),
        )

    if "使用后消耗全部生命" in desc:
        _add_unique(tags, _fmt_T("E.SELF_KO"))

    match = re.search(r"每次使用后,?本技能威力永久([+-])(\d+)", desc)
    if match:
        delta = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
        _add_unique(tags, _fmt_T("E.PERMANENT_MOD", target="power", delta=delta, trigger="per_use"))

    match = re.search(r"每次使用后,?本技能连击数永久([+-])(\d+)", desc)
    if match:
        delta = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
        _add_unique(tags, _fmt_T("E.PERMANENT_MOD", target="hit_count", delta=delta, trigger="per_use"))

    match = re.search(r"若(?:自己|自身)?(?:的)?生命低于(\d+)%,?本次技能连击数\+(\d+)", desc)
    if match:
        threshold = _pct(match.group(1))
        _add_unique(
            tags,
            _fmt_T(
                "E.SKILL_MOD",
                target="self",
                stat="current_hit_count",
                value=int(match.group(2)),
                condition="self_hp_below",
                threshold=threshold,
            ),
        )

    match = re.search(r"每次使用后,?本技能能耗永久([+-])(\d+)", desc)
    if match:
        delta = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
        _add_unique(tags, _fmt_T("E.PERMANENT_MOD", target="cost", delta=delta, trigger="per_use"))

    match = re.search(r"回合结束时,?本技能能耗永久([+-])(\d+)", desc)
    if match:
        delta = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
        _add_unique(tags, _fmt_T("E.PERMANENT_MOD", target="cost", delta=delta, trigger="per_use"))

    match = re.search(r"每次应对后本技能能耗([+-])(\d+)", desc)
    if match:
        delta = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
        _add_unique(tags, _fmt_T("E.PERMANENT_MOD", target="cost", delta=delta, trigger="per_counter"))

    if "使用后能耗重置" in desc:
        _add_unique(tags, _fmt_T("E.RESET_SKILL_COST", when="post_use"))

    if skill.name == "气沉丹田":
        _add_unique(tags, _fmt_T("E.HEAL_HP", pct=0.6))

    # NOTE: counter clauses are handled in skill_to_tags() directly as SEEntry objects.

    return tags


def skill_to_tags(skill: Skill, raw_desc: str) -> List[SEEntry]:
    """Convert a skill's parsed fields + description into a list of SEEntry objects."""
    tags: List[str] = []
    desc = _normalize_desc(raw_desc)

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

    # 无伤害的状态/防御技能中，"3连击"更接近对后续出招的连击增益，而不是技能自身多段。
    if (
        skill.power <= 0
        and skill.category in (SkillCategory.STATUS, SkillCategory.DEFENSE)
        and skill.hit_count > 1
        and "连击数+" not in desc
    ):
        _add_unique(tags, _fmt_T("E.SKILL_MOD", target="self", stat="hit_count", value=skill.hit_count))

    for tag in _extra_desc_tags(skill, raw_desc):
        _add_unique(tags, tag)

    # --- Categorize flat tags into SE timing bins ---
    se_list = _categorize_tags(tags)

    # --- Build counter SEEntry objects from 应对 clauses ---
    counter_entries: List[SEEntry] = []
    for current_marker, clause in _extract_counter_clauses(raw_desc):
        category = _COUNTER_CATEGORY_MAP[current_marker]
        sub_tags = _parse_counter_clause_effects(skill, clause)
        counter_entries.append(SEEntry("ON_COUNTER", sub_tags, {"category": category}))

    if counter_entries:
        # Insert counter entries after ON_HIT and before IF
        insert_idx = 0
        for i, entry in enumerate(se_list):
            if _TIMING_INDEX.get(entry.timing, 99) < _TIMING_INDEX["ON_COUNTER"]:
                insert_idx = i + 1
        for entry in counter_entries:
            se_list.insert(insert_idx, entry)
            insert_idx += 1

    return se_list


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


def tags_for_row(row: sqlite3.Row) -> List[SEEntry]:
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


def generate_mapping(rows: Iterable[sqlite3.Row]) -> tuple[Dict[str, List[SEEntry]], CoverageStats]:
    rows = list(rows)
    all_names = {row["name"] for row in rows}
    manual_in_db = {name for name in MANUAL_EFFECTS if name in all_names}
    base_mapping = load_committed_generated_mapping()
    mapping: Dict[str, List[SEEntry]] = {}

    for row in sorted(rows, key=lambda item: item["name"]):
        name = row["name"]
        if name in manual_in_db:
            continue
        parsed_se = tags_for_row(row)
        if parsed_se:
            mapping[name] = parsed_se
            continue
        # Fallback: wrap raw base tags (old format) in a single ON_USE entry
        base_tags = list(base_mapping.get(name, []))
        if base_tags:
            mapping[name] = [SEEntry("ON_USE", base_tags, {})]
        else:
            mapping[name] = []

    generated_nonempty = {name for name, se_list in mapping.items() if se_list}
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


def render_generated_file(mapping: Dict[str, List[SEEntry]]) -> str:
    lines = [
        '"""',
        "skill_effects_generated.py - 自动生成，请勿手动编辑。",
        "",
        "由 scripts/generate_skill_effects.py 从数据库 description 批量生成。",
        '"""',
        "",
        "from src.effect_models import E, EffectTag, SkillTiming",
        "from src.effect_data import T, SE",
        "",
        "SKILL_EFFECTS_GENERATED = {",
    ]

    for name in sorted(mapping):
        se_list = mapping[name]
        escaped = name.replace('"', '\\"')
        if not se_list:
            lines.append(f'    "{escaped}": [],')
            continue

        rendered = [_render_se(entry) for entry in se_list]
        if len(rendered) == 1:
            lines.append(f'    "{escaped}": [{rendered[0]}],')
            continue
        lines.append(f'    "{escaped}": [')
        for se_str in rendered:
            lines.append(f"        {se_str},")
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

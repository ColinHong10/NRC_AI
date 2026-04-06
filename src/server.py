"""
洛克王国战斗模拟系统 - Web 图形界面后端 (FastAPI + WebSocket)
"""

import sys
import os
import json
import asyncio
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from src.skill_db import load_skills
from src.models import BattleState, StatusType
from src.effect_models import E
from src.battle import (
    TeamBuilder, execute_full_turn, check_winner,
    auto_switch, get_actions
)
from src.mcts import MCTS, EXPERIENCE_A, EXPERIENCE_B

app = FastAPI()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

_db_loaded = False

def _ensure_loaded():
    global _db_loaded
    if not _db_loaded:
        load_skills()
        from src.pokemon_db import load_pokemon_db
        load_pokemon_db()
        _db_loaded = True


def _pct_text(value: float) -> str:
    """将比例值转成更适合 UI 展示的百分比文本。"""
    if value == int(value):
        return f"{int(value)}%"
    return f"{value:.0f}%"


def _format_buff_parts(params: dict, prefix: str) -> str:
    parts = []
    for key, label in [
        ("atk", "物攻"),
        ("def", "物防"),
        ("spatk", "魔攻"),
        ("spdef", "魔防"),
        ("speed", "速度"),
    ]:
        if key in params:
            parts.append(f"{label}{prefix}{_pct_text(params[key] * 100)}")
    if "all_atk" in params:
        parts.append(f"双攻{prefix}{_pct_text(params['all_atk'] * 100)}")
    if "all_def" in params:
        parts.append(f"双防{prefix}{_pct_text(params['all_def'] * 100)}")
    return "，".join(parts)


def _effect_tag_text(tag) -> str:
    """把 EffectTag 翻译成前端更易读的短文本。"""
    params = getattr(tag, "params", {}) or {}
    t = getattr(tag, "type", None)

    if t == E.DAMAGE:
        return "造成伤害"
    if t == E.HEAL_HP:
        return f"回复{_pct_text(params.get('pct', 0) * 100)}HP"
    if t == E.HEAL_ENERGY:
        return f"回能+{params.get('amount', 1)}"
    if t == E.STEAL_ENERGY:
        return f"偷能+{params.get('amount', 1)}"
    if t == E.ENEMY_LOSE_ENERGY:
        return f"敌方失能-{params.get('amount', 1)}"
    if t == E.LIFE_DRAIN:
        return f"吸血{_pct_text(params.get('pct', 0) * 100)}"
    if t == E.SELF_BUFF:
        detail = _format_buff_parts(params, "+")
        return f"自增益{('：' + detail) if detail else ''}"
    if t == E.ENEMY_DEBUFF:
        detail = _format_buff_parts(params, "-")
        return f"敌减益{('：' + detail) if detail else ''}"
    if t == E.POISON:
        return f"中毒×{params.get('stacks', 1)}"
    if t == E.BURN:
        return f"灼烧×{params.get('stacks', 1)}"
    if t == E.FREEZE:
        return f"冻结×{params.get('stacks', 1)}"
    if t == E.LEECH:
        return f"寄生×{params.get('stacks', 1)}"
    if t == E.METEOR:
        return f"星陨×{params.get('stacks', 1)}"
    if t == E.POISON_MARK:
        return f"中毒印记×{params.get('stacks', 1)}"
    if t == E.MOISTURE_MARK:
        return f"湿润印记×{params.get('stacks', 1)}"
    if t == E.DRAGON_MARK:
        return f"龙噬印记×{params.get('stacks', 1)}"
    if t == E.WIND_MARK:
        return f"风起印记×{params.get('stacks', 1)}"
    if t == E.CHARGE_MARK:
        return f"蓄电印记×{params.get('stacks', 1)}"
    if t == E.SOLAR_MARK:
        return f"光合印记×{params.get('stacks', 1)}"
    if t == E.ATTACK_MARK:
        return f"攻击印记×{params.get('stacks', 1)}"
    if t == E.SLOW_MARK:
        return f"减速印记×{params.get('stacks', 1)}"
    if t == E.SLUGGISH_MARK:
        return f"迟缓印记×{params.get('stacks', 1)}"
    if t == E.SPIRIT_MARK:
        return f"降灵印记×{params.get('stacks', 1)}"
    if t == E.METEOR_MARK:
        return f"星陨印记×{params.get('stacks', 1)}"
    if t == E.THORN_MARK:
        return f"荆刺印记×{params.get('stacks', 1)}"
    if t == E.DISPEL_ENEMY_MARKS:
        return "驱散敌方印记"
    if t == E.CONVERT_MARKS_TO_BURN:
        return f"印记→灼烧×{params.get('ratio', 3)}"
    if t == E.DISPEL_MARKS_TO_BURN:
        return f"驱散印记→灼烧×{params.get('burn_per_mark', 5)}"
    if t == E.CONSUME_MARKS_HEAL:
        return "食腐(驱散回血)"
    if t == E.MARKS_TO_METEOR:
        return "印记→星陨"
    if t == E.STEAL_MARKS:
        return "偷取印记"
    if t == E.ENERGY_COST_PER_ENEMY_MARK:
        return "印记减能耗"
    if t == E.DAMAGE_REDUCTION:
        return f"减伤{_pct_text(params.get('pct', 0) * 100)}"
    if t == E.FORCE_SWITCH:
        return "强制换人"
    if t == E.FORCE_ENEMY_SWITCH:
        return "逼退对手"
    if t == E.AGILITY:
        return "先制"
    if t == E.INTERRUPT:
        return "打断"
    if t == E.POWER_DYNAMIC:
        condition = params.get("condition", "")
        if condition == "first_strike":
            return f"先手威力+{_pct_text(params.get('bonus_pct', 0) * 100)}"
        if condition == "per_poison":
            return f"每层中毒增威{params.get('bonus_per_stack', 0)}"
        if condition == "counter":
            return f"应对威力×{params.get('multiplier', 1.0)}"
        return "动态威力"
    if t == E.ENERGY_COST_DYNAMIC:
        return f"动态减耗：每层减{params.get('reduce', 0)}"
    if t == E.PERMANENT_MOD:
        target = params.get("target", "")
        delta = params.get("delta", 0)
        if target == "cost":
            return f"永久能耗{delta:+d}"
        if target == "power":
            return f"永久威力{delta:+d}"
        return "永久修正"
    if t == E.POSITION_BUFF:
        positions = params.get("positions", [])
        return f"位置增益{positions}"
    if t == E.DRIVE:
        return f"传动{params.get('value', 1)}"
    if t == E.PASSIVE_ENERGY_REDUCE:
        return f"连带减耗-{params.get('reduce', 0)}"
    if t == E.REPLAY_AGILITY:
        return "重复先制"
    if t == E.AGILITY_COST_SHARE:
        return f"先制分摊/{params.get('divisor', 2)}"
    if t == E.ENERGY_COST_ACCUMULATE:
        return f"每次能耗+{params.get('delta', 1)}"
    if t == E.ENEMY_ENERGY_COST_UP:
        return f"敌方能耗+{params.get('amount', 0)}"
    if t == E.MIRROR_DAMAGE:
        return "反弹原始伤害"
    if t == E.CONVERT_BUFF_TO_POISON:
        return "增益转中毒"
    if t == E.CONVERT_POISON_TO_MARK:
        return "中毒转印记"
    if t == E.DISPEL_MARKS:
        return "驱散印记"
    if t == E.CONDITIONAL_BUFF:
        return "条件增益"
    # Legacy COUNTER_* tags (保留兼容)
    if t == E.COUNTER_ATTACK:
        base = "应对攻击"
        subs = getattr(tag, "sub_effects", None) or []
        if subs:
            sub_text = "，".join(_effect_tag_text(sub) for sub in subs)
            return f"{base}：{sub_text}" if sub_text else base
        return base
    if t == E.COUNTER_STATUS:
        base = "应对状态"
        subs = getattr(tag, "sub_effects", None) or []
        if subs:
            sub_text = "，".join(_effect_tag_text(sub) for sub in subs)
            return f"{base}：{sub_text}" if sub_text else base
        return base
    if t == E.COUNTER_DEFENSE:
        base = "应对防御"
        subs = getattr(tag, "sub_effects", None) or []
        if subs:
            sub_text = "，".join(_effect_tag_text(sub) for sub in subs)
            return f"{base}：{sub_text}" if sub_text else base
        return base
    if t == E.WEATHER:
        return f"天气：{params.get('type', 'unknown')}"
    if t == E.ABILITY_COMPUTE:
        return f"特性计算：{params.get('action', '')}"
    if t == E.ABILITY_INCREMENT_COUNTER:
        return "特性计数+1"
    if t == E.TRANSFER_MODS:
        return "离场传递增益"
    if t == E.BURN_NO_DECAY:
        return "灼烧不衰减"
    return getattr(t, "name", "未知效果")


def _skill_effect_display(skill) -> dict:
    """生成前端展示用的技能效果摘要。"""
    from src.effect_models import SkillEffect as _SE, SkillTiming as _ST
    tags = []
    details = []
    if getattr(skill, "effects", None):
        for item in skill.effects:
            if isinstance(item, _SE):
                # SE 格式: 展示每个 EffectTag
                prefix = ""
                if item.timing == _ST.ON_COUNTER:
                    cat = item.filter.get("category", "")
                    cat_name = {"attack": "攻击", "status": "状态", "defense": "防御"}.get(cat, cat)
                    prefix = f"应对{cat_name}："
                for tag in item.effects:
                    text = _effect_tag_text(tag)
                    full = f"{prefix}{text}" if prefix else text
                    details.append(full)
                    tags.append(full.split("：", 1)[0] if prefix else text.split("：", 1)[0])
                if not item.effects and prefix:
                    details.append(prefix.rstrip("："))
                    tags.append(prefix.rstrip("："))
            else:
                text = _effect_tag_text(item)
                details.append(text)
                tags.append(text.split("：", 1)[0])

    if skill.life_drain > 0:
        tags.append(f"吸血{int(skill.life_drain * 100)}%")
    if skill.damage_reduction > 0:
        tags.append(f"减伤{int(skill.damage_reduction * 100)}%")
    if skill.self_heal_hp > 0:
        tags.append(f"回HP{int(skill.self_heal_hp * 100)}%")
    if skill.self_heal_energy > 0:
        tags.append(f"回能+{skill.self_heal_energy}")
    if skill.poison_stacks > 0:
        tags.append(f"中毒×{skill.poison_stacks}")
    if skill.burn_stacks > 0:
        tags.append(f"灼烧×{skill.burn_stacks}")
    if skill.freeze_stacks > 0:
        tags.append(f"冻结×{skill.freeze_stacks}")
    if skill.leech_stacks > 0:
        tags.append(f"寄生×{skill.leech_stacks}")
    if skill.meteor_stacks > 0:
        tags.append(f"星陨×{skill.meteor_stacks}")
    if skill.hit_count > 1:
        tags.append(f"{skill.hit_count}连击")
    if skill.force_switch:
        tags.append("强制换人")
    if skill.agility:
        tags.append("先制")
    if skill.charge:
        tags.append("蓄力")
    if skill.priority_mod > 0:
        tags.append("先手")
    if skill.is_mark:
        tags.append("印记")

    tags = list(dict.fromkeys([t for t in tags if t]))
    details = list(dict.fromkeys([d for d in details if d]))
    return {
        "tags": tags,
        "details": details,
        "summary": "；".join(details) if details else "",
        "has_effects": bool(details),
    }


# ═══════════════════════════════════════
# 精准战报：执行前后状态快照 + diff
# ═══════════════════════════════════════

def _snapshot(state: BattleState) -> dict:
    """记录战斗关键数值快照，用于 diff 生成战报"""
    snap = {
        "mp_a": state.mp_a, "mp_b": state.mp_b,
        "current_a": state.current_a, "current_b": state.current_b,
    }
    for team_key, team_list in [("a", state.team_a), ("b", state.team_b)]:
        for i, p in enumerate(team_list):
            snap[f"{team_key}_{i}_hp"]       = max(0, p.current_hp)
            snap[f"{team_key}_{i}_energy"]   = p.energy
            snap[f"{team_key}_{i}_fainted"]  = p.is_fainted
            snap[f"{team_key}_{i}_poison"]   = p.poison_stacks
            snap[f"{team_key}_{i}_burn"]     = p.burn_stacks
            snap[f"{team_key}_{i}_leech"]    = p.leech_stacks
            snap[f"{team_key}_{i}_frost"]    = p.frostbite_damage
            snap[f"{team_key}_{i}_meteor"]   = p.meteor_stacks
            snap[f"{team_key}_{i}_atk_mod"]  = round((p.atk_up - p.atk_down) * 100)
            snap[f"{team_key}_{i}_def_mod"]  = round((p.def_up - p.def_down) * 100)
    return snap


def _diff_to_logs(before: dict, after: dict, state: BattleState) -> List[str]:
    """比对快照，生成详细战报日志"""
    logs = []

    def pname(team, idx):
        team_list = state.team_a if team == "a" else state.team_b
        return team_list[idx].name

    def side_label(team):
        return "🧑你方" if team == "a" else "🤖AI方"

    n = len(state.team_a)

    for team in ["a", "b"]:
        for i in range(n):
            label = side_label(team)
            name  = pname(team, i)
            max_hp = (state.team_a if team == "a" else state.team_b)[i].hp

            hp_before = before.get(f"{team}_{i}_hp", 0)
            hp_after  = after.get(f"{team}_{i}_hp", 0)
            dmg = hp_before - hp_after
            if dmg > 0:
                logs.append(
                    f"  💥 {label} {name} 受到 {dmg} 伤害 → 剩余 HP {hp_after}/{max_hp}"
                )
            elif dmg < 0:
                logs.append(
                    f"  💚 {label} {name} 回复 {-dmg} HP → {hp_after}/{max_hp}"
                )

            # 倒地
            was_fainted  = before.get(f"{team}_{i}_fainted", False)
            now_fainted  = after.get(f"{team}_{i}_fainted", False)
            if not was_fainted and now_fainted:
                logs.append(f"  ☠️  {label} {name} 倒下了！")

            # 能量变化
            e_before = before.get(f"{team}_{i}_energy", 0)
            e_after  = after.get(f"{team}_{i}_energy", 0)
            if e_after > e_before:
                logs.append(f"  ⚡ {label} {name} 能量 +{e_after - e_before} → {e_after}")
            elif e_after < e_before:
                logs.append(f"  ⚡ {label} {name} 能量 -{e_before - e_after} → {e_after}")

            # 状态层数变化
            for key, icon, label_cn in [
                ("poison", "🟣", "中毒"),
                ("burn",   "🔥", "燃烧"),
                ("leech",  "🌿", "寄生"),
                ("meteor", "☄️", "星陨"),
            ]:
                b_val = before.get(f"{team}_{i}_{key}", 0)
                a_val = after.get(f"{team}_{i}_{key}", 0)
                if a_val > b_val:
                    logs.append(f"  {icon} {label} {name} 附加{label_cn} ×{a_val - b_val}（共{a_val}层）")
                elif a_val < b_val and a_val == 0:
                    logs.append(f"  {icon} {label} {name} {label_cn}消除")

            # 冻伤
            f_before = before.get(f"{team}_{i}_frost", 0)
            f_after  = after.get(f"{team}_{i}_frost", 0)
            if f_after > f_before:
                logs.append(f"  🧊 {label} {name} 冻伤累计 +{f_after - f_before}")

            # 属性变化
            for stat_key, stat_name in [("atk_mod", "物攻"), ("def_mod", "物防")]:
                sv_before = before.get(f"{team}_{i}_{stat_key}", 0)
                sv_after  = after.get(f"{team}_{i}_{stat_key}", 0)
                delta = sv_after - sv_before
                if abs(delta) >= 5:
                    sign = "+" if delta > 0 else ""
                    logs.append(f"  📈 {label} {name} {stat_name} {sign}{delta}%")

    # MP 变化
    mp_a_before = before.get("mp_a", 4)
    mp_a_after  = after.get("mp_a", 4)
    mp_b_before = before.get("mp_b", 4)
    mp_b_after  = after.get("mp_b", 4)
    if mp_a_after < mp_a_before:
        logs.append(f"  💔 你方 MP -{mp_a_before - mp_a_after} → {mp_a_after}")
    if mp_b_after < mp_b_before:
        logs.append(f"  💔 AI方 MP -{mp_b_before - mp_b_after} → {mp_b_after}")

    # 换人
    ca_before = before.get("current_a")
    ca_after  = after.get("current_a")
    cb_before = before.get("current_b")
    cb_after  = after.get("current_b")
    if ca_before != ca_after and ca_after is not None:
        logs.append(f"  🔄 你方 换上 {pname('a', ca_after)}")
    if cb_before != cb_after and cb_after is not None:
        logs.append(f"  🔄 AI方 换上 {pname('b', cb_after)}")

    return logs


# ═══════════════════════════════════════
# 全局战斗会话
# ═══════════════════════════════════════

class BattleSession:
    def __init__(self):
        self.state: Optional[BattleState] = None
        self.mcts_b: Optional[MCTS] = None
        self.waiting_for_player = False
        self.game_over = False
        self.logs: List[str] = []

    def reset(self):
        self.state = None
        self.mcts_b = None
        self.waiting_for_player = False
        self.game_over = False
        self.logs = []

    def add_log(self, text: str):
        self.logs.append(text)


session = BattleSession()


# ═══════════════════════════════════════
# 序列化
# ═══════════════════════════════════════

def serialize_pokemon(p, is_current=False):
    # ability_state 中有意义的 UI 字段
    ability_state = getattr(p, "ability_state", {}) or {}
    ability_info = []
    # 特性 buff 层数（如身经百练的应对计数）
    if ability_state.get("guard_counters", 0) > 0:
        ability_info.append(f"应对计数:{ability_state['guard_counters']}")
    if ability_state.get("undying_revive_in", 0) > 0:
        ability_info.append(f"复活倒计时:{ability_state['undying_revive_in']}")
    if ability_state.get("threat_speed_bonus_active"):
        ability_info.append("预警加速")
    if ability_state.get("cost_invert"):
        ability_info.append("能耗反转")

    return {
        "name":            p.name,
        "type":            p.pokemon_type.value,
        "hp":              p.hp,
        "current_hp":      max(0, p.current_hp),
        "energy":          p.energy,
        "is_fainted":      p.is_fainted,
        "ability":         p.ability,
        "poison_stacks":   p.poison_stacks,
        "burn_stacks":     p.burn_stacks,
        "frostbite_damage":p.frostbite_damage,
        "leech_stacks":    p.leech_stacks,
        "meteor_stacks":   p.meteor_stacks,
        "meteor_countdown":p.meteor_countdown,
        "charging":        p.charging_skill_idx >= 0,
        # 净值（正=buff，负=debuff）
        "atk_mod":         round((p.atk_up - p.atk_down) * 100),
        "def_mod":         round((p.def_up - p.def_down) * 100),
        "spatk_mod":       round((p.spatk_up - p.spatk_down) * 100),
        "spdef_mod":       round((p.spdef_up - p.spdef_down) * 100),
        "speed_mod":       round((p.speed_up - p.speed_down) * 100),
        # 分向数值（供前端分色显示）
        "atk_up":    round(p.atk_up * 100),
        "atk_down":  round(p.atk_down * 100),
        "def_up":    round(p.def_up * 100),
        "def_down":  round(p.def_down * 100),
        "spatk_up":  round(p.spatk_up * 100),
        "spatk_down":round(p.spatk_down * 100),
        "spdef_up":  round(p.spdef_up * 100),
        "spdef_down":round(p.spdef_down * 100),
        "speed_up":  round(p.speed_up * 100),
        "speed_down":round(p.speed_down * 100),
        # 特性状态
        "ability_info": ability_info,
        "skills":          [serialize_skill(s, p.energy, p.cooldowns.get(i, 0))
                            for i, s in enumerate(p.skills)] if is_current else [],
    }


def serialize_skill(s, current_energy, cooldown=0):
    effect_view = _skill_effect_display(s)
    return {
        "name":        s.name,
        "type":        s.skill_type.value,
        "category":    s.category.value,
        "power":       s.power,
        "energy_cost": s.energy_cost,
        "can_use":     current_energy >= s.energy_cost and cooldown <= 0,
        "on_cooldown": cooldown > 0,
        "cooldown":    cooldown,
        "tags":        _skill_tags(s),
        "effect_tags": effect_view["tags"],
        "effect_details": effect_view["details"],
        "effect_summary": effect_view["summary"],
        "has_effects": effect_view["has_effects"],
    }


def _skill_tags(s):
    tags = []
    if s.life_drain > 0:       tags.append(f"吸血{int(s.life_drain*100)}%")
    if s.damage_reduction > 0: tags.append(f"减伤{int(s.damage_reduction*100)}%")
    if s.self_heal_hp > 0:     tags.append(f"回血{int(s.self_heal_hp*100)}%")
    if s.poison_stacks > 0:    tags.append(f"中毒×{s.poison_stacks}")
    if s.burn_stacks > 0:      tags.append(f"燃烧×{s.burn_stacks}")
    if s.freeze_stacks > 0:    tags.append(f"冻结×{s.freeze_stacks}")
    if s.leech_stacks > 0:     tags.append(f"寄生×{s.leech_stacks}")
    if s.meteor_stacks > 0:    tags.append(f"星陨×{s.meteor_stacks}")
    if s.hit_count > 1:        tags.append(f"{s.hit_count}连击")
    if s.force_switch:         tags.append("折返")
    if s.agility:              tags.append("迅捷")
    if s.charge:               tags.append("蓄力")
    if s.priority_mod > 0:     tags.append("先手")
    if s.is_mark:              tags.append("印记")
    # 从 effects 读取更多标签，避免 UI 只看到基础数值
    if hasattr(s, "effects") and s.effects:
        from src.effect_models import SkillEffect as _SE, SkillTiming as _ST
        for item in s.effects:
            if isinstance(item, _SE):
                for tag in item.effects:
                    text = _effect_tag_text(tag)
                    if text:
                        tags.append(text.split(":", 1)[0].split("：", 1)[0])
            else:
                text = _effect_tag_text(item)
                if text:
                    tags.append(text.split("：", 1)[0])
    return list(dict.fromkeys(tags))  # 去重保序


def _get_type_effectiveness_for_display(attacker_type_val: str, defender_type_val: str) -> float:
    """计算技能对目标的克制倍率（用于换人提示）"""
    from src.models import get_type_effectiveness, Type
    try:
        atk_type = Type(attacker_type_val)
        def_type = Type(defender_type_val)
        return get_type_effectiveness(atk_type, def_type)
    except Exception:
        return 1.0


def serialize_state(state: BattleState, waiting: bool = False,
                    game_over: bool = False, winner: str = None,
                    events: List[dict] = None,
                    force_switch_prompt: bool = False):
    team_a_data = []
    for i, p in enumerate(state.team_a):
        d = serialize_pokemon(p, is_current=(i == state.current_a))
        d["is_current"] = (i == state.current_a)
        team_a_data.append(d)

    team_b_data = []
    for i, p in enumerate(state.team_b):
        d = serialize_pokemon(p, is_current=(i == state.current_b))
        d["is_current"] = (i == state.current_b)
        team_b_data.append(d)

    # 为 A 队每个精灵计算对当前 B 精灵的最高克制倍率
    enemy_b = state.team_b[state.current_b]
    for d in team_a_data:
        best_eff = 1.0
        for sk in (state.team_a[team_a_data.index(d)].skills if not d["is_current"]
                   else state.team_a[state.current_a].skills):
            eff = _get_type_effectiveness_for_display(sk.skill_type.value, enemy_b.pokemon_type.value)
            best_eff = max(best_eff, eff)
        d["type_advantage"] = best_eff  # 1.0=普通 2.0=克制 0.5=被克制

    return {
        "type":               "state",
        "turn":               state.turn,
        "mp_a":               state.mp_a,
        "mp_b":               state.mp_b,
        "team_a":             team_a_data,
        "team_b":             team_b_data,
        "current_a":          state.current_a,
        "current_b":          state.current_b,
        "waiting_for_player": waiting,
        "game_over":          game_over,
        "winner":             winner,
        "logs":               session.logs,       # 完整日志，前端增量追加
        "events":             events or [],        # 本回合动画事件
        "force_switch_prompt": force_switch_prompt,  # 泡沫幻影等触发后要求玩家选择换人
    }


# ═══════════════════════════════════════
# AI 被动换人
# ═══════════════════════════════════════

def _ai_switch_callback(state, team_list, alive_indices):
    from src.models import get_type_effectiveness
    best_idx  = alive_indices[0]
    best_score = -999
    enemy_team = "b" if team_list is state.team_a else "a"
    enemy = state.get_current(enemy_team)
    for idx in alive_indices:
        p = team_list[idx]
        hp_score   = p.current_hp / max(1, p.hp) * 50
        eff = 0
        for sk in p.skills:
            if sk.power > 0:
                eff = max(eff, get_type_effectiveness(sk.skill_type, enemy.pokemon_type))
        type_score = (eff - 1.0) * 30
        if hp_score + type_score > best_score:
            best_score = hp_score + type_score
            best_idx = idx
    return best_idx


# ═══════════════════════════════════════
# WebSocket
# ═══════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg  = json.loads(data)
            try:
                await handle_message(websocket, msg)
            except Exception as e:
                import traceback as _tb
                err_detail = _tb.format_exc()
                print(f"[WS ERROR] {e}\n{err_detail}", flush=True)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"服务器内部错误: {e}"
                    }))
                    if session.state and not session.game_over:
                        session.waiting_for_player = True
                        await websocket.send_text(json.dumps(serialize_state(
                            session.state, waiting=True
                        )))
                        await websocket.send_text(json.dumps({
                            "type": "your_turn", "turn": session.state.turn
                        }))
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


async def handle_message(ws: WebSocket, msg: dict):
    cmd = msg.get("cmd")
    if   cmd == "start":        await start_battle(ws)
    elif cmd == "start_custom": await start_custom_battle(ws, msg)
    elif cmd == "action":       await receive_player_action(ws, msg)
    elif cmd == "get_state":
        if session.state:
            winner = check_winner(session.state)
            await ws.send_text(json.dumps(serialize_state(
                session.state,
                waiting=session.waiting_for_player,
                game_over=session.game_over,
                winner=winner,
            )))
        else:
            await ws.send_text(json.dumps({"type": "no_battle"}))
    elif cmd == "reset":
        session.reset()
        await ws.send_text(json.dumps({"type": "reset_ok"}))


async def start_battle(ws: WebSocket):
    _ensure_loaded()
    session.reset()

    state = BattleState(
        team_a=TeamBuilder.create_toxic_team(),
        team_b=TeamBuilder.create_wing_team(),
        current_a=0, current_b=0, turn=1
    )
    session.state   = state
    session.mcts_b  = MCTS(simulations=150, team="b", experience=EXPERIENCE_B)
    session.game_over = False

    session.add_log("═══════════════════════════")
    session.add_log("⚔️  战斗开始！")
    session.add_log("🧑 毒队（你）  vs  🤖 翼王队（AI）")
    session.add_log("═══════════════════════════")

    # 初始换人
    snap_before = _snapshot(state)
    auto_switch(state, _ai_switch_callback, _ai_switch_callback)
    snap_after  = _snapshot(state)
    for line in _diff_to_logs(snap_before, snap_after, state):
        session.add_log(line)

    await ws.send_text(json.dumps(serialize_state(state, waiting=True)))
    session.waiting_for_player = True
    await ws.send_text(json.dumps({"type": "your_turn", "turn": state.turn}))


async def start_custom_battle(ws: WebSocket, msg: dict):
    """
    自定义阵容战斗启动。
    msg.player_team: [{name, skills:[skill_name×4]}×6]
    msg.ai_team: "toxic" | "wing"
    """
    _ensure_loaded()
    session.reset()

    player_team_cfg = msg.get("player_team", [])
    ai_team_key     = msg.get("ai_team", "wing")   # "toxic" 或 "wing"

    # ── 构建玩家阵容 ──
    from src.battle import TeamBuilder
    from src.skill_db import get_skill
    from src.pokemon_db import get_pokemon
    from src.models import Pokemon, Type
    from src.skill_db import load_ability_effects

    type_map = TeamBuilder.TYPE_MAP

    player_team = []
    errors = []
    for entry in player_team_cfg:
        pname      = entry.get("name", "")
        skill_names = entry.get("skills", [])
        data = get_pokemon(pname)
        if not data:
            errors.append(f"未找到精灵: {pname}")
            continue
        ptype_str = data["属性"]
        ability   = data["特性"]
        type_enum = type_map.get(ptype_str, Type.NORMAL)
        skills    = [get_skill(n) for n in skill_names if n]
        if len(skills) < 1:
            errors.append(f"{pname} 未配置技能")
            continue
        ability_effects = load_ability_effects(ability) if ability else []
        p = Pokemon(
            name=pname, pokemon_type=type_enum,
            hp=int(data["生命值"]), attack=int(data["物攻"]),
            defense=int(data["物防"]), sp_attack=int(data["魔攻"]),
            sp_defense=int(data["魔防"]), speed=int(data["速度"]),
            ability=ability, skills=skills,
        )
        p.ability_effects = ability_effects
        player_team.append(p)

    if errors:
        await ws.send_text(json.dumps({"type": "error", "message": "; ".join(errors)}))
        return
    if len(player_team) != 6:
        await ws.send_text(json.dumps({"type": "error", "message": f"需要6只精灵，当前{len(player_team)}只"}))
        return

    # ── 构建 AI 阵容 ──
    if ai_team_key == "toxic":
        ai_team = TeamBuilder.create_toxic_team()
        ai_name = "毒队"
    else:
        ai_team = TeamBuilder.create_wing_team()
        ai_name = "翼王队"

    state = BattleState(
        team_a=player_team,
        team_b=ai_team,
        current_a=0, current_b=0, turn=1
    )
    session.state   = state
    session.mcts_b  = MCTS(simulations=150, team="b", experience=EXPERIENCE_B)
    session.game_over = False

    session.add_log("═══════════════════════════")
    session.add_log("⚔️  战斗开始！")
    session.add_log(f"🧑 自定义阵容  vs  🤖 {ai_name}（AI）")
    session.add_log(f"🧑 你方: {', '.join(p.name for p in player_team)}")
    session.add_log(f"🤖 AI方: {', '.join(p.name for p in ai_team)}")
    session.add_log("═══════════════════════════")

    snap_before = _snapshot(state)
    auto_switch(state, _ai_switch_callback, _ai_switch_callback)
    snap_after  = _snapshot(state)
    for line in _diff_to_logs(snap_before, snap_after, state):
        session.add_log(line)

    await ws.send_text(json.dumps(serialize_state(state, waiting=True)))
    session.waiting_for_player = True
    await ws.send_text(json.dumps({"type": "your_turn", "turn": state.turn}))


async def receive_player_action(ws: WebSocket, msg: dict):
    if not session.state or session.game_over:
        return

    state       = session.state
    action_data = msg.get("action")

    # ── 解析玩家行动 ──
    action_a = None
    if action_data["type"] == "charge":
        action_a = (-1,)
    elif action_data["type"] == "skill":
        idx = action_data["index"]
        pa  = state.team_a[state.current_a]
        if idx < len(pa.skills) and pa.energy >= pa.skills[idx].energy_cost:
            action_a = (idx,)
        else:
            await ws.send_text(json.dumps({"type": "error", "message": "无法使用该技能"}))
            return
    elif action_data["type"] == "switch":
        target_idx = action_data["index"]
        if target_idx != state.current_a and not state.team_a[target_idx].is_fainted:
            action_a = (-2, target_idx)
        else:
            await ws.send_text(json.dumps({"type": "error", "message": "无法换人"}))
            return
    else:
        return

    session.waiting_for_player = False

    # ── 检查湿润印记（回合开始前） ──
    moisture_a = state.marks_a.get("moisture_mark", 0)
    moisture_b = state.marks_b.get("moisture_mark", 0)

    # ── 战报：回合头 ──
    pa = state.team_a[state.current_a]
    pb = state.team_b[state.current_b]
    session.add_log("")
    session.add_log(f"─── 回合 {state.turn} ───")
    session.add_log(
        f"  📌 当前: 🧑{pa.name}（HP {pa.current_hp}/{pa.hp} E={pa.energy}）"
        f"  vs  🤖{pb.name}（HP {pb.current_hp}/{pb.hp} E={pb.energy}）"
    )

    # ── 玩家行动描述 ──
    if action_a[0] == -1:
        session.add_log("  🧑 你选择：汇合聚能（+5能）")
    elif action_a[0] == -2:
        session.add_log(f"  🧑 你选择：换上 {state.team_a[action_a[1]].name}")
    else:
        sk = pa.skills[action_a[0]]
        eff_str = _eff_preview(sk)
        session.add_log(
            f"  🧑 你：{pa.name} 使用【{sk.name}】"
            f"（消耗{sk.energy_cost}能 威力{sk.power}）{eff_str}"
        )

    # ── AI 思考 ──
    await ws.send_text(json.dumps({"type": "ai_thinking"}))
    try:
        loop     = asyncio.get_running_loop()
        # BUG #1 FIX: Add 30s timeout to MCTS decision to prevent indefinite hanging
        action_b = await asyncio.wait_for(
            loop.run_in_executor(None, session.mcts_b.get_best_action, state),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        import traceback as _tb
        err_msg = "MCTS决策超时（>30s）"
        print(f"[AI TIMEOUT] {err_msg}", flush=True)
        session.add_log(f"  ⏱️  {err_msg}，使用随机决策")
        # 降级：随机选合法动作
        from src.battle import get_actions
        fallback_actions = get_actions(state, "b")
        import random
        action_b = random.choice(fallback_actions)
    except Exception as e:
        import traceback as _tb
        err = _tb.format_exc()
        print(f"[AI ERROR] {e}\n{err}", flush=True)
        session.add_log(f"  ❌ AI决策异常: {e}")
        # 降级：随机选合法动作
        from src.battle import get_actions
        fallback_actions = get_actions(state, "b")
        import random
        action_b = random.choice(fallback_actions)

    # ── AI行动描述 ──
    if action_b[0] == -1:
        session.add_log("  🤖 AI选择：汇合聚能（+5能）")
    elif action_b[0] == -2:
        session.add_log(f"  🤖 AI选择：换上 {state.team_b[action_b[1]].name}")
    else:
        sk_b    = pb.skills[action_b[0]]
        eff_str = _eff_preview(sk_b)
        session.add_log(
            f"  🤖 AI：{pb.name} 使用【{sk_b.name}】"
            f"（消耗{sk_b.energy_cost}能 威力{sk_b.power}）{eff_str}"
        )

    # ── 执行回合 ──
    snap_before = _snapshot(state)
    # 清除上回合的聚能日志
    if hasattr(state, "_energy_recharge_log"):
        state._energy_recharge_log.clear()
    try:
        execute_full_turn(state, action_a, action_b, _ai_switch_callback, _ai_switch_callback)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        session.add_log(f"  ❌ 战斗执行异常: {e}")
        await ws.send_text(json.dumps({"type": "error", "message": f"战斗异常: {e}\n{err_msg}"}))
        # 恢复等待玩家状态，让游戏可以继续
        session.waiting_for_player = True
        await ws.send_text(json.dumps(serialize_state(state, waiting=True)))
        await ws.send_text(json.dumps({"type": "your_turn", "turn": state.turn}))
        return
    snap_after  = _snapshot(state)

    # ── 聚能提示 ──
    for ev in getattr(state, "_energy_recharge_log", []):
        side_str = "🧑 你" if ev["team"] == "a" else "🤖 AI"
        session.add_log(
            f"  ⚡ {side_str}方 {ev['pokemon']} 能量不足（需{ev['needed']}，有{ev['had']}），"
            f"自动聚能+5，{ev['skill']}未能释放"
        )

    # ── 湿润印记触发提示（在执行前检测到的印记已在execute_full_turn开头消耗） ──
    if moisture_a > 0:
        session.add_log(f"  💧 湿润印记触发！你方全队技能能耗 -{moisture_a}")
    if moisture_b > 0:
        session.add_log(f"  💧 湿润印记触发！AI方全队技能能耗 -{moisture_b}")

    # ── 详细战报 ──
    diff_lines = _diff_to_logs(snap_before, snap_after, state)
    for line in diff_lines:
        session.add_log(line)

    # ── 回合结算摘要 ──
    pa2 = state.team_a[state.current_a]
    pb2 = state.team_b[state.current_b]
    session.add_log(
        f"  📊 结算 → 🧑{pa2.name} HP:{max(0,pa2.current_hp)}/{pa2.hp} E={pa2.energy}"
        f"  |  🤖{pb2.name} HP:{max(0,pb2.current_hp)}/{pb2.hp} E={pb2.energy}"
    )
    session.add_log(f"  🔷 MP → 你={state.mp_a} | AI={state.mp_b}")

    # ── 生成前端动画事件 ──
    events = _build_events(snap_before, snap_after, state, action_a, action_b, pa, pb)

    # ── 处理应对触发的强制换人（泡沫幻影等） ──
    pending = getattr(state, "_pending_switch_requests", [])
    if pending:
        state._pending_switch_requests = []
        for req in pending:
            if req["team"] == "a":
                # 玩家方需要手动选择
                session.add_log(f"  🔄 泡沫幻影应对成功！选择换上哪只精灵")
                await ws.send_text(json.dumps(serialize_state(
                    state, waiting=True, events=events,
                    force_switch_prompt=True,
                )))
                events = []  # 事件已发送，清空避免重复
                # 等待玩家发送换人消息（BUG #2 FIX: Add 15s timeout to prevent indefinite wait）
                try:
                    raw = await asyncio.wait_for(ws.receive_text(), timeout=15.0)
                    msg2 = json.loads(raw)
                except asyncio.TimeoutError:
                    session.add_log(f"  ⏱️  玩家选择换人超时（>15s），AI自动选择")
                    # 超时，AI代选
                    chosen = _ai_switch_callback(state, state.team_a, req["alive"])
                    msg2 = {"type": "switch", "index": chosen}
                except json.JSONDecodeError:
                    session.add_log(f"  ❌ 换人消息格式错误，AI自动选择")
                    chosen = _ai_switch_callback(state, state.team_a, req["alive"])
                    msg2 = {"type": "switch", "index": chosen}
                
                if msg2.get("type") == "switch" and msg2.get("index") in req["alive"]:
                    chosen = msg2["index"]
                    if req["team"] == "a":
                        state.current_a = chosen
                    else:
                        state.current_b = chosen
                    new_p = state.team_a[chosen] if req["team"] == "a" else state.team_b[chosen]
                    session.add_log(f"  ↩️  换上 {new_p.name}")
                    # 触发入场特性
                    from src.battle import _trigger_battle_start_effects
                    _trigger_battle_start_effects(state)
                    EffectExecutor.execute_agility_entry(
                        state, new_p,
                        state.team_b[state.current_b] if req["team"] == "a" else state.team_a[state.current_a],
                        req["team"],
                    )
                    if new_p.ability_effects:
                        EffectExecutor.execute_ability(
                            state, new_p,
                            state.team_b[state.current_b] if req["team"] == "a" else state.team_a[state.current_a],
                            Timing.ON_ENTER, new_p.ability_effects, req["team"],
                        )
            else:
                # AI方由 AI 决策
                chosen = _ai_switch_callback(state, state.team_b, req["alive"])
                state.current_b = chosen
                new_p = state.team_b[chosen]
                session.add_log(f"  🤖 AI 换上 {new_p.name}")
                from src.battle import _trigger_battle_start_effects
                _trigger_battle_start_effects(state)

    winner = check_winner(state)
    if winner:
        session.game_over = True
        if winner == "a":
            session.add_log("")
            session.add_log("🏆 你赢了！毒队胜利！")
        else:
            session.add_log("")
            session.add_log("💔 AI赢了！翼王队胜利！")
        await ws.send_text(json.dumps(serialize_state(
            state, waiting=False, game_over=True, winner=winner, events=events
        )))
        return

    session.waiting_for_player = True
    await ws.send_text(json.dumps(serialize_state(state, waiting=True, events=events)))
    await ws.send_text(json.dumps({"type": "your_turn", "turn": state.turn}))


def _eff_preview(s) -> str:
    """技能效果简短预览，附在战报行中"""
    parts = []
    if s.life_drain > 0:        parts.append(f"吸血{int(s.life_drain*100)}%")
    if s.damage_reduction > 0:  parts.append(f"减伤{int(s.damage_reduction*100)}%")
    if s.poison_stacks > 0:     parts.append(f"→中毒×{s.poison_stacks}")
    if s.burn_stacks > 0:       parts.append(f"→燃烧×{s.burn_stacks}")
    if s.leech_stacks > 0:      parts.append(f"→寄生×{s.leech_stacks}")
    if s.meteor_stacks > 0:     parts.append(f"→星陨×{s.meteor_stacks}")
    if s.force_switch:           parts.append("→折返")
    if s.agility:                parts.append("（迅捷）")
    if s.charge:                 parts.append("（蓄力）")
    # effects 里的应对标签
    if hasattr(s, "effects") and s.effects:
        from src.effect_models import E, SkillEffect, SkillTiming
        for item in s.effects:
            if isinstance(item, SkillEffect) and item.timing == SkillTiming.ON_COUNTER:
                cat = item.filter.get("category", "")
                if cat == "attack":   parts.append("[应对物/魔]")
                elif cat == "defense": parts.append("[应对防御]")
                elif cat == "status":  parts.append("[应对变化]")
            elif hasattr(item, "type"):
                if item.type == E.COUNTER_ATTACK:  parts.append("[应对物/魔]")
                if item.type == E.COUNTER_DEFENSE: parts.append("[应对防御]")
                if item.type == E.COUNTER_STATUS:  parts.append("[应对变化]")
    return "  " + " | ".join(parts) if parts else ""


def _build_events(snap_before, snap_after, state, action_a, action_b, pa_before, pb_before) -> List[dict]:
    """生成本回合前端动画事件列表"""
    events = []
    n = len(state.team_a)

    # A 方伤害事件
    ca = snap_before.get("current_a", 0)
    hp_before = snap_before.get(f"a_{ca}_hp", 0)
    hp_after  = snap_after.get(f"a_{ca}_hp", 0)
    if hp_before - hp_after > 0:
        events.append({"type": "hit", "side": "a", "dmg": hp_before - hp_after})

    # B 方伤害事件
    cb = snap_before.get("current_b", 0)
    hp_before = snap_before.get(f"b_{cb}_hp", 0)
    hp_after  = snap_after.get(f"b_{cb}_hp", 0)
    if hp_before - hp_after > 0:
        events.append({"type": "hit", "side": "b", "dmg": hp_before - hp_after})

    # 防御技能（damage_reduction > 0）→ 盾牌事件
    if action_a[0] >= 0:
        sk = pa_before.skills[action_a[0]]
        if sk.damage_reduction > 0 or _has_counter(sk):
            events.append({"type": "shield", "side": "a"})
    if action_b[0] >= 0:
        sk = pb_before.skills[action_b[0]]
        if sk.damage_reduction > 0 or _has_counter(sk):
            events.append({"type": "shield", "side": "b"})

    # 倒地事件
    for team, n_count in [("a", len(state.team_a)), ("b", len(state.team_b))]:
        for i in range(n_count):
            if not snap_before.get(f"{team}_{i}_fainted") and snap_after.get(f"{team}_{i}_fainted"):
                events.append({"type": "faint", "side": team, "idx": i})

    return events


def _has_counter(s) -> bool:
    if hasattr(s, "effects") and s.effects:
        from src.effect_models import E, SkillEffect, SkillTiming
        for item in s.effects:
            if isinstance(item, SkillEffect) and item.timing == SkillTiming.ON_COUNTER:
                return True
            if hasattr(item, "type") and item.type in (E.COUNTER_ATTACK, E.COUNTER_DEFENSE, E.COUNTER_STATUS):
                return True
    return (s.counter_physical_power_mult > 0 or s.counter_defense_power_mult > 0
            or s.counter_status_power_mult > 0)


# ═══════════════════════════════════════
# REST API — 阵容搭配器数据接口
# ═══════════════════════════════════════

@app.get("/api/pokemon/list")
async def api_pokemon_list(q: str = ""):
    """搜索精灵列表（支持名称关键词/属性筛选），返回全部匹配结果"""
    _ensure_loaded()
    from src.pokemon_db import _get_conn
    conn = _get_conn()
    c = conn.cursor()
    if q:
        c.execute(
            "SELECT id, name, element, ability, base_hp, base_atk, base_spatk, "
            "base_def, base_spdef, base_speed, base_total "
            "FROM pokemon WHERE name LIKE ? OR element LIKE ? "
            "ORDER BY name",
            (f"%{q}%", f"%{q}%"),
        )
    else:
        c.execute(
            "SELECT id, name, element, ability, base_hp, base_atk, base_spatk, "
            "base_def, base_spdef, base_speed, base_total "
            "FROM pokemon ORDER BY name"
        )
    rows = c.fetchall()
    result = []
    for r in rows:
        # 提取简短特性名（去掉冒号后的描述）
        ability_short = r["ability"].split(":")[0].split("：")[0] if r["ability"] else ""
        result.append({
            "id":      r["id"],
            "name":    r["name"],
            "element": r["element"],
            "ability": ability_short,
            "base_total": r["base_total"],
            "base_hp":    r["base_hp"],
            "base_atk":   r["base_atk"],
            "base_spatk": r["base_spatk"],
            "base_def":   r["base_def"],
            "base_spdef": r["base_spdef"],
            "base_speed": r["base_speed"],
        })
    return JSONResponse(result)


@app.get("/api/pokemon/skills")
async def api_pokemon_skills(name: str):
    """获取指定精灵可学技能列表（优先精确匹配，其次前缀匹配）"""
    _ensure_loaded()
    from src.pokemon_db import _get_conn
    conn = _get_conn()
    c = conn.cursor()

    # 精确匹配 → 前缀匹配（取进化阶段最高的）
    c.execute("SELECT id FROM pokemon WHERE name = ?", (name,))
    row = c.fetchone()
    if not row:
        c.execute(
            "SELECT id FROM pokemon WHERE name LIKE ? ORDER BY evo_stage DESC LIMIT 1",
            (f"{name}%",),
        )
        row = c.fetchone()
    if not row:
        return JSONResponse([])

    pokemon_id = row["id"]
    c.execute(
        "SELECT DISTINCT s.name, s.element, s.category, s.energy_cost, s.power, s.description "
        "FROM skill s "
        "JOIN pokemon_skill ps ON ps.skill_id = s.id "
        "WHERE ps.pokemon_id = ? "
        "ORDER BY s.energy_cost, s.name",
        (pokemon_id,),
    )
    rows = c.fetchall()
    from src.skill_db import get_skill
    result = []
    for r in rows:
        skill = get_skill(r["name"])
        effect_view = _skill_effect_display(skill)
        result.append({
            "name":        r["name"],
            "element":     r["element"],
            "category":    r["category"],
            "energy_cost": r["energy_cost"],
            "power":       r["power"],
            "description": r["description"] or "",
            "tags":        effect_view["tags"],
            "effect_details": effect_view["details"],
            "effect_summary": effect_view["summary"],
            "has_effects": effect_view["has_effects"],
        })
    return JSONResponse(result)


# ═══════════════════════════════════════
# 静态文件 & 路由
# ═══════════════════════════════════════

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/battle")
async def battle_page():
    return FileResponse(os.path.join(STATIC_DIR, "battle.html"))

@app.get("/team")
async def team_page():
    return FileResponse(os.path.join(STATIC_DIR, "team.html"))

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    print("启动战斗服务器: http://localhost:8765")
    uvicorn.run(app, host="0.0.0.0", port=8765)

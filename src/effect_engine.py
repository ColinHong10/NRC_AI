"""
效果执行引擎 — 根据 EffectTag 列表驱动战斗效果

核心类 EffectExecutor 提供:
  - execute_skill()          执行技能的全部效果
  - execute_counter()        执行应对效果（子效果走同一个 _apply_tag）
  - execute_ability()        在指定时机触发特性
  - execute_agility_entry()  入场时执行迅捷技能
  - execute_drive()          传动系统

所有效果原语通过 _HANDLERS 注册表分发，不管来自技能、应对子效果还是特性，
逻辑只写一次。
"""

import random
from typing import List, Optional, Dict, Callable, TYPE_CHECKING

from src.effect_models import E, EffectTag, Timing, AbilityEffect, SkillTiming, SkillEffect

if TYPE_CHECKING:
    from src.models import Pokemon, Skill, BattleState, SkillCategory


# ============================================================
#  执行上下文
# ============================================================

class Ctx:
    """
    效果执行上下文 — 替代散落各处的参数传递。

    所有 handler 函数签名: (tag, ctx) -> None
    handler 可以读写 ctx 上的任意字段来传递信息。
    """
    __slots__ = (
        "state", "user", "target", "skill",
        "result", "is_first", "team",
        "enemy_skill", "damage",
    )

    def __init__(
        self,
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill" = None,
        result: Dict = None,
        is_first: bool = False,
        team: str = "a",
        enemy_skill: "Skill" = None,
        damage: int = 0,
    ):
        self.state = state
        self.user = user
        self.target = target
        self.skill = skill
        self.result = result if result is not None else {}
        self.is_first = is_first
        self.team = team
        self.enemy_skill = enemy_skill
        self.damage = damage


# ============================================================
#  辅助函数
# ============================================================

def _get_ability_name(pokemon: "Pokemon") -> str:
    """从 '特性名:描述' 格式中提取特性名"""
    if ":" in pokemon.ability:
        return pokemon.ability.split(":")[0]
    if "：" in pokemon.ability:
        return pokemon.ability.split("：")[0]
    return pokemon.ability


def _find_skill_index(pokemon: "Pokemon", skill: "Skill") -> int:
    """找到技能在精灵技能列表中的索引"""
    for i, s in enumerate(pokemon.skills):
        if s.name == skill.name:
            return i
    return -1


def _apply_buff(pokemon: "Pokemon", params: Dict) -> None:
    """应用正向属性修改（写入 *_up 字段）"""
    if "atk" in params:
        pokemon.atk_up += params["atk"]
    if "def" in params:
        pokemon.def_up += params["def"]
    if "spatk" in params:
        pokemon.spatk_up += params["spatk"]
    if "spdef" in params:
        pokemon.spdef_up += params["spdef"]
    if "speed" in params:
        pokemon.speed_up += params["speed"]
    if "all_atk" in params:
        pokemon.atk_up += params["all_atk"]
        pokemon.spatk_up += params["all_atk"]
    if "all_def" in params:
        pokemon.def_up += params["all_def"]
        pokemon.spdef_up += params["all_def"]


def _apply_debuff(pokemon: "Pokemon", params: Dict) -> None:
    """应用负向属性修改（写入 *_down 字段，params 中的值为正数）"""
    if "atk" in params:
        pokemon.atk_down += params["atk"]
    if "def" in params:
        pokemon.def_down += params["def"]
    if "spatk" in params:
        pokemon.spatk_down += params["spatk"]
    if "spdef" in params:
        pokemon.spdef_down += params["spdef"]
    if "speed" in params:
        pokemon.speed_down += params["speed"]
    if "all_atk" in params:
        pokemon.atk_down += params["all_atk"]
        pokemon.spatk_down += params["all_atk"]
    if "all_def" in params:
        pokemon.def_down += params["all_def"]
        pokemon.spdef_down += params["all_def"]


def _clear_buffs(pokemon: "Pokemon") -> None:
    """清除所有正向增益（*_up 字段归零，power_multiplier 重置）"""
    pokemon.atk_up = 0.0
    pokemon.def_up = 0.0
    pokemon.spatk_up = 0.0
    pokemon.spdef_up = 0.0
    pokemon.speed_up = 0.0
    pokemon.power_multiplier = 1.0
    pokemon.life_drain_mod = 0.0
    pokemon.skill_power_bonus = min(0, pokemon.skill_power_bonus)
    pokemon.skill_power_pct_mod = min(0.0, pokemon.skill_power_pct_mod)
    pokemon.skill_cost_mod = max(0, pokemon.skill_cost_mod)
    pokemon.hit_count_mod = min(0, pokemon.hit_count_mod)
    pokemon.priority_stage = min(0, pokemon.priority_stage)
    pokemon.next_attack_power_bonus = 0
    pokemon.next_attack_power_pct = 0.0


def _clear_debuffs(pokemon: "Pokemon") -> None:
    """清除所有负向减益（*_down 字段归零）"""
    pokemon.atk_down = 0.0
    pokemon.def_down = 0.0
    pokemon.spatk_down = 0.0
    pokemon.spdef_down = 0.0
    pokemon.speed_down = 0.0
    pokemon.poison_stacks = 0
    pokemon.burn_stacks = 0
    pokemon.freeze_stacks = 0
    pokemon.leech_stacks = 0
    pokemon.priority_stage = max(0, pokemon.priority_stage)


def _ability_name(pokemon: "Pokemon") -> str:
    if not getattr(pokemon, "ability", ""):
        return ""
    return pokemon.ability.split(":")[0].split("（")[0].strip()


def _adjust_cost_delta(pokemon: "Pokemon", delta: int) -> int:
    """能耗增减调整：对流特性反转增减方向"""
    return -delta if pokemon.ability_state.get("cost_invert") else delta


def _iter_flat_tags_static(effects) -> list:
    """从 List[SkillEffect] 或 List[EffectTag] 中提取所有 EffectTag（平铺）。"""
    if not effects:
        return
    for item in effects:
        if isinstance(item, SkillEffect):
            yield from item.effects
        else:
            yield item


def _check_runtime_condition(tag: EffectTag, ctx: Ctx) -> bool:
    condition = tag.params.get("condition", "")
    if not condition:
        return True
    if condition == "after_use_hp_gt_half":
        return ctx.user.current_hp > ctx.user.hp / 2
    if condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        return ratio > threshold if condition == "self_hp_above" else ratio < threshold
    if condition in ("enemy_hp_above", "enemy_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        return ratio > threshold if condition == "enemy_hp_above" else ratio < threshold
    if condition == "enemy_switch":
        return bool(ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a)
    return True


def _check_skill_filter(filt: Dict, ctx: Ctx) -> bool:
    """检查 SkillEffect 的 filter 条件是否满足。"""
    if not filt:
        return True

    # 应对类别匹配（ON_COUNTER 阶段由 execute_counter_se 单独处理，此处跳过）
    if "category" in filt:
        return True

    if filt.get("enemy_switch"):
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if not enemy_switched:
            return False

    if filt.get("first_strike"):
        if not ctx.is_first:
            return False

    if "self_hp_lt" in filt:
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        if ratio >= filt["self_hp_lt"]:
            return False

    if "self_hp_gt" in filt:
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        if ratio <= filt["self_hp_gt"]:
            return False

    if "enemy_hp_lt" in filt:
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        if ratio >= filt["enemy_hp_lt"]:
            return False

    if "enemy_hp_gt" in filt:
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        if ratio <= filt["enemy_hp_gt"]:
            return False

    if filt.get("on_kill"):
        # is_fainted 在 battle.py 扣血后设置
        # 在 execute_skill 内部，用 damage 是否能击杀来判断
        damage_dealt = ctx.result.get("damage", 0)
        target_dead = ctx.target.is_fainted or (
            damage_dealt > 0 and ctx.target.current_hp <= damage_dealt
        )
        if not target_dead:
            return False

    if filt.get("energy_zero_after"):
        if ctx.user.energy > 0:
            return False

    if filt.get("prev_counter_success"):
        if ctx.user.ability_state.get("last_counter_success_turn") != ctx.state.turn - 1:
            return False

    if filt.get("counter"):
        # counter 模式: 只在 execute_counter 上下文中生效
        return True

    if "per" in filt:
        # per 条件由 handler 处理缩放逻辑，这里只判断是否有层数
        per = filt["per"]
        if per == "enemy_poison":
            if ctx.target.poison_stacks <= 0:
                return False
        elif per == "enemy_burn":
            if ctx.target.burn_stacks <= 0:
                return False

    if "self_hp_above" in filt:
        threshold = float(filt["self_hp_above"])
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        if start_hp / max(1, ctx.user.hp) <= threshold:
            return False

    if "self_hp_below" in filt:
        threshold = float(filt["self_hp_below"])
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        if start_hp / max(1, ctx.user.hp) >= threshold:
            return False

    if "prev_status" in filt:
        if not (ctx.user.ability_state.get("last_skill_category") == "状态"
                and ctx.user.ability_state.get("last_skill_turn") == ctx.state.turn - 1):
            return False

    if "self_missing_hp_step" in filt:
        # 始终通过 — 实际缩放在 handler 里
        pass

    if "energy_cost_above_base" in filt:
        # 始终通过 — 实际缩放在 handler 里
        pass

    if "per_enemy_poison" in filt:
        if ctx.target.poison_stacks <= 0:
            return False

    return True


def _apply_permanent_mod(user: "Pokemon", skill: "Skill", params: Dict,
                         force: bool = False) -> None:
    """应用永久修改（能耗/威力）。
    per_counter 和 per_position_change 由外部手动调用时传 force=True 绕过 guard。
    """
    target = params.get("target", "")
    delta = params.get("delta", 0)
    trigger = params.get("trigger", "")

    # 非 force 模式下，跳过需要由外部手动触发的类型
    if not force and trigger in ("per_position_change", "per_counter", "per_use"):
        return

    if target == "cost":
        skill.energy_cost = max(0, skill.energy_cost + _adjust_cost_delta(user, delta))
    elif target == "power":
        skill.power = max(0, skill.power + delta)
    elif target == "hit_count":
        skill.hit_count = max(1, skill.hit_count + int(delta))


def _execute_agility_old(pokemon: "Pokemon", enemy: "Pokemon", skill: "Skill") -> None:
    """旧逻辑：执行迅捷技能（没有 effects 字段的技能）"""
    pokemon.energy -= skill.energy_cost
    pokemon.apply_self_buff(skill)
    enemy.apply_enemy_debuff(skill)
    if skill.poison_stacks > 0:
        enemy.poison_stacks += skill.poison_stacks
    if skill.burn_stacks > 0:
        enemy.burn_stacks += skill.burn_stacks
    if skill.leech_stacks > 0:
        enemy.leech_stacks += skill.leech_stacks
    if skill.power > 0 and not enemy.is_fainted:
        from src.battle import DamageCalculator
        dmg = DamageCalculator.calculate(pokemon, enemy, skill)
        enemy.current_hp -= dmg
        if enemy.current_hp <= 0:
            enemy.current_hp = 0
            from src.models import StatusType
            enemy.status = StatusType.FAINTED


# ============================================================
#  效果处理器注册表
#  每个 handler: (tag: EffectTag, ctx: Ctx) -> None
#  特殊返回值通过 ctx.result 传递
# ============================================================

def _h_damage(tag: EffectTag, ctx: Ctx) -> None:
    from src.battle import DamageCalculator, get_mark_damage_modifiers
    skill = ctx.skill

    # ── 惊吓: 能量=0的攻击者无法对目标造伤 ──
    if ctx.target.ability_state.get("immune_zero_energy_attacker") and ctx.user.energy == 0:
        ctx.result["damage"] = ctx.result.get("damage", 0)
        return

    # ── 逐魂鸟: 能耗≤N的攻击技能无法对目标造伤 ──
    immune_cost_threshold = ctx.target.ability_state.get("immune_low_cost_attack")
    if immune_cost_threshold is not None:
        from src.models import SkillCategory
        if skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
            actual_cost = getattr(skill, "_last_actual_cost", skill.energy_cost)
            if actual_cost <= immune_cost_threshold:
                ctx.result["damage"] = ctx.result.get("damage", 0)
                return

    # ── 印记伤害修正 ──
    mark_mods = get_mark_damage_modifiers(ctx.state, ctx.team, ctx.is_first, skill)

    power = (
        skill.power
        + ctx.user.skill_power_bonus
        + ctx.user.next_attack_power_bonus
        + ctx.result.get("_power_bonus", 0)
        + mark_mods["power_bonus"]
    )
    power_mult = (
        1.0
        + ctx.user.skill_power_pct_mod
        + ctx.user.next_attack_power_pct
        + (ctx.result.get("_power_mult", 1.0) - 1.0)
        + (mark_mods["power_mult"] - 1.0)
    )
    if power_mult != 1.0:
        power = int(power * power_mult)
    if power > 0 and not ctx.target.is_fainted:
        weather = getattr(ctx.state, "weather", None)
        hit_count = max(
            1,
            int(
                (skill.hit_count + ctx.user.hit_count_mod + ctx.result.get("_hit_count_bonus", 0))
                * ctx.result.get("_hit_count_mult", 1.0)
            ),
        )

        # ── 侵蚀: 敌方每有1层中毒，连击数+1 (仅攻击技能) ──
        if ctx.user.ability_state.get("hit_count_per_poison"):
            from src.models import SkillCategory as _SC
            if skill.category in (_SC.PHYSICAL, _SC.MAGICAL) and ctx.target.poison_stacks > 0:
                hit_count += ctx.target.poison_stacks

        # ── 噼啪！: 入场首次行动使用次数+1 ──
        if ctx.user.ability_state.get("first_action_bonus"):
            hit_count += 1

        # ── 无差别过滤: 任一方有此标记则连击数固定为2 ──
        fixed_hit = ctx.user.ability_state.get("fixed_hit_count_all") or ctx.target.ability_state.get("fixed_hit_count_all")
        if fixed_hit:
            hit_count = fixed_hit

        # 龙噬印记的攻击倍率：临时加到 atk_up
        old_atk_up = ctx.user.atk_up
        old_spatk_up = ctx.user.spatk_up
        if mark_mods["atk_mult"] > 1.0:
            extra = mark_mods["atk_mult"] - 1.0
            ctx.user.atk_up += extra
            ctx.user.spatk_up += extra

        dmg = DamageCalculator.calculate(ctx.user, ctx.target, skill,
                                         power_override=power, weather=weather,
                                         hit_count_override=hit_count)

        # 恢复临时修正
        ctx.user.atk_up = old_atk_up
        ctx.user.spatk_up = old_spatk_up

        ctx.result["damage"] = ctx.result.get("damage", 0) + dmg
        if ctx.user.next_attack_power_bonus or ctx.user.next_attack_power_pct:
            ctx.result["_consume_next_attack_mod"] = True

        # 星陨印记：造成伤害后消耗层数，造成额外魔伤
        meteor_stacks = mark_mods["meteor_mark_stacks"]
        if meteor_stacks > 0 and dmg > 0:
            enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
            enemy_marks["meteor_mark"] = 0
            meteor_power = 30 * meteor_stacks
            # 星陨印记造成魔法伤害（用攻方魔攻 vs 被攻方魔防）
            from src.models import SkillCategory, Type
            e_spatk = ctx.user.effective_spatk()
            t_spdef = max(1.0, ctx.target.effective_spdef())
            meteor_dmg = max(1, int((e_spatk / t_spdef) * meteor_power * 0.9))
            ctx.target.current_hp -= meteor_dmg
            ctx.result["damage"] = ctx.result.get("damage", 0) + meteor_dmg
            if ctx.target.current_hp <= 0:
                ctx.target.current_hp = 0
                from src.models import StatusType
                ctx.target.status = StatusType.FAINTED


def _h_self_buff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    _apply_buff(ctx.user, tag.params)


def _h_self_debuff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    _apply_debuff(ctx.user, tag.params)


def _h_enemy_debuff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    if tag.params.get("invert"):
        _apply_buff(ctx.target, {k: abs(v) for k, v in tag.params.items() if k != "invert"})
    else:
        _apply_debuff(ctx.target, tag.params)


def _h_heal_hp(tag: EffectTag, ctx: Ctx) -> None:
    pct = tag.params.get("pct", 0)
    heal = int(ctx.user.hp * pct)
    ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)


def _h_heal_energy(tag: EffectTag, ctx: Ctx) -> None:
    ctx.user.gain_energy(tag.params.get("amount", 1))


def _h_self_ko(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_self_ko"] = True


def _h_energy_all_in(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_ALL_IN: 消耗所有能量，威力按消耗量缩放（魔能爆）。
    在 PRE_USE 阶段执行：把当前能量换算成威力加成，然后清空能量。
    """
    current_energy = ctx.user.energy
    power_per_energy = tag.params.get("power_per_energy", 30)
    if current_energy > 0:
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + current_energy * power_per_energy
        ctx.user.energy = 0


def _h_reset_skill_cost(tag: EffectTag, ctx: Ctx) -> None:
    ctx.skill.energy_cost = getattr(ctx.skill, "_base_energy_cost", ctx.skill.energy_cost)


def _h_steal_energy(tag: EffectTag, ctx: Ctx) -> None:
    amt = tag.params.get("amount", 1)
    ctx.user.gain_energy(amt)
    ctx.target.energy = max(0, ctx.target.energy - amt)


def _h_enemy_lose_energy(tag: EffectTag, ctx: Ctx) -> None:
    tgt = tag.params.get("target", "enemy")
    if tgt == "self_mp":
        # 飓风特性: 扣己方MP
        if ctx.team == "a":
            ctx.state.mp_a -= tag.params.get("amount", 1)
        else:
            ctx.state.mp_b -= tag.params.get("amount", 1)
    elif tgt in ("enemy_new", "enemy"):
        ctx.target.energy = max(0, ctx.target.energy - tag.params.get("amount", 1))
    else:
        ctx.target.energy = max(0, ctx.target.energy - tag.params.get("amount", 1))


def _h_life_drain(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_life_drain_pct"] = ctx.result.get("_life_drain_pct", 0.0) + tag.params.get("pct", 0)


def _h_grant_life_drain(tag: EffectTag, ctx: Ctx) -> None:
    ctx.user.life_drain_mod += tag.params.get("pct", 0)


def _h_poison(tag: EffectTag, ctx: Ctx) -> None:
    stacks = tag.params.get("stacks", 1)
    # 特殊: stacks_per_poison_skill（溶解扩散特性）
    if tag.params.get("stacks_per_poison_skill"):
        ability_state = getattr(ctx.user, "ability_state", {})
        stacks = ability_state.get("poison_skill_count", 0)
    # 特殊: stacks_per_mark（扩散侵蚀特性）
    if tag.params.get("stacks_per_mark"):
        mult = tag.params["stacks_per_mark"]
        enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
        mark_stacks = enemy_marks.get("poison_mark", 0)
        stacks = mark_stacks * mult
    # 目标选择
    tgt = tag.params.get("target", "enemy")
    if tgt in ("enemy", "enemy_new"):
        ctx.target.poison_stacks += stacks
    else:
        ctx.user.poison_stacks += stacks


def _h_burn(tag: EffectTag, ctx: Ctx) -> None:
    ctx.target.burn_stacks += tag.params.get("stacks", 1)


def _h_freeze(tag: EffectTag, ctx: Ctx) -> None:
    ctx.target.freeze_stacks += tag.params.get("stacks", 1)


def _h_leech(tag: EffectTag, ctx: Ctx) -> None:
    ctx.target.leech_stacks += tag.params.get("stacks", 1)


def _h_meteor(tag: EffectTag, ctx: Ctx) -> None:
    ctx.target.meteor_stacks += tag.params.get("stacks", 1)
    if ctx.target.meteor_countdown <= 0:
        ctx.target.meteor_countdown = 3


def _h_poison_mark(tag: EffectTag, ctx: Ctx) -> None:
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    marks["poison_mark"] = marks.get("poison_mark", 0) + tag.params.get("stacks", 1)


def _h_moisture_mark(tag: EffectTag, ctx: Ctx) -> None:
    tgt = tag.params.get("target", "enemy")
    if tgt == "self":
        marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    else:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    stacks = tag.params.get("stacks", 1)
    marks["moisture_mark"] = marks.get("moisture_mark", 0) + stacks
    # 湿润印记立即生效：释放后当回合就减能耗，不等下回合
    team_id = ctx.team if tgt == "self" else ("b" if ctx.team == "a" else "a")
    team_list = ctx.state.team_a if team_id == "a" else ctx.state.team_b
    for p in team_list:
        for s in p.skills:
            delta = -stacks
            if p.ability_state.get("cost_invert"):
                delta = -delta
            s.energy_cost = max(0, s.energy_cost + delta)
    marks["moisture_mark"] = 0  # 已消耗


def _h_mark_generic(tag: EffectTag, ctx: Ctx, mark_key: str) -> None:
    """通用印记 handler：根据 target 参数放入对应队伍的 marks dict。"""
    tgt = tag.params.get("target", "enemy")
    if tgt == "self":
        marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    else:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    marks[mark_key] = marks.get(mark_key, 0) + tag.params.get("stacks", 1)


def _h_dragon_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "dragon_mark")

def _h_wind_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "wind_mark")

def _h_charge_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "charge_mark")

def _h_solar_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "solar_mark")

def _h_attack_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "attack_mark")

def _h_slow_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "slow_mark")

def _h_sluggish_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "sluggish_mark")

def _h_spirit_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "spirit_mark")

def _h_meteor_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "meteor_mark")

def _h_thorn_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "thorn_mark")


# ── 印记特殊操作 handler ──

def _h_dispel_enemy_marks(tag: EffectTag, ctx: Ctx) -> None:
    """驱散敌方所有印记"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    enemy_marks.clear()


def _h_convert_marks_to_burn(tag: EffectTag, ctx: Ctx) -> None:
    """炎爆术: 将敌方印记转换为 ratio 倍灼烧层数"""
    ratio = tag.params.get("ratio", 3)
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.target.burn_stacks += int(total * ratio)
        enemy_marks.clear()


def _h_dispel_marks_to_burn(tag: EffectTag, ctx: Ctx) -> None:
    """焚烧烙印: 驱散双方所有印记，每层→N层灼烧"""
    burn_per = tag.params.get("burn_per_mark", 5)
    total = 0
    total += sum(v for v in ctx.state.marks_a.values() if isinstance(v, (int, float)))
    total += sum(v for v in ctx.state.marks_b.values() if isinstance(v, (int, float)))
    ctx.state.marks_a.clear()
    ctx.state.marks_b.clear()
    if total > 0:
        ctx.target.burn_stacks += int(total * burn_per)


def _h_consume_marks_heal(tag: EffectTag, ctx: Ctx) -> None:
    """食腐: 驱散敌方印记，每层回复自己 heal_pct 生命"""
    heal_pct = tag.params.get("heal_pct_per_mark", 0.1)
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    enemy_marks.clear()
    if total > 0:
        heal = int(ctx.user.hp * heal_pct * total)
        ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)


def _h_marks_to_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """心灵洞悉: 敌方获得星陨，层数=敌方印记总层数"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.target.meteor_stacks += int(total)
        if ctx.target.meteor_countdown <= 0:
            ctx.target.meteor_countdown = 3


def _h_steal_marks(tag: EffectTag, ctx: Ctx) -> None:
    """翅刃应对时: 偷取敌方印记给己方"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    my_marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    for k, v in enemy_marks.items():
        my_marks[k] = my_marks.get(k, 0) + v
    enemy_marks.clear()


def _h_energy_cost_per_enemy_mark(tag: EffectTag, ctx: Ctx) -> None:
    """四维降解: 敌方每层印记能耗-1"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.result["_energy_refund"] = ctx.result.get("_energy_refund", 0) + int(total)


def _h_damage_reduction(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_damage_reduction"] = tag.params.get("pct", 0)
    # 特性场景：减伤信息也存到 ability_damage_reduction
    if "ability_damage_reduction" in ctx.result or ctx.result.get("_is_ability_ctx"):
        ctx.result["ability_damage_reduction"] = tag.params.get("pct", 0)


def _h_force_switch(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["force_switch"] = True


def _h_force_enemy_switch(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["force_enemy_switch"] = True


def _h_agility(tag: EffectTag, ctx: Ctx) -> None:
    pass  # 标记，由 execute_agility_entry 处理


def _h_convert_buff_to_poison(tag: EffectTag, ctx: Ctx) -> None:
    total_buff = 0
    for attr in ["atk_up", "def_up", "spatk_up", "spdef_up", "speed_up"]:
        v = getattr(ctx.target, attr, 0)
        if v > 0:
            total_buff += int(v * 10)
            setattr(ctx.target, attr, 0.0)
    if total_buff > 0:
        ctx.target.poison_stacks += total_buff


def _h_convert_poison_to_mark(tag: EffectTag, ctx: Ctx) -> None:
    on = tag.params.get("on", "")
    ratio = tag.params.get("ratio", 0)
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    if on == "kill" and ctx.target.is_fainted:
        stacks = ctx.target.poison_stacks
        marks["poison_mark"] = marks.get("poison_mark", 0) + stacks
        ctx.target.poison_stacks = 0
    elif ratio > 0:
        stacks = ctx.target.poison_stacks
        converted = stacks // ratio
        if converted > 0:
            ctx.target.poison_stacks -= converted * ratio
            marks["poison_mark"] = marks.get("poison_mark", 0) + converted


def _h_dispel_marks(tag: EffectTag, ctx: Ctx) -> None:
    cond = tag.params.get("condition", "")
    if cond == "not_blocked":
        ctx.result["_dispel_if_not_blocked"] = True
    else:
        ctx.state.marks_a.clear()
        ctx.state.marks_b.clear()


def _h_conditional_buff(tag: EffectTag, ctx: Ctx) -> None:
    condition = tag.params.get("condition", "")
    buff = tag.params.get("buff", {})
    if condition == "enemy_switch":
        ctx.result["_conditional_enemy_switch_buff"] = buff
    elif condition == "after_use_hp_gt_half":
        if ctx.user.current_hp > ctx.user.hp / 2:
            ctx.result.setdefault("_post_use_self_buffs", []).append(buff)
    elif condition in ("self_hp_gt", "self_hp_lt", "enemy_hp_gt", "enemy_hp_lt"):
        threshold = float(tag.params.get("threshold", 0))
        source = ctx.user if condition.startswith("self") else ctx.target
        ratio = source.current_hp / max(1, source.hp)
        matched = ratio > threshold if condition.endswith("_gt") else ratio < threshold
        if matched:
            target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
            _apply_buff(target, buff)
    elif condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        ratio = start_hp / max(1, ctx.user.hp)
        matched = ratio > threshold if condition == "self_hp_above" else ratio < threshold
        if matched:
            target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
            _apply_buff(target, buff)
    elif condition == "per_enemy_poison":
        stacks = ctx.target.poison_stacks
        if stacks > 0:
            scaled_buff = {k: v * stacks for k, v in buff.items()}
            _apply_buff(ctx.user, scaled_buff)


def _h_energy_cost_dynamic(tag: EffectTag, ctx: Ctx) -> None:
    per = tag.params.get("per", "")
    reduce = tag.params.get("reduce", 0)
    if per == "enemy_poison":
        stacks = ctx.target.poison_stacks
        ctx.result["_energy_refund"] = stacks * reduce


def _h_power_dynamic(tag: EffectTag, ctx: Ctx) -> None:
    condition = tag.params.get("condition", "")
    if condition == "first_strike" and ctx.is_first:
        bonus_pct = tag.params.get("bonus_pct", 0)
        ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) + bonus_pct
    elif condition == "enemy_switch":
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if enemy_switched:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "prev_status":
        if ctx.user.ability_state.get("last_skill_category") == "状态" and ctx.user.ability_state.get("last_skill_turn") == ctx.state.turn - 1:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "prev_counter_success":
        if ctx.user.ability_state.get("last_counter_success_turn") == ctx.state.turn - 1:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "energy_zero_after_use":
        if ctx.user.energy == 0:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "enemy_energy_leq":
        threshold = tag.params.get("threshold", 0)
        if ctx.target.energy <= threshold:
            if "multiplier" in tag.params:
                mult = tag.params.get("multiplier", 1.0)
                ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) * mult
            else:
                ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "self_missing_hp_step":
        step_pct = float(tag.params.get("step_pct", 0.05))
        bonus_per_step = int(tag.params.get("bonus_per_step", 0))
        if step_pct > 0 and bonus_per_step:
            missing_pct = max(0.0, 1.0 - (ctx.user.current_hp / max(1, ctx.user.hp)))
            steps = int(missing_pct / step_pct)
            if steps > 0:
                ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + steps * bonus_per_step
    elif condition == "energy_cost_above_base":
        base_cost = int(tag.params.get("base_cost", ctx.skill.energy_cost))
        bonus_per_step = int(tag.params.get("bonus_per_step", 0))
        steps = max(0, ctx.skill.energy_cost - base_cost)
        if steps > 0 and bonus_per_step:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + steps * bonus_per_step
    elif condition == "per_poison":
        stacks = ctx.target.poison_stacks
        bonus = tag.params.get("bonus_per_stack", 0) * stacks
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + bonus
    elif condition == "counter":
        # 应对时威力倍率（偷袭3倍），在 execute_counter 中处理
        mult = tag.params.get("multiplier", 1.0)
        from src.battle import DamageCalculator
        new_power = int(ctx.skill.power * mult)
        weather = getattr(ctx.state, "weather", None)
        ctx.result["final_damage"] = DamageCalculator.calculate(
            ctx.user, ctx.target, ctx.skill, power_override=new_power, weather=weather,
        )

def _h_permanent_mod(tag: EffectTag, ctx: Ctx) -> None:
    _apply_permanent_mod(ctx.user, ctx.skill, tag.params)


def _h_skill_mod(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    stat = tag.params.get("stat", "")
    value = tag.params.get("value", 0)
    condition = tag.params.get("condition", "")
    if condition == "enemy_switch":
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if not enemy_switched:
            return
    elif condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        ratio = start_hp / max(1, ctx.user.hp)
        matched = ratio > threshold if condition == "self_hp_above" else ratio < threshold
        if not matched:
            return
    if stat == "power":
        target.skill_power_bonus += int(value)
    elif stat == "power_pct":
        target.skill_power_pct_mod += value
    elif stat == "cost":
        target.skill_cost_mod += _adjust_cost_delta(target, int(value))
    elif stat == "hit_count":
        target.hit_count_mod += int(value)
    elif stat == "current_hit_count":
        ctx.result["_hit_count_bonus"] = ctx.result.get("_hit_count_bonus", 0) + int(value)
    elif stat == "current_hit_count_mult":
        ctx.result["_hit_count_mult"] = ctx.result.get("_hit_count_mult", 1.0) * float(value)
    elif stat == "priority":
        target.priority_stage += int(value)


def _h_next_attack_mod(tag: EffectTag, ctx: Ctx) -> None:
    ctx.user.next_attack_power_bonus += int(tag.params.get("power_bonus", 0))
    ctx.user.next_attack_power_pct += tag.params.get("power_pct", 0.0)


def _h_cleanse(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    mode = tag.params.get("mode", "all")
    if mode in ("buffs", "all"):
        _clear_buffs(target)
    if mode in ("debuffs", "all"):
        _clear_debuffs(target)


def _h_dispel_buffs(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "enemy") == "self" else ctx.target
    _clear_buffs(target)


def _h_dispel_debuffs(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    _clear_debuffs(target)


def _h_position_buff(tag: EffectTag, ctx: Ctx) -> None:
    positions = tag.params.get("positions", [])
    buff = tag.params.get("buff", {})
    skill_idx = _find_skill_index(ctx.user, ctx.skill)
    if skill_idx in positions:
        _apply_buff(ctx.user, buff)


def _h_drive(tag: EffectTag, ctx: Ctx) -> None:
    value = tag.params.get("value", 1)
    ability_filter = ctx.result.get("_ability_filter", {}) if isinstance(ctx.result, dict) else {}
    positions = ability_filter.get("positions", [])

    # 位置型特性：把"传动"转成对应技能本体上的 DRIVE 标签，避免每回合重复叠加。
    if ctx.skill is None and positions:
        for idx, skill in enumerate(ctx.user.skills):
            if idx not in positions:
                continue
            if not getattr(skill, "effects", None):
                skill.effects = []
            # 兼容 SE 和 EffectTag 列表：检查是否已有 DRIVE
            has_drive = False
            for item in skill.effects:
                if isinstance(item, SkillEffect):
                    has_drive = has_drive or any(
                        t.type == E.DRIVE and t.params.get("value", 1) == value
                        for t in item.effects
                    )
                elif hasattr(item, "type") and item.type == E.DRIVE and item.params.get("value", 1) == value:
                    has_drive = True
            if not has_drive:
                if skill.effects and isinstance(skill.effects[0], SkillEffect):
                    skill.effects.append(SkillEffect(SkillTiming.POST_USE, [EffectTag(E.DRIVE, {"value": value})]))
                else:
                    skill.effects.append(EffectTag(E.DRIVE, {"value": value}))
        return

    ctx.result["_drive_value"] = value


def _h_passive_energy_reduce(tag: EffectTag, ctx: Ctx) -> None:
    pass  # 由 execute_drive 处理


def _h_replay_agility(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_replay_agility"] = True


def _h_agility_cost_share(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_agility_cost_share"] = tag.params.get("divisor", 2)


def _h_energy_cost_accumulate(tag: EffectTag, ctx: Ctx) -> None:
    delta = tag.params.get("delta", 1)
    ctx.skill.energy_cost = max(0, ctx.skill.energy_cost + _adjust_cost_delta(ctx.user, delta))


def _h_weather(tag: EffectTag, ctx: Ctx) -> None:
    """设置天气，持续指定回合。params: {"type": "sunny"|"rain"|"sandstorm"|"hail"|"snow", "turns": 8}"""
    from src.models import Type as TypeEnum
    weather_type = tag.params.get("type", "sunny")
    turns = tag.params.get("turns", 5)
    ctx.state.weather = weather_type
    ctx.state.weather_turns = turns  # 写入持续回合数

    # 沙暴：地面系技能能耗减半（向下取整）
    if weather_type == "sandstorm":
        if not hasattr(ctx.state, "_sandstorm_original_costs"):
            ctx.state._sandstorm_original_costs = {}
        for p in ctx.state.team_a + ctx.state.team_b:
            if p.is_fainted:
                continue
            for sk in p.skills:
                if sk.skill_type == TypeEnum.GROUND:
                    key = id(sk)
                    if key not in ctx.state._sandstorm_original_costs:
                        ctx.state._sandstorm_original_costs[key] = sk.energy_cost
                    sk.energy_cost = max(1, sk.energy_cost // 2)


# ── 注册表 ──
_WEATHER_DAMAGE_TYPES = {"sandstorm", "snow"}   # 洛克王国真实天气（沙暴/雪天）
_WEATHER_IMMUNE_TYPES = {"ground", "steel"}      # 游戏无岩系，免疫天气伤害的属性


def _apply_weather_damage(state) -> None:
    """回合结束时应用天气效果。
    - 沙暴：对非地/钢系造成 1/16 HP 伤害
    - 雪天：双方获得 2 层冻结
    """
    from src.models import Type
    w = state.weather
    if not w:
        return
    immune = {Type.GROUND, Type.STEEL}
    if w == "sandstorm":
        dmg_pct = 1 / 16
        for p in state.team_a:
            if not p.is_fainted and p.pokemon_type not in immune:
                p.current_hp = max(1, p.current_hp - int(p.hp * dmg_pct))
        for p in state.team_b:
            if not p.is_fainted and p.pokemon_type not in immune:
                p.current_hp = max(1, p.current_hp - int(p.hp * dmg_pct))
    if w == "snow":
        for p in state.team_a:
            if not p.is_fainted:
                p.freeze_stacks += 2
        for p in state.team_b:
            if not p.is_fainted:
                p.freeze_stacks += 2


def _h_enemy_energy_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    from src.models import SkillCategory as SC
    amount = tag.params.get("amount", 0)
    filt = tag.params.get("filter", "all")
    duration = tag.params.get("duration", 0)

    # Timed cost modifiers are stored on the target and consumed by battle.py
    # when that target actually spends energy on a later turn.
    if duration:
        mod = {
            "amount": int(amount),
            "filter": filt,
            "turns": int(duration),
        }
        if filt in ("used_skill", "other_skills") and ctx.enemy_skill is not None:
            mod["skill_name"] = ctx.enemy_skill.name
        ctx.target.ability_state.setdefault("temporary_skill_cost_mods", []).append(mod)
        return

    for s in ctx.target.skills:
        if filt == "attack" and s.category in (SC.PHYSICAL, SC.MAGICAL):
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))
        elif filt == "all":
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))


def _h_mirror_damage(tag: EffectTag, ctx: Ctx) -> None:
    """
    反弹伤害（听桥）：将攻击方对自己造成的原始伤害值原样反弹给攻击方。
    ctx.damage 在 execute_counter 中传入的是减伤前的原始伤害值。
    如果 ctx.damage == 0（对方没有造成伤害，如状态/防御技能），则不反弹。
    """
    mirror_dmg = ctx.damage
    if mirror_dmg > 0 and not ctx.target.is_fainted:
        ctx.target.current_hp -= mirror_dmg
        from src.models import StatusType
        if ctx.target.current_hp <= 0:
            ctx.target.current_hp = 0
            ctx.target.status = StatusType.FAINTED


def _h_counter_override(tag: EffectTag, ctx: Ctx) -> None:
    replace_type = tag.params.get("replace", "")
    from_val = tag.params.get("from", 0)
    to_val = tag.params.get("to", 0)
    if replace_type == "poison":
        ctx.target.poison_stacks -= from_val
        ctx.target.poison_stacks += to_val


def _h_passive_energy_reduce_water_ring(tag: EffectTag, ctx: Ctx) -> None:
    """水环应对攻击时：全技能能耗 -N（在 execute_counter 子效果中）"""
    reduce = tag.params.get("reduce", 0)
    rng = tag.params.get("range", "all")
    if rng == "all":
        for s in ctx.user.skills:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))


def _h_permanent_mod_ability(tag: EffectTag, ctx: Ctx) -> None:
    """特性中的永久修改（身经百练）"""
    per_counter = tag.params.get("per_counter", 0)
    ability_filter = ctx.result.get("_ability_filter", {}) if isinstance(ctx.result, dict) else {}
    positions = ability_filter.get("positions", [])

    if per_counter > 0:
        counter_count = getattr(
            ctx.state,
            "counter_count_a" if ctx.team == "a" else "counter_count_b",
            0
        )
        bonus_pct = per_counter * counter_count
        skill_filter = tag.params.get("skill_filter", {})
        elements = skill_filter.get("element", [])
        from src.skill_db import _TYPE_MAP
        for s in ctx.user.skills:
            if positions and _find_skill_index(ctx.user, s) not in positions:
                continue
            if elements:
                type_matched = any(_TYPE_MAP.get(el) == s.skill_type for el in elements)
                if not type_matched:
                    continue
            base_power = getattr(s, "_ability_base_power", s.power)
            setattr(s, "_ability_base_power", base_power)
            s.power = int(base_power * (1.0 + bonus_pct))
    else:
        if ctx.skill is not None:
            _apply_permanent_mod(ctx.user, ctx.skill, tag.params)
            return

        if positions:
            for idx, s in enumerate(ctx.user.skills):
                if idx not in positions:
                    continue
                if tag.params.get("target") == "power":
                    base_power = getattr(s, "_ability_base_power", s.power)
                    setattr(s, "_ability_base_power", base_power)
                    s.power = max(0, base_power + int(tag.params.get("delta", 0)))
                else:
                    _apply_permanent_mod(ctx.user, s, tag.params)
        else:
            for s in ctx.user.skills:
                _apply_permanent_mod(ctx.user, s, tag.params)


# ── 应对容器 handler（仅收集，实际由 execute_counter 触发）──

def _h_counter_attack(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)


def _h_counter_status(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)


def _h_counter_defense(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)


def _h_ability_compute(tag: EffectTag, ctx: Ctx) -> None:
    """ABILITY_COMPUTE: 运行时计算并存入 pokemon.ability_state"""
    action = tag.params.get("action", "")
    pokemon = ctx.user

    if action == "count_poison_skills":
        from src.skill_db import _TYPE_MAP
        from src.models import Type
        count = sum(1 for s in pokemon.skills if s.skill_type == Type.POISON)
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["poison_skill_count"] = count

    elif action == "modify_matching_skills":
        _apply_matching_skill_mods(pokemon, ctx.target, tag.params)

    elif action == "shared_wing_skills":
        from src.models import Type
        team_list = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
        my_skills = {s.name for s in pokemon.skills}
        shared = set()
        for p in team_list:
            if p.name == pokemon.name:
                continue
            if p.pokemon_type == Type.FLYING:
                for s in p.skills:
                    if s.name in my_skills:
                        shared.add(s.name)
        for s in pokemon.skills:
            if s.name in shared:
                s.agility = True
                if getattr(s, "effects", None):
                    if not any(e.type == E.AGILITY for e in _iter_flat_tags_static(s.effects)):
                        if isinstance(s.effects[0], SkillEffect):
                            # Insert AGILITY into the first ON_USE SE
                            for se in s.effects:
                                if se.timing == SkillTiming.ON_USE:
                                    se.effects.insert(0, EffectTag(E.AGILITY))
                                    break
                            else:
                                s.effects.insert(0, SkillEffect(SkillTiming.ON_USE, [EffectTag(E.AGILITY)]))
                        else:
                            s.effects.insert(0, EffectTag(E.AGILITY))

    elif action == "grant_first_skill_agility":
        # 给第一个技能添加迅捷标记
        if pokemon.skills:
            first_skill = pokemon.skills[0]
            first_skill.agility = True
            # 如果技能有 effects 框架，添加 AGILITY 标记
            if getattr(first_skill, "effects", None) and isinstance(first_skill.effects, list):
                # 检查是否已有 AGILITY
                has_agility = any(
                    e.type == E.AGILITY for e in _iter_flat_tags_static(first_skill.effects)
                )
                if not has_agility:
                    if isinstance(first_skill.effects[0], SkillEffect):
                        for se in first_skill.effects:
                            if se.timing == SkillTiming.ON_USE:
                                se.effects.insert(0, EffectTag(E.AGILITY))
                                break
                        else:
                            first_skill.effects.insert(0, SkillEffect(SkillTiming.ON_USE, [EffectTag(E.AGILITY)]))
                    else:
                        first_skill.effects.insert(0, EffectTag(E.AGILITY))

    elif action == "first_strike_power_bonus":
        # 标记 Pokemon 在先手时应用威力提升（需要在 battle.py 中检查并应用）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["first_strike_power_bonus"] = tag.params.get("bonus_pct", 0.0)

    elif action == "first_strike_hit_bonus":
        # 标记 Pokemon 在先手时应用连击数提升（需要在 battle.py 中检查并应用）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["first_strike_hit_bonus"] = True

    elif action == "auto_switch_on_zero_energy":
        # 标记能量为0时自动换人（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["auto_switch_zero_energy"] = True

    elif action == "auto_switch_every_turn":
        # 标记每回合末自动换人（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["auto_switch_every_turn"] = True

    elif action == "swap_ally_on_zero_energy":
        # 标记能量为0时替换队友入场（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["swap_ally_zero_energy"] = True


def _h_ability_increment_counter(tag: EffectTag, ctx: Ctx) -> None:
    """ABILITY_INCREMENT_COUNTER: 海豹船长计数+1"""
    if ctx.team == "a":
        ctx.state.counter_count_a += 1
    else:
        ctx.state.counter_count_b += 1


def _skill_matches_ability_filter(skill: "Skill", params: Dict) -> bool:
    """判断技能是否匹配特性筛选条件。"""
    from src.models import SkillCategory
    from src.skill_db import _TYPE_MAP

    elements = params.get("element")
    if elements:
        if not isinstance(elements, (list, tuple, set)):
            elements = [elements]
        expected = {_TYPE_MAP.get(el) for el in elements}
        if skill.skill_type not in expected:
            return False

    category = params.get("category", "")
    if category == "attack" and skill.category not in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
        return False
    if category == "defense" and skill.category != SkillCategory.DEFENSE:
        return False
    if category == "status" and skill.category != SkillCategory.STATUS:
        return False

    if params.get("attack_only") and skill.power <= 0:
        return False

    if params.get("pure_attack"):
        if skill.power <= 0:
            return False
        # 兼容 SE 和 EffectTag: "纯攻击"= 只有 DAMAGE 效果
        flat_tags = list(_iter_flat_tags_static(skill.effects)) if skill.effects else []
        if not flat_tags or len(flat_tags) != 1 or flat_tags[0].type != E.DAMAGE:
            return False

    if "energy_cost_gt" in params and skill.energy_cost <= params["energy_cost_gt"]:
        return False
    if "energy_cost_ge" in params and skill.energy_cost < params["energy_cost_ge"]:
        return False
    if "energy_cost_lt" in params and skill.energy_cost >= params["energy_cost_lt"]:
        return False
    if "energy_cost_le" in params and skill.energy_cost > params["energy_cost_le"]:
        return False
    if "energy_cost_eq" in params and skill.energy_cost != params["energy_cost_eq"]:
        return False

    return True


def _apply_matching_skill_mods(pokemon: "Pokemon", enemy: "Pokemon", params: Dict) -> None:
    """对匹配的携带技能应用持久修改。"""
    count_source = params.get("count_source", "")
    count = 1
    if count_source == "self_element":
        from src.skill_db import _TYPE_MAP
        elements = params.get("count_element", params.get("element", []))
        if not isinstance(elements, (list, tuple, set)):
            elements = [elements]
        count_types = {_TYPE_MAP.get(el) for el in elements}
        count = sum(1 for s in pokemon.skills if s.skill_type in count_types)
    elif count_source == "enemy_energy_sum":
        count = sum(max(0, s.energy_cost) for s in enemy.skills)

    power_pct = float(params.get("power_pct", 0.0)) * count
    power_bonus = int(params.get("power_bonus", 0)) * count
    hit_count_bonus = int(params.get("hit_count_bonus", 0)) * count
    grant_agility = bool(params.get("grant_agility", False))

    for s in pokemon.skills:
        if not _skill_matches_ability_filter(s, params):
            continue

        if power_pct or power_bonus:
            base_power = getattr(s, "_ability_base_power", s.power)
            setattr(s, "_ability_base_power", base_power)
            s.power = max(0, int(base_power * (1.0 + power_pct)) + power_bonus)

        if hit_count_bonus:
            s.hit_count = max(1, s.hit_count + hit_count_bonus)

        if grant_agility:
            s.agility = True


def _h_transfer_mods(tag: EffectTag, ctx: Ctx) -> None:
    """TRANSFER_MODS: 洁癖离场时保存属性修正，存入 result 供 battle.py 传递"""
    pokemon = ctx.user
    ctx.result["transfer_mods"] = {
        "atk_up":     pokemon.atk_up,
        "atk_down":   pokemon.atk_down,
        "def_up":     pokemon.def_up,
        "def_down":   pokemon.def_down,
        "spatk_up":   pokemon.spatk_up,
        "spatk_down": pokemon.spatk_down,
        "spdef_up":   pokemon.spdef_up,
        "spdef_down": pokemon.spdef_down,
        "speed_up":   pokemon.speed_up,
        "speed_down": pokemon.speed_down,
    }


def _h_burn_no_decay(tag: EffectTag, ctx: Ctx) -> None:
    """BURN_NO_DECAY: 标记煤渣草在场，本回合灼烧不衰减"""
    ctx.result["burn_no_decay"] = True


def _h_power_multiplier_buff(tag: EffectTag, ctx: Ctx) -> None:
    """POWER_MULTIPLIER_BUFF: 独立威力提升乘法层，站场期间持续，下场重置"""
    ctx.user.power_multiplier *= tag.params.get("multiplier", 1.0)


# ── 特性专用 handler（从 battle.py 硬编码迁移）──

def _h_threat_speed_buff(tag: EffectTag, ctx: Ctx) -> None:
    """THREAT_SPEED_BUFF: 预警/哨兵 — 敌方有击杀威胁时速度加成"""
    from src.battle import _has_ko_threat
    pokemon = ctx.user
    enemy = ctx.target
    # 清除上回合的临时标记
    pokemon.ability_state.pop("threat_speed_bonus_active", None)
    pokemon.ability_state.pop("force_switch_after_action", None)
    if _has_ko_threat(enemy, pokemon):
        speed_val = tag.params.get("speed", 0.5)
        pokemon.speed_up += speed_val
        pokemon.ability_state["threat_speed_bonus_active"] = True
        if tag.params.get("force_switch", False):
            pokemon.ability_state["force_switch_after_action"] = True


def _h_counter_accumulate_transform(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_ACCUMULATE_TRANSFORM: 保卫 — 应对成功计数，达阈值变身棋绮后"""
    from src.battle import _transform_to_guard_queen
    pokemon = ctx.user
    skill = ctx.result.get("_counter_skill") or getattr(ctx, "skill", None)
    # 按 category_filter 过滤（默认只有防御类技能触发）
    cat_filter = tag.params.get("category_filter", "")
    if cat_filter and skill:
        from src.models import SkillCategory
        if skill.category != SkillCategory(cat_filter):
            return
    # 每回合只计数一次
    if pokemon.ability_state.get("guard_counter_turn") == ctx.state.turn:
        return
    pokemon.ability_state["guard_counter_turn"] = ctx.state.turn
    count = pokemon.ability_state.get("guard_counters", 0) + 1
    pokemon.ability_state["guard_counters"] = count
    threshold = tag.params.get("threshold", 2)
    if count >= threshold:
        pokemon.ability_state["guard_counters"] = 0
        defer = ctx.result.get("_defer_transform", False)
        if defer:
            pokemon.ability_state["guard_transform_pending"] = True
        else:
            _transform_to_guard_queen(pokemon)


def _h_delayed_revive(tag: EffectTag, ctx: Ctx) -> None:
    """DELAYED_REVIVE: 不朽 — 力竭时设置延迟复活计时器"""
    turns = tag.params.get("turns", 3)
    ctx.user.ability_state["undying_revive_in"] = turns


def _h_copy_switch_state(tag: EffectTag, ctx: Ctx) -> None:
    """COPY_SWITCH_STATE: 贪婪 — 敌方换人时复制离场精灵状态到入场精灵"""
    from src.battle import _transfer_pokemon_state
    context = ctx.result if isinstance(ctx.result, dict) else {}
    # context 由 battle.py 的 execute_ability 调用传入
    snapshot = context.get("switch_snapshot")
    switched_in = context.get("switched_in")
    if snapshot and switched_in:
        _transfer_pokemon_state(snapshot, switched_in)


def _h_cost_invert(tag: EffectTag, ctx: Ctx) -> None:
    """COST_INVERT: 对流 — 设置能耗反转被动标记"""
    ctx.user.ability_state["cost_invert"] = True

# ── TIER 1 特性 handler ──

def _h_counter_success_double_damage(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_DOUBLE_DAMAGE: 应对成功后下一次伤害翻倍"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["double_damage_next"] = True


def _h_counter_success_buff_permanent(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_BUFF_PERMANENT: 应对成功后获得永久增益"""
    if not ctx.user or not ctx.user.ability_state:
        return
    
    params = tag.params
    if not ctx.user.ability_state.get("counter_buffs"):
        ctx.user.ability_state["counter_buffs"] = {}
    
    # Merge buff params
    if "atk" in params:
        ctx.user.ability_state["counter_buffs"]["atk"] = params["atk"]
    if "spatk" in params:
        ctx.user.ability_state["counter_buffs"]["spatk"] = params["spatk"]
    if "def" in params:
        ctx.user.ability_state["counter_buffs"]["def"] = params["def"]
    if "spdef" in params:
        ctx.user.ability_state["counter_buffs"]["spdef"] = params["spdef"]
    if "speed" in params:
        ctx.user.ability_state["counter_buffs"]["speed"] = params["speed"]


def _h_counter_success_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_POWER_BONUS: 应对成功后威力永久+N（斗技）"""
    if not ctx.user or not ctx.user.ability_state:
        return
    
    delta = tag.params.get("delta", 20)
    if "power_bonus" not in ctx.user.ability_state:
        ctx.user.ability_state["power_bonus"] = 0
    ctx.user.ability_state["power_bonus"] += delta


def _h_counter_success_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_COST_REDUCE: 应对成功后能耗永久-N（思维之盾）"""
    if not ctx.user or not ctx.user.ability_state:
        return
    
    delta = tag.params.get("delta", 5)
    if "cost_reduce" not in ctx.user.ability_state:
        ctx.user.ability_state["cost_reduce"] = 0
    ctx.user.ability_state["cost_reduce"] += delta


def _h_counter_success_speed_priority(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_SPEED_PRIORITY: 应对成功后速度优先级+1（野性感官）"""
    if not ctx.user or not ctx.user.ability_state:
        return
    
    if "speed_priority" not in ctx.user.ability_state:
        ctx.user.ability_state["speed_priority"] = 0
    ctx.user.ability_state["speed_priority"] += 1


def _h_first_strike_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_POWER_BONUS: 先手攻击威力加成（破空/顺风）"""
    if not ctx.is_first:
        return
    
    bonus_pct = tag.params.get("bonus_pct", 0.5)
    if "power_multiplier" not in ctx.result:
        ctx.result["power_multiplier"] = 1.0
    ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_first_strike_hit_count(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_HIT_COUNT: 先手攻击连击数+1（咔咔冲刺）"""
    if not ctx.is_first:
        return
    
    if not ctx.skill or not hasattr(ctx.skill, 'hit_count'):
        return
    
    ctx.skill.hit_count += 1


def _h_first_strike_agility(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_AGILITY: 首个技能获得迅捷（起飞加速）"""
    if not ctx.is_first:
        return
    
    ctx.user.agility_tag = True


def _h_auto_switch_on_zero_energy(tag: EffectTag, ctx: Ctx) -> None:
    """AUTO_SWITCH_ON_ZERO_ENERGY: 能量为0时自动换人（警惕）"""
    if ctx.user and ctx.user.energy <= 0:
        ctx.user.force_switch = True


def _h_auto_switch_after_action(tag: EffectTag, ctx: Ctx) -> None:
    """AUTO_SWITCH_AFTER_ACTION: 每个回合结束后自动换人（防过载保护）"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["auto_switch_eot"] = True




# ── 注册表 ──

# ──────────────────────────────────────────────
# TIER 2 Handlers
# ──────────────────────────────────────────────

def _h_team_synergy_bug_swarm_attack(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_SWARM_ATTACK: 虫群突袭 - +15% stats per other bug"""
    if not ctx.user or not ctx.battle:
        return
    # Count bugs in team (excluding self)
    bug_count = 0
    for mon in ctx.battle.user_team:
        if mon and mon != ctx.user and mon.type1 == 9 or mon.type2 == 9:  # 9 = Bug type
            bug_count += 1
    bonus_pct = tag.params.get("bonus_pct", 0.15)
    multiplier = 1.0 + (bonus_pct * bug_count)
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["all"] = multiplier


def _h_team_synergy_bug_swarm_inspire(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_SWARM_INSPIRE: 虫群鼓舞 - +10% stats per other bug"""
    if not ctx.user or not ctx.battle:
        return
    # Count bugs in team (excluding self)
    bug_count = 0
    for mon in ctx.battle.user_team:
        if mon and mon != ctx.user and (mon.type1 == 9 or mon.type2 == 9):
            bug_count += 1
    bonus_pct = tag.params.get("bonus_pct", 0.1)
    multiplier = 1.0 + (bonus_pct * bug_count)
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["all"] = multiplier


def _h_team_synergy_brave_if_bugs(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BRAVE_IF_BUGS: 壮胆 - +50% attack if bugs in team"""
    if not ctx.user or not ctx.battle:
        return
    # Check if any other bug in team
    has_bugs = any(mon and mon != ctx.user and (mon.type1 == 9 or mon.type2 == 9) for mon in ctx.battle.user_team)
    if has_bugs:
        bonus_pct = tag.params.get("bonus_pct", 0.5)
        if "stat_multiplier" not in ctx.result:
            ctx.result["stat_multiplier"] = {}
        ctx.result["stat_multiplier"]["atk"] = 1.0 + bonus_pct


def _h_team_synergy_bug_kill_aff(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_KILL_AFF: 振奋虫心 - +5 aff on team kill (ON_KILL)"""
    if ctx.user and ctx.user.ability_state is not None:
        aff_bonus = tag.params.get("aff_bonus", 5)
        ctx.user.ability_state["aff_bonus"] = aff_bonus


def _h_stat_scale_defense_per_energy(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_DEFENSE_PER_ENERGY: 囤积 - +10% defense per energy"""
    if not ctx.user:
        return
    bonus_pct_per_energy = tag.params.get("bonus_pct_per_energy", 0.1)
    multiplier = 1.0 + (bonus_pct_per_energy * ctx.user.energy)
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["def"] = multiplier


def _h_stat_scale_hits_per_hp_lost(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_HITS_PER_HP_LOST: 嫁祸 - +2 hits per 25% HP lost"""
    if not ctx.user:
        return
    max_hp = ctx.user.max_hp if ctx.user.max_hp > 0 else 1
    hp_lost_pct = (max_hp - ctx.user.hp) / max_hp
    quarters_lost = int(hp_lost_pct * 4)  # 0-4 quarters
    hits_per_quarter = tag.params.get("hits_per_quarter", 2)
    extra_hits = quarters_lost * hits_per_quarter
    if "hit_count_bonus" not in ctx.result:
        ctx.result["hit_count_bonus"] = 0
    ctx.result["hit_count_bonus"] += extra_hits


def _h_stat_scale_attack_decay(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_ATTACK_DECAY: 全神贯注 - +100% attack, -20% per action"""
    if not ctx.user or ctx.user.ability_state is None:
        return
    init_bonus = tag.params.get("init_bonus", 1.0)
    decay_per_action = tag.params.get("decay_per_action", 0.2)
    action_count = ctx.user.ability_state.get("action_count", 0)
    bonus = init_bonus - (decay_per_action * action_count)
    bonus = max(bonus, 0)  # Never go negative
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["atk"] = 1.0 + bonus


def _h_stat_scale_meteor_marks_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_METEOR_MARKS_PER_TURN: 吸积盘 - +2 meteor marks per turn (ON_TURN_END)"""
    if ctx.user and ctx.user.ability_state is not None:
        marks_per_turn = tag.params.get("marks_per_turn", 2)
        ctx.user.ability_state["meteor_mark_add"] = marks_per_turn


def _h_mark_power_per_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_POWER_PER_METEOR: 坠星/观星 - +15% power per meteor mark"""
    if not ctx.enemy or not ctx.battle:
        return
    # Get meteor mark count on enemy
    meteor_count = ctx.enemy.marks.get("meteor", 0) if ctx.enemy.marks else 0
    bonus_pct_per_mark = tag.params.get("bonus_pct_per_mark", 0.15)
    multiplier = 1.0 + (bonus_pct_per_mark * meteor_count)
    if "power_multiplier" not in ctx.result:
        ctx.result["power_multiplier"] = 1.0
    ctx.result["power_multiplier"] *= multiplier


def _h_mark_freeze_to_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_FREEZE_TO_METEOR: 月牙雪糕 - Freeze = meteor mark"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["freeze_becomes_meteor"] = True


def _h_mark_stack_no_replace(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_STACK_NO_REPLACE: 吟游之弦 - Marks stack (don't replace)"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["mark_stack_additive"] = True


def _h_mark_stack_debuffs(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_STACK_DEBUFFS: 灰色肖像 - Stack enemy debuffs +3"""
    if ctx.enemy and ctx.enemy.ability_state is not None:
        stack_bonus = tag.params.get("stack_bonus", 3)
        ctx.enemy.ability_state["debuff_stack_bonus"] = stack_bonus


def _h_damage_mod_non_stab(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_STAB: 涂鸦 - +50% non-STAB power"""
    if not ctx.user or not ctx.skill:
        return
    # Check if skill is STAB (same type as either of user's types)
    if ctx.skill.type not in (ctx.user.type1, ctx.user.type2):
        bonus_pct = tag.params.get("bonus_pct", 0.5)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_damage_mod_non_light(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_LIGHT: 目空 - +25% non-light power"""
    if not ctx.skill:
        return
    # Type.LIGHT = 18 (or check by name)
    from .types import Type
    if ctx.skill.type != Type.LIGHT:
        bonus_pct = tag.params.get("bonus_pct", 0.25)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_damage_mod_non_weakness(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_WEAKNESS: 绒粉星光 - +100% vs non-weakness"""
    if not ctx.user or not ctx.skill or not ctx.enemy:
        return
    from .types import get_type_effectiveness
    # Check effectiveness
    effectiveness = get_type_effectiveness(ctx.skill.type, ctx.enemy.type1, ctx.enemy.type2)
    if effectiveness <= 1.0:  # Not super-effective
        bonus_pct = tag.params.get("bonus_pct", 1.0)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_damage_mod_pollutant_blood(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_POLLUTANT_BLOOD: 天通地明 - +100% vs pollutant blood (特定敌方血脉)"""
    if ctx.enemy and ctx.enemy.ability_state is not None:
        if ctx.enemy.ability_state.get("blood_type") == "pollutant":
            bonus_pct = tag.params.get("bonus_pct", 1.0)
            if "power_multiplier" not in ctx.result:
                ctx.result["power_multiplier"] = 1.0
            ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_damage_mod_leader_blood(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_LEADER_BLOOD: 月光审判 - +100% vs leader blood (特定敌方血脉)"""
    if ctx.enemy and ctx.enemy.ability_state is not None:
        if ctx.enemy.ability_state.get("blood_type") == "leader":
            bonus_pct = tag.params.get("bonus_pct", 1.0)
            if "power_multiplier" not in ctx.result:
                ctx.result["power_multiplier"] = 1.0
            ctx.result["power_multiplier"] *= (1.0 + bonus_pct)


def _h_damage_resist_same_type(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_RESIST_SAME_TYPE: 偏振 - -40% from same-type attacks"""
    if not ctx.user or not ctx.skill:
        return
    # If enemy uses same type attack, reduce damage
    if ctx.skill.type == ctx.user.type1 or ctx.skill.type == ctx.user.type2:
        resist_pct = tag.params.get("resist_pct", 0.4)
        if "damage_reduction" not in ctx.result:
            ctx.result["damage_reduction"] = 0
        ctx.result["damage_reduction"] += resist_pct


# ── Healing/Sustain (2) ──

def _h_heal_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """HEAL_PER_TURN: 生长 - Recover 12% per turn"""
    if not ctx.user:
        return
    heal_pct = tag.params.get("heal_pct", 0.12)
    heal_amount = int(ctx.user.max_hp * heal_pct)
    ctx.user.hp = min(ctx.user.hp + heal_amount, ctx.user.max_hp)
    if ctx.user.hp != ctx.user.max_hp:
        ctx.logs.append(f"{ctx.user.name} recovered {heal_amount} HP (生长)")


def _h_heal_on_grass_skill(tag: EffectTag, ctx: Ctx) -> None:
    """HEAL_ON_GRASS_SKILL: 深层氧循环 - Recover 15% on grass skill"""
    if not ctx.user or not ctx.skill:
        return
    from src.types import Type
    if ctx.skill.type != Type.GRASS:
        return
    heal_pct = tag.params.get("heal_pct", 0.15)
    heal_amount = int(ctx.user.max_hp * heal_pct)
    ctx.user.hp = min(ctx.user.hp + heal_amount, ctx.user.max_hp)
    ctx.logs.append(f"{ctx.user.name} recovered {heal_amount} HP via grass skill (深层氧循环)")


# ── Energy Cost Modification (1) ──

def _h_skill_cost_reduction_type(tag: EffectTag, ctx: Ctx) -> None:
    """SKILL_COST_REDUCTION_TYPE: 缩壳 - -2 cost on defense skills"""
    if not ctx.skill:
        return
    # Check if skill is defensive type (category == "防御")
    skill_category = getattr(ctx.skill, 'category', None)
    if skill_category != "防御":
        return
    cost_reduction = tag.params.get("cost_reduction", 2)
    if "cost_reduction" not in ctx.result:
        ctx.result["cost_reduction"] = 0
    ctx.result["cost_reduction"] += cost_reduction


# ── Status Application (2) ──

def _h_poison_stat_debuff(tag: EffectTag, ctx: Ctx) -> None:
    """POISON_STAT_DEBUFF: 毒牙 - Poison = -40% spatk/spdef"""
    if not ctx.user:
        return
    # Check if enemy has poison status
    if ctx.user.status != "POISON":
        return
    spatk_reduction = tag.params.get("spatk_reduction", 0.4)
    spdef_reduction = tag.params.get("spdef_reduction", 0.4)
    if "spatk_reduction" not in ctx.result:
        ctx.result["spatk_reduction"] = 0
    if "spdef_reduction" not in ctx.result:
        ctx.result["spdef_reduction"] = 0
    ctx.result["spatk_reduction"] += spatk_reduction
    ctx.result["spdef_reduction"] += spdef_reduction
    ctx.logs.append(f"{ctx.user.name}'s Sp. ATK and Sp. DEF reduced by poison (毒牙)")


def _h_poison_on_skill_apply(tag: EffectTag, ctx: Ctx) -> None:
    """POISON_ON_SKILL_APPLY: 毒腺 - 4-layer poison on low-cost"""
    if not ctx.user or not ctx.skill:
        return
    # Apply poison if skill cost < threshold (default 5)
    cost_threshold = tag.params.get("cost_threshold", 5)
    if ctx.skill.cost >= cost_threshold:
        return
    poison_stacks = tag.params.get("poison_stacks", 4)
    ctx.user.apply_status("POISON", stacks=poison_stacks)
    ctx.logs.append(f"{ctx.user.name} was poisoned by low-cost skill (毒腺)")


# ── Entry Effects (1) ──

def _h_freeze_immunity_and_buff(tag: EffectTag, ctx: Ctx) -> None:
    """FREEZE_IMMUNITY_AND_BUFF: 吉利丁片 - +20% defense, freeze immune"""
    if not ctx.user:
        return
    # Apply defense buff
    def_bonus = tag.params.get("def_bonus", 0.2)
    if "def_buff" not in ctx.user.ability_state:
        ctx.user.ability_state["def_buff"] = 0
    ctx.user.ability_state["def_buff"] += def_bonus
    # Mark as freeze immune
    if "freeze_immune" not in ctx.user.ability_state:
        ctx.user.ability_state["freeze_immune"] = True
    ctx.logs.append(f"{ctx.user.name} gained +{int(def_bonus*100)}% defense and freeze immunity (吉利丁片)")


# ── 通用特性 handler (批量新增) ──

def _h_extra_freeze_on_freeze(tag: EffectTag, ctx: Ctx) -> None:
    """EXTRA_FREEZE_ON_FREEZE: 加个雪球 — 敌方获得冻结时额外+N层"""
    ctx.user.ability_state["extra_freeze"] = tag.params.get("extra", 2)


def _h_faint_no_mp_loss(tag: EffectTag, ctx: Ctx) -> None:
    """FAINT_NO_MP_LOSS: 诈死 — 力竭时不扣MP"""
    ctx.user.ability_state["faint_no_mp_loss"] = True


def _h_on_skill_element_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_BUFF: 使用某系技能后获得buff（助燃/爆燃）"""
    buff = tag.params.get("buff", {})
    if buff:
        _apply_buff(ctx.user, buff)


def _h_on_skill_element_poison(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_POISON: 使用某系技能后敌方中毒（生物碱）"""
    stacks = tag.params.get("stacks", 2)
    ctx.target.poison_stacks += stacks


def _h_on_skill_element_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_COST_REDUCE: 使用某系技能后全能耗-N（浸润/浪潮）"""
    reduce = tag.params.get("reduce", 1)
    for s in ctx.user.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))


def _h_on_skill_element_heal(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_HEAL: 使用某系技能后回血（氧循环）"""
    heal_pct = tag.params.get("heal_pct", 0.1)
    heal = int(ctx.user.hp * heal_pct)
    ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)


def _h_on_skill_element_enemy_energy(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_ENEMY_ENERGY: 使用某系技能后敌方失去能量（碰瓷）"""
    amount = tag.params.get("amount", 2)
    ctx.target.energy = max(0, ctx.target.energy - amount)


def _h_carry_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_SKILL_POWER_BONUS: 携带某条件技能威力+N%（勇敢）
    Store in ability_state for damage calc to pick up.
    """
    ctx.user.ability_state["carry_skill_power_bonus"] = {
        "condition": tag.params.get("condition", "cost_gt"),
        "value": tag.params.get("value", 3),
        "bonus_pct": tag.params.get("bonus_pct", 0.4),
    }


def _h_carry_skill_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_SKILL_COST_REDUCE: 携带某类技能能耗-N"""
    from src.models import SkillCategory as SC
    category = tag.params.get("category", "")
    reduce = tag.params.get("reduce", 2)
    for s in ctx.user.skills:
        match = False
        if category == "defense" and s.category == SC.DEFENSE:
            match = True
        elif category == "attack" and s.category in (SC.PHYSICAL, SC.MAGICAL):
            match = True
        elif category == "status" and s.category == SC.STATUS:
            match = True
        elif not category:
            match = True
        if match:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))


def _h_carry_element_count_buff(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_ELEMENT_COUNT_BUFF: 每携带N个某系技能获得效果（消波块）"""
    from src.skill_db import _TYPE_MAP
    element = tag.params.get("element", "")
    per_skill = tag.params.get("per_skill", {})
    target_type = _TYPE_MAP.get(element)
    count = sum(1 for s in ctx.user.skills if s.skill_type == target_type) if target_type else 0
    if count > 0 and per_skill:
        cost_reduce = per_skill.get("cost_reduce", 0) * count
        target_element = per_skill.get("target_element", "")
        target_skill_type = _TYPE_MAP.get(target_element)
        if cost_reduce and target_skill_type:
            for s in ctx.user.skills:
                if s.skill_type == target_skill_type:
                    s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -cost_reduce))


def _h_on_kill_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_KILL_BUFF: 击败敌方后获得buff（恶魔的晚宴）"""
    if ctx.target.is_fainted:
        buff = tag.params.get("buff", {})
        if buff:
            _apply_buff(ctx.user, buff)


def _h_recoil_damage(tag: EffectTag, ctx: Ctx) -> None:
    """RECOIL_DAMAGE: 受到攻击时反弹固定伤害（刺肤）"""
    power = tag.params.get("power", 50)
    dmg = max(1, int(power))
    if not ctx.target.is_fainted:
        ctx.target.current_hp -= dmg
        if ctx.target.current_hp <= 0:
            ctx.target.current_hp = 0
            from src.models import StatusType
            ctx.target.status = StatusType.FAINTED


def _h_entry_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_BUFF: 入场时获得buff（专注力等）"""
    buff = tag.params.get("buff", {})
    duration = tag.params.get("duration", 0)
    if buff:
        _apply_buff(ctx.user, buff)
    if duration:
        ctx.user.ability_state["entry_buff_duration"] = duration
        ctx.user.ability_state["entry_buff_keys"] = list(buff.keys())


def _h_on_enter_grant_drain(tag: EffectTag, ctx: Ctx) -> None:
    """ON_ENTER_GRANT_DRAIN: 入场时获得吸血（渴求）"""
    pct = tag.params.get("pct", 0.5)
    ctx.user.life_drain_mod += pct


def _h_enemy_all_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_ALL_COST_UP: 在场时敌方全技能能耗+N（冰封）"""
    amount = tag.params.get("amount", 1)
    for s in ctx.target.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))


def _h_entry_freeze_extra(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_FREEZE_EXTRA: 入场时冻结+额外能耗增加（抓到你了）"""
    freeze = tag.params.get("freeze", 2)
    extra_cost_up = tag.params.get("extra_cost_up", 1)
    ctx.target.freeze_stacks += freeze
    if extra_cost_up:
        for s in ctx.target.skills:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, extra_cost_up))


def _h_leave_heal_ally(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_HEAL_ALLY: 离场后替换精灵回血（茶多酚）"""
    heal_pct = tag.params.get("heal_pct", 0.2)
    ctx.result["leave_heal_ally"] = heal_pct


def _h_leave_buff_ally(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_BUFF_ALLY: 离场后替换精灵获得buff（美拉德反应）"""
    buff = tag.params.get("buff", {})
    ctx.result["leave_buff_ally"] = buff


def _h_leave_energy_refill(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_ENERGY_REFILL: 离场时回复能量（快充）"""
    amount = tag.params.get("amount", 10)
    ctx.user.gain_energy(amount)


def _h_energy_regen_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_REGEN_PER_TURN: 回合结束回复能量（养分重吸收）"""
    amount = tag.params.get("amount", 3)
    ctx.user.gain_energy(amount)


def _h_steal_all_enemy_energy(tag: EffectTag, ctx: Ctx) -> None:
    """STEAL_ALL_ENEMY_ENERGY: 回合结束偷取敌方全队能量（毒蘑菇）"""
    amount = tag.params.get("amount", 1)
    enemy_team = ctx.state.team_b if ctx.team == "a" else ctx.state.team_a
    for p in enemy_team:
        if not p.is_fainted:
            stolen = min(p.energy, amount)
            p.energy = max(0, p.energy - amount)
            ctx.user.gain_energy(stolen)


def _h_enemy_switch_debuff(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_SWITCH_DEBUFF: 敌方换人后对入场者施加效果（做噩梦/下黑手）"""
    if tag.params.get("energy_loss"):
        ctx.target.energy = max(0, ctx.target.energy - tag.params["energy_loss"])
    if tag.params.get("poison"):
        ctx.target.poison_stacks += tag.params["poison"]


def _h_enemy_switch_self_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_SWITCH_SELF_COST_REDUCE: 敌方换人时自己全技能能耗-N（珊瑚骨）"""
    reduce = tag.params.get("reduce", 3)
    for s in ctx.user.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))


def _h_on_interrupt_cooldown(tag: EffectTag, ctx: Ctx) -> None:
    """ON_INTERRUPT_COOLDOWN: 打断敌方时被打断技能进入冷却（威慑）"""
    turns = tag.params.get("turns", 2)
    ctx.user.ability_state["interrupt_cooldown_turns"] = turns


def _h_low_cost_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """LOW_COST_SKILL_POWER_BONUS: 能耗≤N的技能威力+M%（挺起胸脯）"""
    ctx.user.ability_state["low_cost_skill_power_bonus"] = {
        "cost_threshold": tag.params.get("cost_threshold", 1),
        "bonus_pct": tag.params.get("bonus_pct", 0.5),
    }


def _h_energy_cost_condition_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_COST_CONDITION_BUFF: 使用能耗为N的技能时获得buff（鼓气/三鼓作气）"""
    cost = tag.params.get("cost", 0)
    buff = tag.params.get("buff", {})
    permanent = tag.params.get("permanent", False)
    if ctx.skill and getattr(ctx.skill, "_base_energy_cost", ctx.skill.energy_cost) == cost:
        if buff:
            _apply_buff(ctx.user, buff)


def _h_enemy_tech_total_power(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_TECH_TOTAL_POWER: 敌方技能总能耗越多自己越强（冰钻）"""
    ctx.user.ability_state["enemy_tech_total_power"] = {
        "bonus_pct_per_cost": tag.params.get("bonus_pct_per_cost", 0.1),
    }


def _h_half_meteor_full_damage(tag: EffectTag, ctx: Ctx) -> None:
    """HALF_METEOR_FULL_DAMAGE: 星陨只消耗一半层数但满伤（守望星）"""
    ctx.user.ability_state["half_meteor_full_damage"] = True


# ── 第五批特性原语 handlers ──

def _h_hit_count_per_poison(tag: EffectTag, ctx: Ctx) -> None:
    """HIT_COUNT_PER_POISON: 侵蚀 — 敌方每有1层中毒，自己连击数+1（仅攻击技能）
    PASSIVE handler: stores flag in ability_state. Actual hit_count bonus applied in _h_damage.
    """
    ctx.user.ability_state["hit_count_per_poison"] = True


def _h_first_action_hit_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_ACTION_HIT_BONUS: 噼啪！ — 入场后首次行动使用次数+1（所有技能类型）
    ON_ENTER: set flag. Actual hit_count bonus applied in _h_damage and cleared after first skill use.
    """
    if ctx.result.get("_is_ability_ctx"):
        # ON_ENTER: set flag
        if not ctx.result.get("skill"):
            ctx.user.ability_state["first_action_bonus"] = True
            return
        # ON_USE_SKILL: clear the flag (bonus already applied in _h_damage)
        if ctx.user.ability_state.get("first_action_bonus"):
            ctx.user.ability_state["first_action_bonus"] = False


def _h_fixed_hit_count_all(tag: EffectTag, ctx: Ctx) -> None:
    """FIXED_HIT_COUNT_ALL: 无差别过滤 — 在场时所有精灵连击数固定为2"""
    ctx.user.ability_state["fixed_hit_count_all"] = tag.params.get("count", 2)


def _h_extra_poison_tick(tag: EffectTag, ctx: Ctx) -> None:
    """EXTRA_POISON_TICK: 复方汤剂 — 回合结束时敌方中毒额外触发1次"""
    if ctx.target.poison_stacks > 0 and not ctx.target.is_fainted:
        dmg = max(1, int(ctx.target.hp * 0.03 * ctx.target.poison_stacks))
        ctx.target.current_hp -= dmg
        if ctx.target.current_hp <= 0:
            ctx.target.current_hp = 0
            from src.models import StatusType
            ctx.target.status = StatusType.FAINTED


def _h_conditional_entry_buff_total_cost(tag: EffectTag, ctx: Ctx) -> None:
    """CONDITIONAL_ENTRY_BUFF_TOTAL_COST: 保守派 — 总技能能耗<4时双防+80%"""
    threshold = tag.params.get("cost_threshold", 4)
    total_cost = sum(getattr(s, "_base_energy_cost", s.energy_cost) for s in ctx.user.skills)
    if total_cost < threshold:
        buff = tag.params.get("buff", {"def": 0.8, "spdef": 0.8})
        _apply_buff(ctx.user, buff)


def _h_conditional_entry_buff_mp(tag: EffectTag, ctx: Ctx) -> None:
    """CONDITIONAL_ENTRY_BUFF_MP: 图书守卫者 — MP=1时双攻+50%  /  构装契约者 — 敌方MP=1时双防+50%"""
    mp_value = tag.params.get("mp_value", 1)
    check_enemy = tag.params.get("check_enemy", False)
    team = ctx.team
    if check_enemy:
        mp = ctx.state.mp_b if team == "a" else ctx.state.mp_a
    else:
        mp = ctx.state.mp_a if team == "a" else ctx.state.mp_b
    if mp == mp_value:
        buff = tag.params.get("buff", {"atk": 0.5, "spatk": 0.5})
        _apply_buff(ctx.user, buff)


def _h_immune_zero_energy_attacker(tag: EffectTag, ctx: Ctx) -> None:
    """IMMUNE_ZERO_ENERGY_ATTACKER: 惊吓 — 能量=0的精灵无法对自己造伤"""
    ctx.user.ability_state["immune_zero_energy_attacker"] = True


def _h_immune_low_cost_attack(tag: EffectTag, ctx: Ctx) -> None:
    """IMMUNE_LOW_COST_ATTACK: 逐魂鸟 — 能耗≤1的攻击技能无法对自己造伤"""
    ctx.user.ability_state["immune_low_cost_attack"] = tag.params.get("cost_threshold", 1)


def _h_entry_self_damage(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_SELF_DAMAGE: 铃兰晚钟 — 首次入场时失去一半当前HP"""
    if ctx.user.ability_state.get("entry_self_damage_triggered"):
        return
    ctx.user.ability_state["entry_self_damage_triggered"] = True
    ctx.user.current_hp = max(1, ctx.user.current_hp // 2)


# ── 第六批特性原语 handlers ──

def _h_specific_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """SPECIFIC_SKILL_POWER_BONUS: 共鸣 — 携带的指定名称技能威力+N"""
    skill_name = tag.params.get("skill_name", "")
    power_bonus = tag.params.get("power_bonus", 20)
    for s in ctx.user.skills:
        if s.name == skill_name:
            if not hasattr(s, "_ability_base_power"):
                s._ability_base_power = s.power
            s.power = s._ability_base_power + power_bonus
            break


def _h_energy_no_cap(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_NO_CAP: 多人宿舍 — 能量可超过上限（无上限）"""
    ctx.user.ability_state["energy_no_cap"] = True


def _h_hp_for_energy(tag: EffectTag, ctx: Ctx) -> None:
    """HP_FOR_ENERGY: 石头大餐 — 能量不足时每缺1点消耗5%HP代替"""
    ctx.user.ability_state["hp_for_energy"] = True


def _h_shuffle_skills_reduce_last(tag: EffectTag, ctx: Ctx) -> None:
    """SHUFFLE_SKILLS_REDUCE_LAST: 盲拧 — 回合开始打乱技能顺序,4号位能耗-4"""
    cost_reduce = tag.params.get("cost_reduce", 4)
    skills = ctx.user.skills
    if len(skills) >= 2:
        random.shuffle(skills)
        # 新4号位(最后一个)能耗-4
        if len(skills) >= 4:
            last = skills[3]
            last.energy_cost = max(0, last.energy_cost - _adjust_cost_delta(ctx.user, cost_reduce))


def _h_weather_conditional_buff(tag: EffectTag, ctx: Ctx) -> None:
    """WEATHER_CONDITIONAL_BUFF: 得寸进尺 — 天气条件下获得buff"""
    weather = tag.params.get("weather", "rain")
    buff = tag.params.get("buff", {})
    if getattr(ctx.state, "weather", None) == weather:
        _apply_buff(ctx.user, buff)


def _h_fainted_allies_buff(tag: EffectTag, ctx: Ctx) -> None:
    """FAINTED_ALLIES_BUFF: 悲悯/悼亡 — 每有1只力竭精灵双攻+N%"""
    buff_per = tag.params.get("buff_per", {"atk": 0.3, "spatk": 0.3})
    scope = tag.params.get("scope", "allies")
    my_team = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    enemy_team = ctx.state.team_b if ctx.team == "a" else ctx.state.team_a
    fainted = sum(1 for p in my_team if p.is_fainted)
    if scope == "all":
        fainted += sum(1 for p in enemy_team if p.is_fainted)
    if fainted > 0:
        scaled_buff = {k: v * fainted for k, v in buff_per.items()}
        _apply_buff(ctx.user, scaled_buff)


def _h_on_super_effective_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SUPER_EFFECTIVE_BUFF: 最好的伙伴 — 造成克制伤害后buff+回能"""
    if not ctx.skill:
        return
    from src.models import get_type_effectiveness
    effectiveness = get_type_effectiveness(ctx.skill.skill_type, ctx.target.pokemon_type)
    if effectiveness > 1.0:
        buff = tag.params.get("buff", {})
        energy = tag.params.get("energy", 0)
        if buff:
            _apply_buff(ctx.user, buff)
        if energy:
            ctx.user.gain_energy(energy)


def _h_enemy_element_diversity_power(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_ELEMENT_DIVERSITY_POWER: 血型吸引 — 敌方每携带1种系别威力+N"""
    power_per_type = tag.params.get("power_per_type", 10)
    unique_types = set()
    for s in ctx.target.skills:
        unique_types.add(s.skill_type)
    bonus = len(unique_types) * power_per_type
    if bonus > 0:
        ctx.user.skill_power_bonus += bonus


def _h_kill_mp_penalty(tag: EffectTag, ctx: Ctx) -> None:
    """KILL_MP_PENALTY: 付给恶魔的赎价 — 击败敌方-1MP / 被击败自己-1MP
    ON_KILL: 敌方额外-1MP. ON_FAINT: 己方额外-1MP.
    """
    # Determine context based on timing (stored by the caller in result)
    timing = ctx.result.get("_ability_timing")
    if timing == "ON_KILL":
        # 击败敌方时，敌方额外-1MP
        if ctx.team == "a":
            ctx.state.mp_b = max(0, ctx.state.mp_b - 1)
        else:
            ctx.state.mp_a = max(0, ctx.state.mp_a - 1)
    elif timing == "ON_FAINT":
        # 被击败时，己方额外-1MP
        if ctx.team == "a":
            ctx.state.mp_a = max(0, ctx.state.mp_a - 1)
        else:
            ctx.state.mp_b = max(0, ctx.state.mp_b - 1)


_HANDLERS: Dict[E, Callable] = {
    E.DAMAGE:                   _h_damage,
    E.SELF_BUFF:                _h_self_buff,
    E.SELF_DEBUFF:              _h_self_debuff,
    E.ENEMY_DEBUFF:             _h_enemy_debuff,
    E.HEAL_HP:                  _h_heal_hp,
    E.HEAL_ENERGY:              _h_heal_energy,
    E.SELF_KO:                  _h_self_ko,
    E.RESET_SKILL_COST:         _h_reset_skill_cost,
    E.ENERGY_ALL_IN:            _h_energy_all_in,
    E.STEAL_ENERGY:             _h_steal_energy,
    E.ENEMY_LOSE_ENERGY:        _h_enemy_lose_energy,
    E.LIFE_DRAIN:               _h_life_drain,
    E.GRANT_LIFE_DRAIN:         _h_grant_life_drain,
    E.POISON:                   _h_poison,
    E.BURN:                     _h_burn,
    E.FREEZE:                   _h_freeze,
    E.LEECH:                    _h_leech,
    E.METEOR:                   _h_meteor,
    E.POISON_MARK:              _h_poison_mark,
    E.MOISTURE_MARK:            _h_moisture_mark,
    E.DRAGON_MARK:              _h_dragon_mark,
    E.WIND_MARK:                _h_wind_mark,
    E.CHARGE_MARK:              _h_charge_mark,
    E.SOLAR_MARK:               _h_solar_mark,
    E.ATTACK_MARK:              _h_attack_mark,
    E.SLOW_MARK:                _h_slow_mark,
    E.SLUGGISH_MARK:            _h_sluggish_mark,
    E.SPIRIT_MARK:              _h_spirit_mark,
    E.METEOR_MARK:              _h_meteor_mark,
    E.THORN_MARK:               _h_thorn_mark,
    E.DISPEL_ENEMY_MARKS:       _h_dispel_enemy_marks,
    E.CONVERT_MARKS_TO_BURN:    _h_convert_marks_to_burn,
    E.DISPEL_MARKS_TO_BURN:     _h_dispel_marks_to_burn,
    E.CONSUME_MARKS_HEAL:       _h_consume_marks_heal,
    E.MARKS_TO_METEOR:          _h_marks_to_meteor,
    E.STEAL_MARKS:              _h_steal_marks,
    E.ENERGY_COST_PER_ENEMY_MARK: _h_energy_cost_per_enemy_mark,
    E.DAMAGE_REDUCTION:         _h_damage_reduction,
    E.FORCE_SWITCH:             _h_force_switch,
    E.FORCE_ENEMY_SWITCH:       _h_force_enemy_switch,
    E.AGILITY:                  _h_agility,
    E.CONVERT_BUFF_TO_POISON:   _h_convert_buff_to_poison,
    E.CONVERT_POISON_TO_MARK:   _h_convert_poison_to_mark,
    E.DISPEL_MARKS:             _h_dispel_marks,
    E.CONDITIONAL_BUFF:         _h_conditional_buff,
    E.ENERGY_COST_DYNAMIC:      _h_energy_cost_dynamic,
    E.POWER_DYNAMIC:            _h_power_dynamic,
    E.PERMANENT_MOD:            _h_permanent_mod,
    E.SKILL_MOD:                _h_skill_mod,
    E.NEXT_ATTACK_MOD:          _h_next_attack_mod,
    E.CLEANSE:                  _h_cleanse,
    E.DISPEL_BUFFS:             _h_dispel_buffs,
    E.DISPEL_DEBUFFS:           _h_dispel_debuffs,
    E.POSITION_BUFF:            _h_position_buff,
    E.DRIVE:                    _h_drive,
    E.PASSIVE_ENERGY_REDUCE:    _h_passive_energy_reduce,
    E.REPLAY_AGILITY:           _h_replay_agility,
    E.AGILITY_COST_SHARE:       _h_agility_cost_share,
    E.ENERGY_COST_ACCUMULATE:   _h_energy_cost_accumulate,
    E.ENEMY_ENERGY_COST_UP:     _h_enemy_energy_cost_up,
    E.MIRROR_DAMAGE:            _h_mirror_damage,
    E.COUNTER_OVERRIDE:         _h_counter_override,
    E.COUNTER_ATTACK:           _h_counter_attack,
    E.COUNTER_STATUS:           _h_counter_status,
    E.COUNTER_DEFENSE:          _h_counter_defense,
    E.WEATHER:                  _h_weather,
    # ── 特性专用原语 ──
    E.ABILITY_COMPUTE:              _h_ability_compute,
    E.ABILITY_INCREMENT_COUNTER:    _h_ability_increment_counter,
    E.TRANSFER_MODS:                _h_transfer_mods,
    E.BURN_NO_DECAY:                _h_burn_no_decay,
    E.POWER_MULTIPLIER_BUFF:        _h_power_multiplier_buff,
    E.THREAT_SPEED_BUFF:            _h_threat_speed_buff,
    E.COUNTER_ACCUMULATE_TRANSFORM: _h_counter_accumulate_transform,
    E.DELAYED_REVIVE:               _h_delayed_revive,
    E.COPY_SWITCH_STATE:            _h_copy_switch_state,
    E.COST_INVERT:                  _h_cost_invert,
    # ── TIER 1 特性原语 ──
    E.COUNTER_SUCCESS_DOUBLE_DAMAGE:     _h_counter_success_double_damage,
    E.COUNTER_SUCCESS_BUFF_PERMANENT:    _h_counter_success_buff_permanent,
    E.COUNTER_SUCCESS_POWER_BONUS:       _h_counter_success_power_bonus,
    E.COUNTER_SUCCESS_COST_REDUCE:       _h_counter_success_cost_reduce,
    E.COUNTER_SUCCESS_SPEED_PRIORITY:    _h_counter_success_speed_priority,
    E.FIRST_STRIKE_POWER_BONUS:          _h_first_strike_power_bonus,
    E.FIRST_STRIKE_HIT_COUNT:            _h_first_strike_hit_count,
    E.FIRST_STRIKE_AGILITY:              _h_first_strike_agility,
    E.AUTO_SWITCH_ON_ZERO_ENERGY:        _h_auto_switch_on_zero_energy,
    E.AUTO_SWITCH_AFTER_ACTION:          _h_auto_switch_after_action,

    # ── TIER 2 Handler Registrations ──
    E.TEAM_SYNERGY_BUG_SWARM_ATTACK:     _h_team_synergy_bug_swarm_attack,
    E.TEAM_SYNERGY_BUG_SWARM_INSPIRE:    _h_team_synergy_bug_swarm_inspire,
    E.TEAM_SYNERGY_BRAVE_IF_BUGS:        _h_team_synergy_brave_if_bugs,
    E.TEAM_SYNERGY_BUG_KILL_AFF:         _h_team_synergy_bug_kill_aff,
    E.STAT_SCALE_DEFENSE_PER_ENERGY:     _h_stat_scale_defense_per_energy,
    E.STAT_SCALE_HITS_PER_HP_LOST:       _h_stat_scale_hits_per_hp_lost,
    E.STAT_SCALE_ATTACK_DECAY:           _h_stat_scale_attack_decay,
    E.STAT_SCALE_METEOR_MARKS_PER_TURN:  _h_stat_scale_meteor_marks_per_turn,
    E.MARK_POWER_PER_METEOR:             _h_mark_power_per_meteor,
    E.MARK_FREEZE_TO_METEOR:             _h_mark_freeze_to_meteor,
    E.MARK_STACK_NO_REPLACE:             _h_mark_stack_no_replace,
    E.MARK_STACK_DEBUFFS:                _h_mark_stack_debuffs,
    E.DAMAGE_MOD_NON_STAB:               _h_damage_mod_non_stab,
    E.DAMAGE_MOD_NON_LIGHT:              _h_damage_mod_non_light,
    E.DAMAGE_MOD_NON_WEAKNESS:           _h_damage_mod_non_weakness,
    E.DAMAGE_MOD_POLLUTANT_BLOOD:        _h_damage_mod_pollutant_blood,
    E.DAMAGE_MOD_LEADER_BLOOD:           _h_damage_mod_leader_blood,
    E.DAMAGE_RESIST_SAME_TYPE:           _h_damage_resist_same_type,
    E.HEAL_PER_TURN:                 _h_heal_per_turn,
    E.HEAL_ON_GRASS_SKILL:           _h_heal_on_grass_skill,
    E.SKILL_COST_REDUCTION_TYPE:     _h_skill_cost_reduction_type,
    E.POISON_STAT_DEBUFF:            _h_poison_stat_debuff,
    E.POISON_ON_SKILL_APPLY:         _h_poison_on_skill_apply,
    E.FREEZE_IMMUNITY_AND_BUFF:      _h_freeze_immunity_and_buff,
    # ── 通用特性原语 (批量新增) ──
    E.EXTRA_FREEZE_ON_FREEZE:        _h_extra_freeze_on_freeze,
    E.FAINT_NO_MP_LOSS:              _h_faint_no_mp_loss,
    E.ON_SKILL_ELEMENT_BUFF:         _h_on_skill_element_buff,
    E.ON_SKILL_ELEMENT_POISON:       _h_on_skill_element_poison,
    E.ON_SKILL_ELEMENT_COST_REDUCE:  _h_on_skill_element_cost_reduce,
    E.ON_SKILL_ELEMENT_HEAL:         _h_on_skill_element_heal,
    E.ON_SKILL_ELEMENT_ENEMY_ENERGY: _h_on_skill_element_enemy_energy,
    E.CARRY_SKILL_POWER_BONUS:       _h_carry_skill_power_bonus,
    E.CARRY_SKILL_COST_REDUCE:       _h_carry_skill_cost_reduce,
    E.CARRY_ELEMENT_COUNT_BUFF:      _h_carry_element_count_buff,
    E.ON_KILL_BUFF:                  _h_on_kill_buff,
    E.RECOIL_DAMAGE:                 _h_recoil_damage,
    E.ENTRY_BUFF:                    _h_entry_buff,
    E.ON_ENTER_GRANT_DRAIN:          _h_on_enter_grant_drain,
    E.ENEMY_ALL_COST_UP:             _h_enemy_all_cost_up,
    E.ENTRY_FREEZE_EXTRA:            _h_entry_freeze_extra,
    E.LEAVE_HEAL_ALLY:               _h_leave_heal_ally,
    E.LEAVE_BUFF_ALLY:               _h_leave_buff_ally,
    E.LEAVE_ENERGY_REFILL:           _h_leave_energy_refill,
    E.ENERGY_REGEN_PER_TURN:         _h_energy_regen_per_turn,
    E.STEAL_ALL_ENEMY_ENERGY:        _h_steal_all_enemy_energy,
    E.ENEMY_SWITCH_DEBUFF:           _h_enemy_switch_debuff,
    E.ENEMY_SWITCH_SELF_COST_REDUCE: _h_enemy_switch_self_cost_reduce,
    E.ON_INTERRUPT_COOLDOWN:         _h_on_interrupt_cooldown,
    E.LOW_COST_SKILL_POWER_BONUS:    _h_low_cost_skill_power_bonus,
    E.ENERGY_COST_CONDITION_BUFF:    _h_energy_cost_condition_buff,
    E.ENEMY_TECH_TOTAL_POWER:        _h_enemy_tech_total_power,
    E.HALF_METEOR_FULL_DAMAGE:       _h_half_meteor_full_damage,
    # ── 第五批特性原语 ──
    E.HIT_COUNT_PER_POISON:          _h_hit_count_per_poison,
    E.FIRST_ACTION_HIT_BONUS:        _h_first_action_hit_bonus,
    E.FIXED_HIT_COUNT_ALL:           _h_fixed_hit_count_all,
    E.EXTRA_POISON_TICK:             _h_extra_poison_tick,
    E.CONDITIONAL_ENTRY_BUFF_TOTAL_COST: _h_conditional_entry_buff_total_cost,
    E.CONDITIONAL_ENTRY_BUFF_MP:     _h_conditional_entry_buff_mp,
    E.IMMUNE_ZERO_ENERGY_ATTACKER:   _h_immune_zero_energy_attacker,
    E.IMMUNE_LOW_COST_ATTACK:        _h_immune_low_cost_attack,
    E.ENTRY_SELF_DAMAGE:             _h_entry_self_damage,
    # ── 第六批特性原语 ──
    E.SPECIFIC_SKILL_POWER_BONUS:    _h_specific_skill_power_bonus,
    E.ENERGY_NO_CAP:                 _h_energy_no_cap,
    E.HP_FOR_ENERGY:                 _h_hp_for_energy,
    E.SHUFFLE_SKILLS_REDUCE_LAST:    _h_shuffle_skills_reduce_last,
    E.WEATHER_CONDITIONAL_BUFF:      _h_weather_conditional_buff,
    E.FAINTED_ALLIES_BUFF:           _h_fainted_allies_buff,
    E.ON_SUPER_EFFECTIVE_BUFF:       _h_on_super_effective_buff,
    E.ENEMY_ELEMENT_DIVERSITY_POWER: _h_enemy_element_diversity_power,
    E.KILL_MP_PENALTY:               _h_kill_mp_penalty,
}

# 特性中部分 handler 与技能略有不同，按 tag type 覆盖
_ABILITY_HANDLER_OVERRIDES: Dict[E, Callable] = {
    E.PERMANENT_MOD:             _h_permanent_mod_ability,
    E.PASSIVE_ENERGY_REDUCE:     _h_passive_energy_reduce_water_ring,
    E.ENEMY_LOSE_ENERGY:         _h_enemy_lose_energy,
    # 特性专用原语（只在 ability_mode 下触发）
    E.ABILITY_COMPUTE:           _h_ability_compute,
    E.ABILITY_INCREMENT_COUNTER: _h_ability_increment_counter,
    E.TRANSFER_MODS:             _h_transfer_mods,
    E.BURN_NO_DECAY:             _h_burn_no_decay,
    E.POWER_MULTIPLIER_BUFF:     _h_power_multiplier_buff,
    E.THREAT_SPEED_BUFF:         _h_threat_speed_buff,
    E.COUNTER_ACCUMULATE_TRANSFORM: _h_counter_accumulate_transform,
    E.DELAYED_REVIVE:            _h_delayed_revive,
    E.COPY_SWITCH_STATE:         _h_copy_switch_state,
    E.COST_INVERT:               _h_cost_invert,
    # ── TIER 1 特性原语（能力模式） ──
    E.COUNTER_SUCCESS_DOUBLE_DAMAGE:     _h_counter_success_double_damage,
    E.COUNTER_SUCCESS_BUFF_PERMANENT:    _h_counter_success_buff_permanent,
    E.COUNTER_SUCCESS_POWER_BONUS:       _h_counter_success_power_bonus,
    E.COUNTER_SUCCESS_COST_REDUCE:       _h_counter_success_cost_reduce,
    E.COUNTER_SUCCESS_SPEED_PRIORITY:    _h_counter_success_speed_priority,
    E.FIRST_STRIKE_POWER_BONUS:          _h_first_strike_power_bonus,
    E.FIRST_STRIKE_HIT_COUNT:            _h_first_strike_hit_count,
    E.FIRST_STRIKE_AGILITY:              _h_first_strike_agility,
    E.AUTO_SWITCH_ON_ZERO_ENERGY:        _h_auto_switch_on_zero_energy,
    E.AUTO_SWITCH_AFTER_ACTION:          _h_auto_switch_after_action,

    # ── TIER 2 Handler Registrations (Ability Overrides) ──
    E.TEAM_SYNERGY_BUG_SWARM_ATTACK:     _h_team_synergy_bug_swarm_attack,
    E.TEAM_SYNERGY_BUG_SWARM_INSPIRE:    _h_team_synergy_bug_swarm_inspire,
    E.TEAM_SYNERGY_BRAVE_IF_BUGS:        _h_team_synergy_brave_if_bugs,
    E.TEAM_SYNERGY_BUG_KILL_AFF:         _h_team_synergy_bug_kill_aff,
    E.STAT_SCALE_DEFENSE_PER_ENERGY:     _h_stat_scale_defense_per_energy,
    E.STAT_SCALE_HITS_PER_HP_LOST:       _h_stat_scale_hits_per_hp_lost,
    E.STAT_SCALE_ATTACK_DECAY:           _h_stat_scale_attack_decay,
    E.STAT_SCALE_METEOR_MARKS_PER_TURN:  _h_stat_scale_meteor_marks_per_turn,
    E.MARK_POWER_PER_METEOR:             _h_mark_power_per_meteor,
    E.MARK_FREEZE_TO_METEOR:             _h_mark_freeze_to_meteor,
    E.MARK_STACK_NO_REPLACE:             _h_mark_stack_no_replace,
    E.MARK_STACK_DEBUFFS:                _h_mark_stack_debuffs,
    E.DAMAGE_MOD_NON_STAB:               _h_damage_mod_non_stab,
    E.DAMAGE_MOD_NON_LIGHT:              _h_damage_mod_non_light,
    E.DAMAGE_MOD_NON_WEAKNESS:           _h_damage_mod_non_weakness,
    E.DAMAGE_MOD_POLLUTANT_BLOOD:        _h_damage_mod_pollutant_blood,
    E.DAMAGE_MOD_LEADER_BLOOD:           _h_damage_mod_leader_blood,
    E.DAMAGE_RESIST_SAME_TYPE:           _h_damage_resist_same_type,
    E.HEAL_PER_TURN:                 _h_heal_per_turn,
    E.HEAL_ON_GRASS_SKILL:           _h_heal_on_grass_skill,
    E.SKILL_COST_REDUCTION_TYPE:     _h_skill_cost_reduction_type,
    E.POISON_STAT_DEBUFF:            _h_poison_stat_debuff,
    E.POISON_ON_SKILL_APPLY:         _h_poison_on_skill_apply,
    E.FREEZE_IMMUNITY_AND_BUFF:      _h_freeze_immunity_and_buff,
    # ── 通用特性原语 (批量新增) ──
    E.EXTRA_FREEZE_ON_FREEZE:        _h_extra_freeze_on_freeze,
    E.FAINT_NO_MP_LOSS:              _h_faint_no_mp_loss,
    E.ON_SKILL_ELEMENT_BUFF:         _h_on_skill_element_buff,
    E.ON_SKILL_ELEMENT_POISON:       _h_on_skill_element_poison,
    E.ON_SKILL_ELEMENT_COST_REDUCE:  _h_on_skill_element_cost_reduce,
    E.ON_SKILL_ELEMENT_HEAL:         _h_on_skill_element_heal,
    E.ON_SKILL_ELEMENT_ENEMY_ENERGY: _h_on_skill_element_enemy_energy,
    E.CARRY_SKILL_POWER_BONUS:       _h_carry_skill_power_bonus,
    E.CARRY_SKILL_COST_REDUCE:       _h_carry_skill_cost_reduce,
    E.CARRY_ELEMENT_COUNT_BUFF:      _h_carry_element_count_buff,
    E.ON_KILL_BUFF:                  _h_on_kill_buff,
    E.RECOIL_DAMAGE:                 _h_recoil_damage,
    E.ENTRY_BUFF:                    _h_entry_buff,
    E.ON_ENTER_GRANT_DRAIN:          _h_on_enter_grant_drain,
    E.ENEMY_ALL_COST_UP:             _h_enemy_all_cost_up,
    E.ENTRY_FREEZE_EXTRA:            _h_entry_freeze_extra,
    E.LEAVE_HEAL_ALLY:               _h_leave_heal_ally,
    E.LEAVE_BUFF_ALLY:               _h_leave_buff_ally,
    E.LEAVE_ENERGY_REFILL:           _h_leave_energy_refill,
    E.ENERGY_REGEN_PER_TURN:         _h_energy_regen_per_turn,
    E.STEAL_ALL_ENEMY_ENERGY:        _h_steal_all_enemy_energy,
    E.ENEMY_SWITCH_DEBUFF:           _h_enemy_switch_debuff,
    E.ENEMY_SWITCH_SELF_COST_REDUCE: _h_enemy_switch_self_cost_reduce,
    E.ON_INTERRUPT_COOLDOWN:         _h_on_interrupt_cooldown,
    E.LOW_COST_SKILL_POWER_BONUS:    _h_low_cost_skill_power_bonus,
    E.ENERGY_COST_CONDITION_BUFF:    _h_energy_cost_condition_buff,
    E.ENEMY_TECH_TOTAL_POWER:        _h_enemy_tech_total_power,
    E.HALF_METEOR_FULL_DAMAGE:       _h_half_meteor_full_damage,
    # ── 第五批特性原语 ──
    E.HIT_COUNT_PER_POISON:          _h_hit_count_per_poison,
    E.FIRST_ACTION_HIT_BONUS:        _h_first_action_hit_bonus,
    E.FIXED_HIT_COUNT_ALL:           _h_fixed_hit_count_all,
    E.EXTRA_POISON_TICK:             _h_extra_poison_tick,
    E.CONDITIONAL_ENTRY_BUFF_TOTAL_COST: _h_conditional_entry_buff_total_cost,
    E.CONDITIONAL_ENTRY_BUFF_MP:     _h_conditional_entry_buff_mp,
    E.IMMUNE_ZERO_ENERGY_ATTACKER:   _h_immune_zero_energy_attacker,
    E.IMMUNE_LOW_COST_ATTACK:        _h_immune_low_cost_attack,
    E.ENTRY_SELF_DAMAGE:             _h_entry_self_damage,
    # ── 第六批特性原语 ──
    E.SPECIFIC_SKILL_POWER_BONUS:    _h_specific_skill_power_bonus,
    E.ENERGY_NO_CAP:                 _h_energy_no_cap,
    E.HP_FOR_ENERGY:                 _h_hp_for_energy,
    E.SHUFFLE_SKILLS_REDUCE_LAST:    _h_shuffle_skills_reduce_last,
    E.WEATHER_CONDITIONAL_BUFF:      _h_weather_conditional_buff,
    E.FAINTED_ALLIES_BUFF:           _h_fainted_allies_buff,
    E.ON_SUPER_EFFECTIVE_BUFF:       _h_on_super_effective_buff,
    E.ENEMY_ELEMENT_DIVERSITY_POWER: _h_enemy_element_diversity_power,
    E.KILL_MP_PENALTY:               _h_kill_mp_penalty,
}


def _apply_tag(tag: EffectTag, ctx: Ctx, ability_mode: bool = False) -> None:
    """统一效果分发入口。ability_mode=True 时优先用特性专属 handler。"""
    if ability_mode:
        handler = _ABILITY_HANDLER_OVERRIDES.get(tag.type) or _HANDLERS.get(tag.type)
    else:
        handler = _HANDLERS.get(tag.type)
    if handler:
        handler(tag, ctx)


# ============================================================
#  效果执行引擎
# ============================================================

class EffectExecutor:
    """
    无状态的效果执行器。所有方法均为 @staticmethod。
    """

    # ────────────────────────────────────────
    #  主入口: 执行技能
    # ────────────────────────────────────────

    @staticmethod
    def execute_skill(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects,
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """
        执行技能的全部效果。
        自动检测 effects 是 List[SkillEffect] 还是 List[EffectTag]，分别走新/旧路径。
        """
        if effects and isinstance(effects[0], SkillEffect):
            return EffectExecutor._execute_skill_se(
                state, user, target, skill, effects,
                is_first=is_first, enemy_skill=enemy_skill, team=team,
            )
        # ── 旧格式: List[EffectTag] ──
        return EffectExecutor._execute_skill_legacy(
            state, user, target, skill, effects,
            is_first=is_first, enemy_skill=enemy_skill, team=team,
        )

    @staticmethod
    def _execute_skill_legacy(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects: List[EffectTag],
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """
        执行技能的全部效果（非应对部分）。
        应对容器（COUNTER_*）被收集到 result["counter_effects"]，
        由 battle.py 在之后调用 execute_counter 处理。
        """
        result = {
            "damage": 0,
            "interrupted": False,
            "countered": False,
            "force_switch": False,
            "force_enemy_switch": False,
            "counter_effects": [],
            "_user_hp_start": user.current_hp,
            "_target_hp_start": target.current_hp,
        }
        ctx = Ctx(
            state=state, user=user, target=target, skill=skill,
            result=result, is_first=is_first, team=team, enemy_skill=enemy_skill,
        )
        damage_tags: List[EffectTag] = []
        post_use_tags: List[EffectTag] = []
        for tag in effects:
            if tag.params.get("when") == "post_use":
                post_use_tags.append(tag)
                continue
            if tag.type == E.DAMAGE:
                damage_tags.append(tag)
                continue
            _apply_tag(tag, ctx)
        for tag in damage_tags:
            _apply_tag(tag, ctx)
        total_drain = result.get("_life_drain_pct", 0.0) + getattr(user, "life_drain_mod", 0.0)
        if total_drain > 0 and result.get("damage", 0) > 0:
            heal = int(result["damage"] * total_drain)
            user.current_hp = min(user.hp, user.current_hp + heal)
        for tag in post_use_tags:
            _apply_tag(tag, ctx)
        for buff in result.pop("_post_use_self_buffs", []):
            _apply_buff(user, buff)
        if result.get("_consume_next_attack_mod"):
            user.next_attack_power_bonus = 0
            user.next_attack_power_pct = 0.0
        return result

    # ────────────────────────────────────────
    #  新格式: SkillEffect 按阶段执行
    # ────────────────────────────────────────

    @staticmethod
    def _execute_skill_se(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects: List[SkillEffect],
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """按 SkillTiming 阶段顺序执行技能效果。"""
        result = {
            "damage": 0,
            "interrupted": False,
            "countered": False,
            "force_switch": False,
            "force_enemy_switch": False,
            "counter_effects": [],
            "_user_hp_start": user.current_hp,
            "_target_hp_start": target.current_hp,
        }
        ctx = Ctx(
            state=state, user=user, target=target, skill=skill,
            result=result, is_first=is_first, team=team, enemy_skill=enemy_skill,
        )

        # 按 filter 中的 per 缩放: 注入到 ctx 上供 handler 使用
        # 缩放因子在 PRE_USE 阶段计算一次

        # ── 阶段1: PRE_USE ──
        for se in effects:
            if se.timing == SkillTiming.PRE_USE and _check_skill_filter(se.filter, ctx):
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 阶段2: IF (运行时条件 — 在伤害前，影响威力/连击数) ──
        for se in effects:
            if se.timing == SkillTiming.IF and _check_skill_filter(se.filter, ctx):
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 阶段3: ON_USE (主体伤害/状态) ──
        #    DAMAGE 标签延后到其他 ON_USE 标签之后，确保威力修正先生效
        on_use_damage = []
        for se in effects:
            if se.timing == SkillTiming.ON_USE:
                for tag in se.effects:
                    if tag.type == E.DAMAGE:
                        on_use_damage.append(tag)
                    else:
                        _apply_tag(tag, ctx)
        for tag in on_use_damage:
            _apply_tag(tag, ctx)

        # ── 阶段4: ON_HIT (仅有伤害时) ──
        if result.get("damage", 0) > 0:
            for se in effects:
                if se.timing == SkillTiming.ON_HIT and _check_skill_filter(se.filter, ctx):
                    for tag in se.effects:
                        _apply_tag(tag, ctx)

        # ── 阶段5: ON_COUNTER (收集，由 battle.py 在应对时执行) ──
        for se in effects:
            if se.timing == SkillTiming.ON_COUNTER:
                result["counter_effects"].append(se)

        # ── 阶段6: POST_USE ──
        for se in effects:
            if se.timing == SkillTiming.POST_USE:
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 吸血结算 ──
        total_drain = result.get("_life_drain_pct", 0.0) + getattr(user, "life_drain_mod", 0.0)
        if total_drain > 0 and result.get("damage", 0) > 0:
            heal = int(result["damage"] * total_drain)
            user.current_hp = min(user.hp, user.current_hp + heal)

        # ── 后处理 ──
        for buff in result.pop("_post_use_self_buffs", []):
            _apply_buff(user, buff)
        if result.get("_consume_next_attack_mod"):
            user.next_attack_power_bonus = 0
            user.next_attack_power_pct = 0.0

        return result

    # ────────────────────────────────────────
    #  新格式: 应对效果执行
    # ────────────────────────────────────────

    @staticmethod
    def execute_counter_se(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        counter_se: SkillEffect,
        enemy_skill: "Skill",
        damage: int,
        team: str = "a",
    ) -> Optional[Dict]:
        """
        执行新格式应对效果。
        counter_se 是 SkillEffect(timing=ON_COUNTER, filter={"category": ...})
        """
        from src.models import SkillCategory

        result = {
            "final_damage": damage,
            "interrupted": False,
            "force_switch": False,
            "force_enemy_switch": False,
        }

        # 按 filter["category"] 匹配
        category = counter_se.filter.get("category", "")
        matched = False
        if category == "attack":
            matched = enemy_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL)
        elif category == "status":
            matched = enemy_skill.category == SkillCategory.STATUS
        elif category == "defense":
            matched = enemy_skill.category == SkillCategory.DEFENSE
        elif not category:
            # 无类别限制 = 全匹配
            matched = True

        if not matched:
            return None

        # 应对成功：更新计数
        if team == "a":
            state.counter_count_a += 1
        else:
            state.counter_count_b += 1

        ctx = Ctx(
            state=state, user=user, target=target, skill=skill,
            result=result, team=team, enemy_skill=enemy_skill, damage=damage,
        )

        for tag in counter_se.effects:
            if tag.type == E.INTERRUPT:
                result["interrupted"] = True
            elif tag.type == E.FORCE_SWITCH:
                result["force_switch"] = True
            elif tag.type == E.FORCE_ENEMY_SWITCH:
                result["force_enemy_switch"] = True
            elif tag.type == E.PASSIVE_ENERGY_REDUCE:
                _h_passive_energy_reduce_water_ring(tag, ctx)
            else:
                _apply_tag(tag, ctx)

        # 如果应对中有伤害/威力修正，重新计算伤害
        if any(key in result for key in ("_power_bonus", "_power_mult", "_hit_count_bonus", "_hit_count_mult")):
            from src.battle import DamageCalculator
            weather = getattr(state, "weather", None)
            power = (
                skill.power
                + user.skill_power_bonus
                + user.next_attack_power_bonus
                + result.get("_power_bonus", 0)
            )
            power_mult = (
                1.0
                + user.skill_power_pct_mod
                + user.next_attack_power_pct
                + (result.get("_power_mult", 1.0) - 1.0)
            )
            if power_mult != 1.0:
                power = int(power * power_mult)
            hit_count = max(
                1,
                int(
                    (skill.hit_count + user.hit_count_mod + result.get("_hit_count_bonus", 0))
                    * result.get("_hit_count_mult", 1.0)
                ),
            )
            result["final_damage"] = DamageCalculator.calculate(
                user, target, skill,
                power_override=power, weather=weather, hit_count_override=hit_count,
            )

        return result

    # ────────────────────────────────────────
    #  应对效果执行 (旧格式)
    # ────────────────────────────────────────

    @staticmethod
    def execute_counter(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        counter_tag,
        enemy_skill: "Skill",
        damage: int,
        team: str = "a",
    ) -> Optional[Dict]:
        """
        执行应对效果。自动检测新格式（SkillEffect）或旧格式（EffectTag）。
        """
        if isinstance(counter_tag, SkillEffect):
            return EffectExecutor.execute_counter_se(
                state, user, target, skill, counter_tag, enemy_skill, damage, team,
            )
        # ── 旧格式: EffectTag 容器 ──
        from src.models import SkillCategory

        result = {
            "final_damage": damage,
            "interrupted": False,
            "force_switch": False,
            "force_enemy_switch": False,
        }

        # 检查应对类型是否匹配
        matched = False
        if counter_tag.type == E.COUNTER_ATTACK:
            matched = enemy_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL)
        elif counter_tag.type == E.COUNTER_STATUS:
            matched = enemy_skill.category == SkillCategory.STATUS
        elif counter_tag.type == E.COUNTER_DEFENSE:
            matched = enemy_skill.category == SkillCategory.DEFENSE

        if not matched:
            return None

        # 应对成功：更新计数
        if team == "a":
            state.counter_count_a += 1
        else:
            state.counter_count_b += 1

        # 执行子效果（走同一套 _apply_tag）
        ctx = Ctx(
            state=state, user=user, target=target, skill=skill,
            result=result, team=team, enemy_skill=enemy_skill, damage=damage,
        )
        for sub in counter_tag.sub_effects:
            if sub.type == E.INTERRUPT:
                result["interrupted"] = True
            elif sub.type == E.FORCE_SWITCH:
                result["force_switch"] = True
            elif sub.type == E.FORCE_ENEMY_SWITCH:
                result["force_enemy_switch"] = True
            elif sub.type == E.PASSIVE_ENERGY_REDUCE:
                # 水环：应对时全技能能耗-N
                _h_passive_energy_reduce_water_ring(sub, ctx)
            else:
                _apply_tag(sub, ctx)

        if any(key in result for key in ("_power_bonus", "_power_mult", "_hit_count_bonus", "_hit_count_mult")):
            from src.battle import DamageCalculator
            weather = getattr(state, "weather", None)
            power = (
                skill.power
                + user.skill_power_bonus
                + user.next_attack_power_bonus
                + result.get("_power_bonus", 0)
            )
            power_mult = (
                1.0
                + user.skill_power_pct_mod
                + user.next_attack_power_pct
                + (result.get("_power_mult", 1.0) - 1.0)
            )
            if power_mult != 1.0:
                power = int(power * power_mult)
            hit_count = max(
                1,
                int(
                    (skill.hit_count + user.hit_count_mod + result.get("_hit_count_bonus", 0))
                    * result.get("_hit_count_mult", 1.0)
                ),
            )
            result["final_damage"] = DamageCalculator.calculate(
                user,
                target,
                skill,
                power_override=power,
                weather=weather,
                hit_count_override=hit_count,
            )

        return result

    # ────────────────────────────────────────
    #  特性触发
    # ────────────────────────────────────────

    @staticmethod
    def execute_ability(
        state: "BattleState",
        pokemon: "Pokemon",
        enemy: "Pokemon",
        timing: Timing,
        ability_effects: List[AbilityEffect],
        team: str = "a",
        context: Optional[Dict] = None,
    ) -> Dict:
        """在指定时机触发特性效果。"""
        result = {"triggered": False, "damage_reduction": 0}
        context = context or {}

        for ae in ability_effects:
            if ae.timing != timing:
                continue

            context["_ability_filter"] = ae.filter
            if not EffectExecutor._check_ability_filter(ae, pokemon, enemy, state, team, context):
                continue

            result["triggered"] = True

            # 通用效果：走同一套 _apply_tag（ability_mode=True）
            # 用 context 充当 result，以便 ability 内部传递信息
            ctx = Ctx(
                state=state, user=pokemon, target=enemy, skill=None,
                result=context, team=team,
            )
            # 标记为 ability 上下文
            context["_is_ability_ctx"] = True
            context["_ability_timing"] = timing.name

            for tag in ae.effects:
                _apply_tag(tag, ctx, ability_mode=True)
                if tag.type == E.DAMAGE_REDUCTION:
                    result["damage_reduction"] = tag.params.get("pct", 0)

        return result

    # ────────────────────────────────────────
    #  迅捷入场
    # ────────────────────────────────────────

    @staticmethod
    def execute_agility_entry(
        state: "BattleState",
        pokemon: "Pokemon",
        enemy: "Pokemon",
        team: str = "a",
    ) -> None:
        """入场时执行带迅捷标记的技能"""
        for skill in pokemon.skills:
            if not getattr(skill, "effects", None):
                if skill.agility and pokemon.energy >= skill.energy_cost:
                    _execute_agility_old(pokemon, enemy, skill)
                continue

            has_agility = any(e.type == E.AGILITY for e in _iter_flat_tags_static(skill.effects))
            if has_agility and pokemon.energy >= skill.energy_cost:
                pokemon.energy -= skill.energy_cost
                EffectExecutor.execute_skill(
                    state, pokemon, enemy, skill, skill.effects,
                    is_first=True, team=team,
                )
                break  # 只触发第一个迅捷技能

    # ────────────────────────────────────────
    #  传动系统
    # ────────────────────────────────────────

    @staticmethod
    def execute_drive(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        drive_value: int,
        team: str = "a",
    ) -> None:
        """执行传动：触发后方 N 位技能的被动效果。"""
        skill_idx = _find_skill_index(user, skill)
        if skill_idx < 0:
            return

        n_skills = len(user.skills)
        if n_skills == 0:
            return

        target_idx = (skill_idx + drive_value) % n_skills
        target_skill = user.skills[target_idx]

        if not getattr(target_skill, "effects", None):
            return

        for tag in _iter_flat_tags_static(target_skill.effects):
            if tag.type == E.PASSIVE_ENERGY_REDUCE:
                reduce = tag.params.get("reduce", 0)
                rng = tag.params.get("range", "self")
                if rng == "self":
                    target_skill.energy_cost = max(
                        0,
                        target_skill.energy_cost + _adjust_cost_delta(user, -reduce),
                    )
                elif rng == "adjacent":
                    for offset in [-1, 1]:
                        adj_idx = (target_idx + offset) % n_skills
                        user.skills[adj_idx].energy_cost = max(
                            0,
                            user.skills[adj_idx].energy_cost + _adjust_cost_delta(user, -reduce),
                        )
            elif tag.type == E.PERMANENT_MOD:
                if tag.params.get("trigger") == "per_position_change":
                    target_skill.power += tag.params.get("delta", 0)

    # ────────────────────────────────────────
    #  内部: 特性过滤
    # ────────────────────────────────────────

    @staticmethod
    def _check_ability_filter(
        ae: AbilityEffect,
        pokemon: "Pokemon",
        enemy: "Pokemon",
        state: "BattleState",
        team: str,
        context: Dict,
    ) -> bool:
        f = ae.filter
        if not f:
            return True

        if "element" in f:
            skill = context.get("skill")
            if not skill:
                return False
            from src.skill_db import _TYPE_MAP
            elements = f["element"]
            if not isinstance(elements, (list, tuple, set)):
                elements = [elements]
            expected_types = {_TYPE_MAP.get(el) for el in elements}
            if skill.skill_type not in expected_types:
                return False

        if f.get("condition") == "skill_element_not_enemy_type":
            skill = context.get("skill")
            if skill and skill.skill_type != enemy.pokemon_type:
                return True
            return False

        if f.get("condition") == "energy_zero":
            return pokemon.energy <= 0

        if f.get("condition") == "energy_not_zero":
            return pokemon.energy > 0

        if "positions" in f:
            skill = context.get("skill")
            if skill:
                idx = _find_skill_index(pokemon, skill)
                if idx not in f["positions"]:
                    return False
            else:
                # 位置型被动特性会在没有具体 skill 的时机触发，
                # 由 handler 依据 filter 自行选择目标技能。
                pass

        return True




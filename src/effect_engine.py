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

from src.effect_models import E, EffectTag, Timing, AbilityEffect

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
    """应用正向属性修改"""
    if "atk" in params:
        pokemon.atk_mod += params["atk"]
    if "def" in params:
        pokemon.def_mod += params["def"]
    if "spatk" in params:
        pokemon.spatk_mod += params["spatk"]
    if "spdef" in params:
        pokemon.spdef_mod += params["spdef"]
    if "speed" in params:
        pokemon.speed_mod += params["speed"]
    if "all_atk" in params:
        pokemon.atk_mod += params["all_atk"]
        pokemon.spatk_mod += params["all_atk"]
    if "all_def" in params:
        pokemon.def_mod += params["all_def"]
        pokemon.spdef_mod += params["all_def"]


def _apply_debuff(pokemon: "Pokemon", params: Dict) -> None:
    """应用负向属性修改（params 中的值为正，自动取反）"""
    if "atk" in params:
        pokemon.atk_mod -= params["atk"]
    if "def" in params:
        pokemon.def_mod -= params["def"]
    if "spatk" in params:
        pokemon.spatk_mod -= params["spatk"]
    if "spdef" in params:
        pokemon.spdef_mod -= params["spdef"]
    if "speed" in params:
        pokemon.speed_mod -= params["speed"]
    if "all_atk" in params:
        pokemon.atk_mod -= params["all_atk"]
        pokemon.spatk_mod -= params["all_atk"]
    if "all_def" in params:
        pokemon.def_mod -= params["all_def"]
        pokemon.spdef_mod -= params["all_def"]


def _apply_permanent_mod(user: "Pokemon", skill: "Skill", params: Dict) -> None:
    """应用永久修改（能耗/威力）"""
    target = params.get("target", "")
    delta = params.get("delta", 0)
    trigger = params.get("trigger", "")

    # per_position_change 由 execute_drive 单独处理
    if trigger == "per_position_change":
        return

    if target == "cost":
        skill.energy_cost = max(0, skill.energy_cost + delta)
    elif target == "power":
        skill.power = max(0, skill.power + delta)


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
    from src.battle import DamageCalculator
    skill = ctx.skill
    power = skill.power + ctx.result.get("_power_bonus", 0)
    power_mult = ctx.result.get("_power_mult", 1.0)
    if power_mult != 1.0:
        power = int(power * power_mult)
    if power > 0 and not ctx.target.is_fainted:
        dmg = DamageCalculator.calculate(ctx.user, ctx.target, skill, power_override=power)
        ctx.result["damage"] = ctx.result.get("damage", 0) + dmg


def _h_self_buff(tag: EffectTag, ctx: Ctx) -> None:
    _apply_buff(ctx.user, tag.params)


def _h_enemy_debuff(tag: EffectTag, ctx: Ctx) -> None:
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
    else:
        ctx.target.energy = max(0, ctx.target.energy - tag.params.get("amount", 1))


def _h_life_drain(tag: EffectTag, ctx: Ctx) -> None:
    pct = tag.params.get("pct", 0)
    heal = int(ctx.result.get("damage", 0) * pct)
    ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)


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
    marks["moisture_mark"] = marks.get("moisture_mark", 0) + tag.params.get("stacks", 1)


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
    for attr in ["atk_mod", "def_mod", "spatk_mod", "spdef_mod", "speed_mod"]:
        v = getattr(ctx.target, attr, 0)
        if v > 0:
            total_buff += int(v * 10)
            setattr(ctx.target, attr, 0)
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
    elif condition == "per_poison":
        stacks = ctx.target.poison_stacks
        bonus = tag.params.get("bonus_per_stack", 0) * stacks
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + bonus
    elif condition == "counter":
        # 应对时威力倍率（偷袭3倍），在 execute_counter 中处理
        mult = tag.params.get("multiplier", 1.0)
        from src.battle import DamageCalculator
        new_power = int(ctx.skill.power * mult)
        ctx.result["final_damage"] = DamageCalculator.calculate(
            ctx.user, ctx.target, ctx.skill, power_override=new_power
        )


def _h_permanent_mod(tag: EffectTag, ctx: Ctx) -> None:
    _apply_permanent_mod(ctx.user, ctx.skill, tag.params)


def _h_position_buff(tag: EffectTag, ctx: Ctx) -> None:
    positions = tag.params.get("positions", [])
    buff = tag.params.get("buff", {})
    skill_idx = _find_skill_index(ctx.user, ctx.skill)
    if skill_idx in positions:
        _apply_buff(ctx.user, buff)


def _h_drive(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_drive_value"] = tag.params.get("value", 1)


def _h_passive_energy_reduce(tag: EffectTag, ctx: Ctx) -> None:
    pass  # 由 execute_drive 处理


def _h_replay_agility(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_replay_agility"] = True


def _h_agility_cost_share(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_agility_cost_share"] = tag.params.get("divisor", 2)


def _h_energy_cost_accumulate(tag: EffectTag, ctx: Ctx) -> None:
    delta = tag.params.get("delta", 1)
    ctx.skill.energy_cost += delta


def _h_enemy_energy_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    from src.models import SkillCategory as SC
    amount = tag.params.get("amount", 0)
    filt = tag.params.get("filter", "all")
    for s in ctx.target.skills:
        if filt == "attack" and s.category in (SC.PHYSICAL, SC.MAGICAL):
            s.energy_cost += amount
        elif filt == "all":
            s.energy_cost += amount


def _h_mirror_damage(tag: EffectTag, ctx: Ctx) -> None:
    """
    反弹伤害（听桥）：将攻击方对自己造成的伤害值原样反弹给攻击方。
    ctx.damage 是攻击方本次攻击造成的伤害值（在 execute_counter 中传入）。
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
            s.energy_cost = max(0, s.energy_cost - reduce)


def _h_permanent_mod_ability(tag: EffectTag, ctx: Ctx) -> None:
    """特性中的永久修改（身经百练）"""
    per_counter = tag.params.get("per_counter", 0)
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
            if elements:
                type_matched = any(_TYPE_MAP.get(el) == s.skill_type for el in elements)
                if type_matched:
                    s.power = int(s.power * (1.0 + bonus_pct))
    else:
        _apply_permanent_mod(ctx.user, ctx.skill, tag.params)


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
                    if not any(e.type == E.AGILITY for e in s.effects):
                        s.effects.insert(0, EffectTag(E.AGILITY))


def _h_ability_increment_counter(tag: EffectTag, ctx: Ctx) -> None:
    """ABILITY_INCREMENT_COUNTER: 海豹船长计数+1"""
    if ctx.team == "a":
        ctx.state.counter_count_a += 1
    else:
        ctx.state.counter_count_b += 1


def _h_transfer_mods(tag: EffectTag, ctx: Ctx) -> None:
    """TRANSFER_MODS: 洁癖离场时保存属性修正，存入 result 供 battle.py 传递"""
    pokemon = ctx.user
    ctx.result["transfer_mods"] = {
        "atk_mod":   pokemon.atk_mod,
        "def_mod":   pokemon.def_mod,
        "spatk_mod": pokemon.spatk_mod,
        "spdef_mod": pokemon.spdef_mod,
        "speed_mod": pokemon.speed_mod,
    }


def _h_burn_no_decay(tag: EffectTag, ctx: Ctx) -> None:
    """BURN_NO_DECAY: 标记煤渣草在场，本回合灼烧不衰减"""
    ctx.result["burn_no_decay"] = True


# ── 注册表 ──
_HANDLERS: Dict[E, Callable] = {
    E.DAMAGE:                   _h_damage,
    E.SELF_BUFF:                _h_self_buff,
    E.ENEMY_DEBUFF:             _h_enemy_debuff,
    E.HEAL_HP:                  _h_heal_hp,
    E.HEAL_ENERGY:              _h_heal_energy,
    E.STEAL_ENERGY:             _h_steal_energy,
    E.ENEMY_LOSE_ENERGY:        _h_enemy_lose_energy,
    E.LIFE_DRAIN:               _h_life_drain,
    E.POISON:                   _h_poison,
    E.BURN:                     _h_burn,
    E.FREEZE:                   _h_freeze,
    E.LEECH:                    _h_leech,
    E.METEOR:                   _h_meteor,
    E.POISON_MARK:              _h_poison_mark,
    E.MOISTURE_MARK:            _h_moisture_mark,
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
    # ── 特性专用原语 ──
    E.ABILITY_COMPUTE:              _h_ability_compute,
    E.ABILITY_INCREMENT_COUNTER:    _h_ability_increment_counter,
    E.TRANSFER_MODS:                _h_transfer_mods,
    E.BURN_NO_DECAY:                _h_burn_no_decay,
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
        }
        ctx = Ctx(
            state=state, user=user, target=target, skill=skill,
            result=result, is_first=is_first, team=team, enemy_skill=enemy_skill,
        )
        for tag in effects:
            _apply_tag(tag, ctx)
        return result

    # ────────────────────────────────────────
    #  应对效果执行
    # ────────────────────────────────────────

    @staticmethod
    def execute_counter(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        counter_tag: EffectTag,
        enemy_skill: "Skill",
        damage: int,
        team: str = "a",
    ) -> Dict:
        """
        执行应对效果。子效果复用同一套 _apply_tag，无重复逻辑。
        """
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
            return result

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

            has_agility = any(e.type == E.AGILITY for e in skill.effects)
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

        for tag in target_skill.effects:
            if tag.type == E.PASSIVE_ENERGY_REDUCE:
                reduce = tag.params.get("reduce", 0)
                rng = tag.params.get("range", "self")
                if rng == "self":
                    target_skill.energy_cost = max(0, target_skill.energy_cost - reduce)
                elif rng == "adjacent":
                    for offset in [-1, 1]:
                        adj_idx = (target_idx + offset) % n_skills
                        user.skills[adj_idx].energy_cost = max(
                            0, user.skills[adj_idx].energy_cost - reduce
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
            if skill:
                from src.skill_db import _TYPE_MAP
                expected_type = _TYPE_MAP.get(f["element"])
                if expected_type and skill.skill_type != expected_type:
                    return False
            else:
                return False

        if f.get("condition") == "skill_element_not_enemy_type":
            skill = context.get("skill")
            if skill and skill.skill_type != enemy.pokemon_type:
                return True
            return False

        if "positions" in f:
            skill = context.get("skill")
            if skill:
                idx = _find_skill_index(pokemon, skill)
                if idx not in f["positions"]:
                    return False
            else:
                return False

        return True




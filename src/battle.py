"""
洛克王国战斗模拟系统 - 战斗引擎 + 队伍构建
"""

import sys
import os
import random
from typing import Optional, List, Tuple, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.models import (
    Pokemon, Skill, BattleState, Type, SkillCategory,
    StatusType, get_type_effectiveness
)
from src.skill_db import get_skill
from src.effect_models import E, Timing
from src.effect_engine import EffectExecutor, _apply_permanent_mod, _adjust_cost_delta


def _iter_flat_tags(effects):
    """从 List[SkillEffect] 或 List[EffectTag] 中提取所有 EffectTag（平铺）。"""
    from src.effect_models import SkillEffect
    if not effects:
        return
    for item in effects:
        if isinstance(item, SkillEffect):
            yield from item.effects
        else:
            yield item


def _has_tag_type(effects, etype) -> bool:
    """检查效果列表中是否存在某类型的 EffectTag。"""
    return any(tag.type == etype for tag in _iter_flat_tags(effects))


def _find_tags(effects, etype):
    """返回效果列表中所有匹配类型的 EffectTag。"""
    return [tag for tag in _iter_flat_tags(effects) if tag.type == etype]


def _ability_name(pokemon: Pokemon) -> str:
    if not pokemon.ability:
        return ""
    return pokemon.ability.split(":")[0].split("（")[0].strip()


def _has_ko_threat(attacker: Pokemon, defender: Pokemon) -> bool:
    for idx, skill in enumerate(attacker.skills):
        if skill.power <= 0:
            continue
        if attacker.energy < skill.energy_cost:
            continue
        if attacker.cooldowns.get(idx, 0) > 0:
            continue
        damage = DamageCalculator.calculate(attacker, defender, skill)
        if damage >= defender.current_hp:
            return True
    return False


def _apply_turn_start_ability_logic(state: BattleState) -> None:
    """回合开始：触发双方 ON_TURN_START 特性（预警/哨兵等）"""
    pairs = [
        (state.team_a, state.current_a, state.team_b, state.current_b, "a"),
        (state.team_b, state.current_b, state.team_a, state.current_a, "b"),
    ]
    for my_team, my_idx, enemy_team, enemy_idx, team_id in pairs:
        current = my_team[my_idx]
        if current.is_fainted or not current.ability_effects:
            continue
        enemy = enemy_team[enemy_idx]
        EffectExecutor.execute_ability(
            state, current, enemy, Timing.ON_TURN_START,
            current.ability_effects, team_id,
        )


def _clear_turn_temporary_ability_logic(state: BattleState) -> None:
    for pokemon in state.team_a + state.team_b:
        if pokemon.ability_state.pop("threat_speed_bonus_active", None):
            if pokemon.speed_up >= 0.5:
                pokemon.speed_up -= 0.5
        pokemon.ability_state.pop("force_switch_after_action", None)


def _transfer_pokemon_state(source: Pokemon, target: Pokemon) -> None:
    target.atk_up = source.atk_up
    target.atk_down = source.atk_down
    target.def_up = source.def_up
    target.def_down = source.def_down
    target.spatk_up = source.spatk_up
    target.spatk_down = source.spatk_down
    target.spdef_up = source.spdef_up
    target.spdef_down = source.spdef_down
    target.speed_up = source.speed_up
    target.speed_down = source.speed_down
    target.power_multiplier = source.power_multiplier
    target.life_drain_mod = source.life_drain_mod
    target.skill_power_bonus = source.skill_power_bonus
    target.skill_power_pct_mod = source.skill_power_pct_mod
    target.skill_cost_mod = source.skill_cost_mod
    target.hit_count_mod = source.hit_count_mod
    target.priority_stage = source.priority_stage
    target.next_attack_power_bonus = source.next_attack_power_bonus
    target.next_attack_power_pct = source.next_attack_power_pct
    target.poison_stacks = source.poison_stacks
    target.burn_stacks = source.burn_stacks
    target.freeze_stacks = source.freeze_stacks
    target.leech_stacks = source.leech_stacks
    target.frostbite_damage = source.frostbite_damage
    if "cute_mark" in source.ability_state:
        target.ability_state["cute_mark"] = source.ability_state["cute_mark"]
    if "temporary_skill_cost_mods" in source.ability_state:
        target.ability_state["temporary_skill_cost_mods"] = [
            dict(mod) for mod in source.ability_state["temporary_skill_cost_mods"]
        ]


def _temporary_skill_cost_delta(user: Pokemon, skill: Skill) -> int:
    delta = 0
    for mod in user.ability_state.get("temporary_skill_cost_mods", []):
        filt = mod.get("filter", "all")
        matched = False
        if filt == "all":
            matched = True
        elif filt == "attack":
            matched = skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL)
        elif filt == "used_skill":
            matched = skill.name == mod.get("skill_name")
        elif filt == "other_skills":
            matched = skill.name != mod.get("skill_name")
        if matched:
            delta += _adjust_cost_delta(user, int(mod.get("amount", 0)))
    return delta


def _transform_to_guard_queen(pokemon: Pokemon) -> None:
    from src.pokemon_db import get_pokemon

    if "棋绮后" in pokemon.name:
        return
    target_name = "棋绮后（白子）" if "白子" in pokemon.name else "棋绮后（黑子）"
    data = get_pokemon(target_name)
    if not data:
        return
    pokemon.name = target_name
    pokemon.hp = int(data["生命值"])
    pokemon.attack = int(data["物攻"])
    pokemon.sp_attack = int(data["魔攻"])
    pokemon.defense = int(data["物防"])
    pokemon.sp_defense = int(data["魔防"])
    pokemon.speed = int(data["速度"])
    pokemon.current_hp = pokemon.hp
    pokemon.energy = 10
    pokemon.status = StatusType.NORMAL
    pokemon.poison_stacks = 0
    pokemon.burn_stacks = 0
    pokemon.freeze_stacks = 0
    pokemon.leech_stacks = 0
    pokemon.frostbite_damage = 0
    pokemon.reset_mods()


def _handle_counter_success_ability(
    state: BattleState, pokemon: Pokemon, skill: Skill, defer_transform: bool = False
) -> None:
    """应对成功时触发特性（保卫等），通过数据驱动的 ON_COUNTER_SUCCESS"""
    if not pokemon.ability_effects:
        return
    # 确定对手
    enemy_list = state.team_b if pokemon in state.team_a else state.team_a
    enemy_idx = state.current_b if pokemon in state.team_a else state.current_a
    enemy = enemy_list[enemy_idx]
    team = "a" if pokemon in state.team_a else "b"
    EffectExecutor.execute_ability(
        state, pokemon, enemy, Timing.ON_COUNTER_SUCCESS,
        pokemon.ability_effects, team,
        context={"_counter_skill": skill, "_defer_transform": defer_transform},
    )


def _process_revive_timers(state: BattleState) -> None:
    for pokemon in state.team_a + state.team_b:
        turns_left = pokemon.ability_state.get("undying_revive_in")
        if turns_left is None:
            continue
        turns_left -= 1
        if turns_left > 0:
            pokemon.ability_state["undying_revive_in"] = turns_left
            continue
        pokemon.ability_state.pop("undying_revive_in", None)
        pokemon.ability_state["faint_processed"] = False
        pokemon.current_hp = pokemon.hp
        pokemon.status = StatusType.NORMAL
        pokemon.poison_stacks = 0
        pokemon.burn_stacks = 0
        pokemon.freeze_stacks = 0
        pokemon.leech_stacks = 0
        pokemon.frostbite_damage = 0


# ============================================================
# 伤害计算
# ============================================================
class DamageCalculator:

    # 天气修正表（洛克王国真实天气：沙暴/雪天/雨天）
    _WEATHER_MULT: Dict[str, Dict[str, float]] = {
        "rain":      {"water": 1.5},   # 雨天：水系招式威力+50%，无其他效果
        "sandstorm": {},               # 沙暴：无招式威力修正（回合伤害在 turn_end 处理）
        "snow":      {},               # 雪天：无招式威力修正
    }

    @staticmethod
    def calculate(attacker: Pokemon, defender: Pokemon, skill: Skill,
                  power_override: int = 0, weather: str = None,
                  hit_count_override: int = 0) -> int:
        power = power_override or skill.power
        if power <= 0:
            return 0

        # 按技能类型选取方向字段
        if skill.category == SkillCategory.MAGICAL:
            base_atk = attacker.sp_attack
            base_def = defender.sp_defense
            atk_up   = attacker.spatk_up
            atk_down = attacker.spatk_down
            def_up   = defender.spdef_up
            def_down = defender.spdef_down
        else:
            base_atk = attacker.attack
            base_def = defender.defense
            atk_up   = attacker.atk_up
            atk_down = attacker.atk_down
            def_up   = defender.def_up
            def_down = defender.def_down

        # 能力等级 = (1 + 我方攻升 + 敌方防降) / (1 + 我方攻降 + 敌方防升)
        ability_level = (1.0 + atk_up + def_down) / max(0.1, 1.0 + atk_down + def_up)

        atk = base_atk * ability_level
        dfn = max(1.0, float(base_def))

        # 基础伤害 = (攻击/防御) × 威力 × 0.9
        base = (atk / dfn) * power * 0.9

        # 属性克制
        eff = get_type_effectiveness(skill.skill_type, defender.pokemon_type)

        # 本系加成 1.5x
        stab = 1.5 if skill.skill_type == attacker.pokemon_type else 1.0

        # 天气修正
        weather_mult = 1.0
        if weather:
            wm = DamageCalculator._WEATHER_MULT.get(weather, {})
            skill_type_val = skill.skill_type.value if hasattr(skill.skill_type, "value") else str(skill.skill_type)
            weather_mult = wm.get(skill_type_val, 1.0)

        # 连击
        hits = hit_count_override or skill.hit_count

        # 威力提升 buff（独立乘法层）
        power_mult_buff = getattr(attacker, "power_multiplier", 1.0)

        damage = base * eff * stab * weather_mult * hits * power_mult_buff
        return max(1, int(damage))


# ============================================================
# 技能执行
# ============================================================

# ============================================================
# 回合执行
# ============================================================
Action = Tuple[int, ...]  # (skill_idx,) | (-1,) 汇合聚能 | (-2, switch_idx) 换人


def _compare_action_order(state: BattleState, action_a: Action, action_b: Action) -> int:
    """比较回合内行动顺序: 先手等级 > 当前速度 > 随机。返回 -1 表示 A 先手，否则 B 先手。"""
    pri_a = get_priority(state, "a", action_a)
    pri_b = get_priority(state, "b", action_b)
    if pri_a != pri_b:
        return -1 if pri_a > pri_b else 1

    p_a = state.team_a[state.current_a]
    p_b = state.team_b[state.current_b]
    spd_a = p_a.effective_speed()
    spd_b = p_b.effective_speed()
    if spd_a != spd_b:
        return -1 if spd_a > spd_b else 1

    return random.choice([-1, 1])


def get_actions(state: BattleState, team: str) -> List[Action]:
    """获取合法动作"""
    actions = []
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    current = team_list[idx]

    if current.is_fainted:
        for i, p in enumerate(team_list):
            if i != idx and not p.is_fainted:
                actions.append((-2, i))
        return actions if actions else [(-1,)]

    actions.append((-1,))  # 汇合聚能

    for i, skill in enumerate(current.skills):
        cd = current.cooldowns.get(i, 0)
        if current.energy >= skill.energy_cost and cd <= 0:
            actions.append((i,))

    return actions if actions else [(-1,)]



def auto_switch(state: BattleState, switch_cb_a=None, switch_cb_b=None) -> None:
    """
    被动换人：精灵倒下后选择下一只上场精灵，不占用行动回合。
    
    switch_cb_a/b: 可选的回调函数 (state, team_list, alive_indices) -> int
      返回要换上的精灵索引。若为 None 则默认选第一个存活精灵。
    """
    if state.team_a[state.current_a].is_fainted:
        alive = [i for i, p in enumerate(state.team_a) if not p.is_fainted]
        if alive:
            state.team_a[state.current_a].on_switch_out()
            if switch_cb_a and len(alive) > 1:
                chosen = switch_cb_a(state, state.team_a, alive)
                state.current_a = chosen if chosen in alive else alive[0]
            else:
                state.current_a = alive[0]
    if state.team_b[state.current_b].is_fainted:
        alive = [i for i, p in enumerate(state.team_b) if not p.is_fainted]
        if alive:
            state.team_b[state.current_b].on_switch_out()
            if switch_cb_b and len(alive) > 1:
                chosen = switch_cb_b(state, state.team_b, alive)
                state.current_b = chosen if chosen in alive else alive[0]
            else:
                state.current_b = alive[0]

    _trigger_battle_start_effects(state)


def _trigger_battle_start_effects(state: BattleState) -> None:
    """只触发一次的开局特性。"""
    if state.battle_start_effects_triggered:
        return
    state.battle_start_effects_triggered = True

    current_a = state.team_a[state.current_a]
    current_b = state.team_b[state.current_b]

    if current_a.ability_effects and not current_a.is_fainted:
        EffectExecutor.execute_ability(
            state, current_a, current_b, Timing.ON_BATTLE_START,
            current_a.ability_effects, "a",
        )
    if current_b.ability_effects and not current_b.is_fainted:
        EffectExecutor.execute_ability(
            state, current_b, current_a, Timing.ON_BATTLE_START,
            current_b.ability_effects, "b",
        )


def _trigger_ally_counter_effects(state: BattleState, team: str, enemy: Pokemon) -> None:
    """同队任意精灵应对成功后，触发该队的 ON_ALLY_COUNTER 特性。"""
    team_list = state.team_a if team == "a" else state.team_b
    for p in team_list:
        if p.is_fainted or not p.ability_effects:
            continue
        EffectExecutor.execute_ability(
            state, p, enemy, Timing.ON_ALLY_COUNTER,
            p.ability_effects, team,
        )


def turn_end_effects(state: BattleState) -> None:
    """回合结束：状态伤害结算 + 特性触发 (规则 v0.2)"""

    # 先触发回合结束特性
    pairs_ability = [
        (state.team_a, state.current_a, state.team_b, state.current_b, "a"),
        (state.team_b, state.current_b, state.team_a, state.current_a, "b"),
    ]
    burn_no_decay = set()  # 记录哪方灼烧不衰减
    for my_team, my_idx, enemy_team, enemy_idx, team_id in pairs_ability:
        p = my_team[my_idx]
        if p.is_fainted:
            continue
        if p.ability_effects:
            ctx = {}
            EffectExecutor.execute_ability(
                state, p, enemy_team[enemy_idx], Timing.ON_TURN_END,
                p.ability_effects, team_id, ctx,
            )
            if ctx.get("burn_no_decay"):
                burn_no_decay.add(team_id)

            # 燃薪虫煤渣草: PASSIVE 也检查
            EffectExecutor.execute_ability(
                state, p, enemy_team[enemy_idx], Timing.PASSIVE,
                p.ability_effects, team_id, ctx,
            )
            if ctx.get("burn_no_decay"):
                burn_no_decay.add(team_id)

    pairs = [
        (state.team_a, state.current_a, state.team_b, state.current_b, "a"),
        (state.team_b, state.current_b, state.team_a, state.current_a, "b"),
    ]
    for my_team, my_idx, enemy_team_list, enemy_idx, team_id in pairs:
        p = my_team[my_idx]
        if p.is_fainted:
            continue

        # 中毒: 3% × 层数 (不衰减)
        if p.poison_stacks > 0:
            dmg = int(p.hp * 0.03 * p.poison_stacks)
            p.current_hp -= max(1, dmg)

        # 燃烧: 4% × 层数, 然后层数减半(最少减1层)
        # 燃薪虫煤渣草: 灼烧不衰减反而增长
        if p.burn_stacks > 0:
            dmg = int(p.hp * 0.04 * p.burn_stacks)
            p.current_hp -= max(1, dmg)
            # 判断对手是否有煤渣草特性 (对手的在场精灵)
            enemy_team_id = "b" if team_id == "a" else "a"
            if enemy_team_id in burn_no_decay:
                # 灼烧增长 (增加与衰减等量)
                growth = max(1, p.burn_stacks // 2)
                p.burn_stacks += growth
            else:
                decay = max(1, p.burn_stacks // 2)
                p.burn_stacks = max(0, p.burn_stacks - decay)

        # 冻伤: 每回合累加 hp//12 不可恢复伤害
        if p.frostbite_damage > 0 or p.freeze_stacks > 0:
            frost_tick = p.hp // 12
            p.frostbite_damage += frost_tick
            if p.current_hp <= p.frostbite_damage:
                p.current_hp = 0
            else:
                effective_max = p.effective_max_hp
                if p.current_hp > effective_max:
                    p.current_hp = effective_max

        # 寄生: 每层8%最大HP, 吸取给对手
        if p.leech_stacks > 0:
            leech_dmg = int(p.hp * 0.08 * p.leech_stacks)
            p.current_hp -= max(1, leech_dmg)
            enemy = enemy_team_list[enemy_idx]
            if not enemy.is_fainted:
                enemy.current_hp = min(enemy.hp, enemy.current_hp + leech_dmg)

        # 星陨: 倒计时-1, 到0时引爆
        if p.meteor_countdown > 0:
            p.meteor_countdown -= 1
            if p.meteor_countdown <= 0 and p.meteor_stacks > 0:
                enemy = enemy_team_list[enemy_idx]
                meteor_power = 30 * p.meteor_stacks
                if not enemy.is_fainted:
                    e_spatk = enemy.effective_spatk()
                    p_spdef = max(1.0, p.effective_spdef())
                    meteor_dmg = max(1, int((e_spatk / p_spdef) * meteor_power * 0.9))
                else:
                    meteor_dmg = max(1, meteor_power)
                p.current_hp -= meteor_dmg
                p.meteor_stacks = 0

        # 判定倒下
        if p.current_hp <= 0:
            p.current_hp = 0
            p.status = StatusType.FAINTED

    # 天气伤害/效果 (沙暴：对非地/钢系造成1/16 HP伤害；雪天双方获得2层冻结)
    if state.weather in ("sandstorm", "hail", "snow"):
        from src.effect_engine import _apply_weather_damage
        _apply_weather_damage(state)

    # 天气回合递减
    if state.weather and hasattr(state, "weather_turns") and state.weather_turns > 0:
        state.weather_turns -= 1
        if state.weather_turns <= 0:
            # 沙暴结束：恢复地面系技能原始能耗
            if state.weather == "sandstorm" and hasattr(state, "_sandstorm_original_costs"):
                for p in state.team_a + state.team_b:
                    if p.is_fainted:
                        continue
                    for sk in p.skills:
                        key = id(sk)
                        if key in state._sandstorm_original_costs:
                            sk.energy_cost = state._sandstorm_original_costs[key]
                state._sandstorm_original_costs.clear()
            state.weather = None

    # 减少冷却
    for p in state.team_a + state.team_b:
        for k in list(p.cooldowns.keys()):
            if p.cooldowns[k] > 0:
                p.cooldowns[k] -= 1
        if p.ability_state.get("temporary_skill_cost_mods"):
            next_mods = []
            for mod in p.ability_state["temporary_skill_cost_mods"]:
                turns = int(mod.get("turns", 0)) - 1
                if turns > 0:
                    kept = dict(mod)
                    kept["turns"] = turns
                    next_mods.append(kept)
            if next_mods:
                p.ability_state["temporary_skill_cost_mods"] = next_mods
            else:
                p.ability_state.pop("temporary_skill_cost_mods", None)

    _process_revive_timers(state)
    _clear_turn_temporary_ability_logic(state)



def _check_fainted_and_deduct_mp(state: BattleState) -> None:
    """检查倒地精灵，扣除MP"""
    pa = state.team_a[state.current_a]
    pb = state.team_b[state.current_b]
    if pa.is_fainted and not pa.ability_state.get("faint_processed"):
        pa.ability_state["faint_processed"] = True
        state.mp_a -= 1
        # 触发 ON_FAINT 特性（不朽等）
        if pa.ability_effects:
            EffectExecutor.execute_ability(
                state, pa, pb, Timing.ON_FAINT, pa.ability_effects, "a")
    if pb.is_fainted and not pb.ability_state.get("faint_processed"):
        pb.ability_state["faint_processed"] = True
        state.mp_b -= 1
        if pb.ability_effects:
            EffectExecutor.execute_ability(
                state, pb, pa, Timing.ON_FAINT, pb.ability_effects, "b")


def _apply_moisture_mark(state: BattleState) -> None:
    """
    湿润印记效果：每层为己方全队所有技能能耗永久 -1。
    每回合行动前触发一次；印记清零后不再叠加，效果永久保留在技能能耗上。
    """
    for team, marks in [("a", state.marks_a), ("b", state.marks_b)]:
        stacks = marks.get("moisture_mark", 0)
        if stacks <= 0:
            continue
        team_list = state.team_a if team == "a" else state.team_b
        for p in team_list:
            for s in p.skills:
                delta = -stacks
                if p.ability_state.get("cost_invert"):
                    delta = -delta
                s.energy_cost = max(0, s.energy_cost + delta)
        marks["moisture_mark"] = 0   # 消耗印记，效果已永久写入技能


def _get_skill_for_action(state: BattleState, team: str, action: Action) -> Optional[Skill]:
    """从 action 中获取技能对象，换人/跳过返回 None。"""
    if action[0] < 0:
        return None
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    pokemon = team_list[idx]
    if action[0] >= len(pokemon.skills):
        return None
    return pokemon.skills[action[0]]


def _skill_has_counter_for(skill_a, skill_b) -> bool:
    """检查 skill_a 是否有对 skill_b 类型的应对。"""
    if not skill_a or not skill_b:
        return False
    from src.effect_models import SkillEffect as _SE, SkillTiming as _ST
    cat_map = {
        SkillCategory.PHYSICAL: "attack",
        SkillCategory.MAGICAL: "attack",
        SkillCategory.STATUS: "status",
        SkillCategory.DEFENSE: "defense",
    }
    enemy_cat = cat_map.get(skill_b.category, "")
    if not enemy_cat:
        return False
    for item in getattr(skill_a, "effects", []):
        if isinstance(item, _SE) and item.timing == _ST.ON_COUNTER:
            counter_cat = item.filter.get("category", "")
            if counter_cat == enemy_cat or not counter_cat:
                return True
        elif hasattr(item, "type"):
            from src.effect_models import E
            type_to_cat = {
                E.COUNTER_ATTACK: "attack",
                E.COUNTER_STATUS: "status",
                E.COUNTER_DEFENSE: "defense",
            }
            if type_to_cat.get(item.type) == enemy_cat:
                return True
    return False


def execute_full_turn(state: BattleState, action_a: Action, action_b: Action,
                      switch_cb_a=None, switch_cb_b=None) -> None:
    """
    执行完整回合。

    应对机制：
    - 如果 A 的技能有对 B 技能类型的应对 → A 应对 B → B 先动但 A 的应对先结算
    - 如果双方互相应对 → 按正常先手顺序
    - 应对无视速度和先手等级

    switch_cb_a/b: 被动换人回调 (state, team_list, alive_indices) -> int
      精灵倒下后让玩家/AI选择下一只上场精灵。
    """
    # 湿润印记：回合开始时应用全队能耗减少
    _trigger_battle_start_effects(state)
    _apply_turn_start_ability_logic(state)

    _apply_moisture_mark(state)

    p_a = state.team_a[state.current_a]
    p_b = state.team_b[state.current_b]

    # 重置本回合换人标记
    state.switch_this_turn_a = False
    state.switch_this_turn_b = False

    # 获取双方技能
    skill_a = _get_skill_for_action(state, "a", action_a)
    skill_b = _get_skill_for_action(state, "b", action_b)

    # 应对检测
    a_counters_b = _skill_has_counter_for(skill_a, skill_b)
    b_counters_a = _skill_has_counter_for(skill_b, skill_a)

    if a_counters_b and not b_counters_a:
        # A 应对 B → B 先动（被应对方先释放），A 后动
        # 但 A 的应对效果会在 B 释放过程中先结算
        first_team, second_team = "b", "a"
        first_act, second_act = action_b, action_a
    elif b_counters_a and not a_counters_b:
        # B 应对 A → A 先动（被应对方先释放），B 后动
        first_team, second_team = "a", "b"
        first_act, second_act = action_a, action_b
    else:
        # 无应对 / 双方互相应对 → 正常先手判定
        if _compare_action_order(state, action_a, action_b) == -1:
            first_team, second_team = "a", "b"
            first_act, second_act = action_a, action_b
        else:
            first_team, second_team = "b", "a"
            first_act, second_act = action_b, action_a

    # 先手行动
    _execute_with_counter(state, first_team, first_act, second_team, second_act, is_first=True)
    _check_fainted_and_deduct_mp(state)
    auto_switch(state, switch_cb_a, switch_cb_b)

    if check_winner(state):
        _clear_turn_temporary_ability_logic(state)
        return

    # 后手行动
    _execute_with_counter(state, second_team, second_act, first_team, first_act, is_first=False)
    _check_fainted_and_deduct_mp(state)
    auto_switch(state, switch_cb_a, switch_cb_b)

    if check_winner(state):
        _clear_turn_temporary_ability_logic(state)
        return

    turn_end_effects(state)
    _check_fainted_and_deduct_mp(state)
    auto_switch(state, switch_cb_a, switch_cb_b)
    state.turn += 1


def _execute_with_counter(state: BattleState, team: str, action: Action,
                          enemy_team: str, enemy_action: Action,
                          is_first: bool) -> None:
    """执行行动+应对解析 (兼容新旧引擎)"""
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    enemy_list = state.team_b if team == "a" else state.team_a
    eidx = state.current_b if team == "a" else state.current_a
    current = team_list[idx]
    enemy = enemy_list[eidx]

    if current.is_fainted:
        return

    # 换人
    if action[0] == -2:
        old_pokemon = current
        switch_snapshot = current.copy_state()
        current.on_switch_out()

        # 特性: 离场触发 (翠顶夫人洁癖)
        transfer_ctx = {}
        if old_pokemon.ability_effects:
            EffectExecutor.execute_ability(
                state, old_pokemon, enemy, Timing.ON_LEAVE,
                old_pokemon.ability_effects, team, transfer_ctx,
            )

        if team == "a":
            state.current_a = action[1]
            state.switch_this_turn_a = True
        else:
            state.current_b = action[1]
            state.switch_this_turn_b = True

        new_pokemon = team_list[action[1]]

        # 洁癖: 传递属性修正
        if "transfer_mods" in transfer_ctx:
            mods = transfer_ctx["transfer_mods"]
            new_pokemon.atk_up    += mods.get("atk_up", 0)
            new_pokemon.atk_down  += mods.get("atk_down", 0)
            new_pokemon.def_up    += mods.get("def_up", 0)
            new_pokemon.def_down  += mods.get("def_down", 0)
            new_pokemon.spatk_up  += mods.get("spatk_up", 0)
            new_pokemon.spatk_down += mods.get("spatk_down", 0)
            new_pokemon.spdef_up  += mods.get("spdef_up", 0)
            new_pokemon.spdef_down += mods.get("spdef_down", 0)
            new_pokemon.speed_up  += mods.get("speed_up", 0)
            new_pokemon.speed_down += mods.get("speed_down", 0)

        # 特性: 入场触发
        if new_pokemon.ability_effects:
            EffectExecutor.execute_ability(
                state, new_pokemon, enemy, Timing.ON_ENTER,
                new_pokemon.ability_effects, team,
            )

        # 迅捷：入场时自动释放带 agility 标记的技能
        EffectExecutor.execute_agility_entry(state, new_pokemon, enemy, team)

        # 敌方特性: 对手换人时触发 (影狸下黑手 / 贪婪等)
        if enemy.ability_effects:
            EffectExecutor.execute_ability(
                state, enemy, new_pokemon, Timing.ON_ENEMY_SWITCH,
                enemy.ability_effects, enemy_team,
                context={"switched_out": old_pokemon, "switched_in": new_pokemon,
                         "switch_snapshot": switch_snapshot},
            )
        return

    # 汇合聚能
    if action[0] == -1:
        current.gain_energy(5)
        return

    skill = current.skills[action[0]]

    # 蓄力逻辑
    if skill.charge:
        if current.charging_skill_idx != action[0]:
            current.charging_skill_idx = action[0]
            return
        else:
            current.charging_skill_idx = -1

    # 计算实际能耗（含动态减免，如毒液渗透）
    actual_cost = max(
        0,
        skill.energy_cost
        + getattr(current, "skill_cost_mod", 0)
        + _temporary_skill_cost_delta(current, skill),
    )
    for tag in _iter_flat_tags(getattr(skill, "effects", [])):
        if tag.type == E.ENERGY_COST_DYNAMIC:
            per = tag.params.get("per", "")
            reduce = tag.params.get("reduce", 0)
            if per == "enemy_poison":
                refund = enemy.poison_stacks * reduce
                dynamic_delta = -refund
                if current.ability_state.get("cost_invert"):
                    dynamic_delta = -dynamic_delta
                actual_cost = max(0, actual_cost + dynamic_delta)

    if current.energy < actual_cost:
        current.gain_energy(5)
        # 记录聚能事件，供 server.py 日志展示
        if not hasattr(state, "_energy_recharge_log"):
            state._energy_recharge_log = []
        state._energy_recharge_log.append({
            "team": team, "pokemon": current.name,
            "skill": skill.name, "needed": actual_cost, "had": current.energy - 5,
        })
        return
    current.energy -= actual_cost

    # 所有技能走新引擎（效果由 EffectTag 驱动）
    _execute_new_engine(state, team, enemy_team, current, enemy, skill,
                        action, enemy_action, team_list, idx, is_first)


def _execute_new_engine(state: BattleState, team: str, enemy_team: str,
                        current: Pokemon, enemy: Pokemon, skill: Skill,
                        action: Action, enemy_action: Action,
                        team_list: list, idx: int, is_first: bool) -> None:
    """新引擎路径: 用 EffectExecutor 执行有 effects 的技能"""

    # 获取对方技能 (用于应对判定)
    enemy_skill = None
    enemy_list = state.team_b if team == "a" else state.team_a
    if enemy_action[0] >= 0 and not enemy.is_fainted:
        enemy_skill = enemy.skills[enemy_action[0]]

    # 执行主效果
    result = EffectExecutor.execute_skill(
        state, current, enemy, skill, skill.effects,
        is_first=is_first, enemy_skill=enemy_skill, team=team,
    )

    damage = result["damage"]

    # 保存原始伤害，用于应对反弹（听桥等需要反弹原始伤害而非已减伤值）
    original_damage = damage

    # 先检查敌方技能是否有防御减伤（防御/风墙/听桥/火焰护盾等）
    # damage_reduction 先于应对效果结算
    if enemy_skill and hasattr(enemy_skill, "effects") and enemy_skill.effects:
        for e2 in _iter_flat_tags(enemy_skill.effects):
            if e2.type == E.DAMAGE_REDUCTION and damage > 0:
                pct = e2.params.get("pct", 0)
                damage = int(damage * (1.0 - pct))

    # 应对解析 (我方技能有 COUNTER_*，如毒液渗透/偷袭等)
    should_resolve_self_counters = _has_tag_type(skill.effects, E.DAMAGE)
    if enemy_skill and not enemy.is_fainted and result["counter_effects"] and should_resolve_self_counters:
        for counter_tag in result["counter_effects"]:
            pre_counter_count = state.counter_count_a if team == "a" else state.counter_count_b
            counter_result = EffectExecutor.execute_counter(
                state, current, enemy, skill, counter_tag,
                enemy_skill, damage, team,
            )

            counter_succeeded = (
                (state.counter_count_a if team == "a" else state.counter_count_b)
                > pre_counter_count
            )

            if counter_result and "final_damage" in counter_result:
                damage = counter_result["final_damage"]

            if counter_succeeded:
                for s in current.skills:
                    if not getattr(s, "effects", None):
                        continue
                    for tag in _iter_flat_tags(s.effects):
                        if tag.type == E.PERMANENT_MOD and tag.params.get("trigger") == "per_counter":
                            _apply_permanent_mod(current, s, tag.params, force=True)

            if counter_result and counter_result.get("interrupted"):
                result["interrupted"] = True

            if counter_succeeded:
                current.ability_state["last_counter_success_turn"] = state.turn
                _handle_counter_success_ability(state, current, skill)
                _trigger_ally_counter_effects(state, team, enemy)
            if counter_result and counter_result.get("force_switch"):
                result["force_switch"] = True

            if counter_result and counter_result.get("force_enemy_switch"):
                result["force_enemy_switch"] = True

    # 对方技能的应对效果（对方防御/状态技能应对我方攻击）
    # 传入原始伤害（听桥需要反弹原始伤害）
    if enemy_skill and hasattr(enemy_skill, "effects") and enemy_skill.effects:
        _counter_items = []
        for item in enemy_skill.effects:
            from src.effect_models import SkillEffect as _SE
            if isinstance(item, _SE):
                from src.effect_models import SkillTiming as _ST
                if item.timing == _ST.ON_COUNTER:
                    _counter_items.append(item)
            elif hasattr(item, "type") and item.type in (E.COUNTER_ATTACK, E.COUNTER_STATUS, E.COUNTER_DEFENSE):
                _counter_items.append(item)
        for etag in _counter_items:
                pre_counter_count = (
                    state.counter_count_a if enemy_team == "a" else state.counter_count_b
                )
                counter_result = EffectExecutor.execute_counter(
                    state, enemy, current, enemy_skill, etag,
                    skill, original_damage, enemy_team,   # 传入原始伤害（非已减伤值）
                )
                counter_succeeded = (
                    (state.counter_count_a if enemy_team == "a" else state.counter_count_b)
                    > pre_counter_count
                )

                if counter_succeeded:
                    for s in enemy.skills:
                        if not getattr(s, "effects", None):
                            continue
                        for tag in _iter_flat_tags(s.effects):
                            if tag.type == E.PERMANENT_MOD and tag.params.get("trigger") == "per_counter":
                                # 能量刃：每应对1次威力永久+N
                                _apply_permanent_mod(enemy, s, tag.params, force=True)

                if counter_succeeded:
                    enemy.ability_state["last_counter_success_turn"] = state.turn
                    _handle_counter_success_ability(state, enemy, enemy_skill, defer_transform=True)
                    _trigger_ally_counter_effects(state, enemy_team, current)
                if counter_result and counter_result.get("force_enemy_switch"):
                    # 吓退: 强制我方脱离
                    alive = [i for i, p in enumerate(team_list)
                             if not p.is_fainted and i != idx]
                    if alive:
                        current.on_switch_out()
                        new_idx = random.choice(alive)
                        if team == "a":
                            state.current_a = new_idx
                        else:
                            state.current_b = new_idx

    # 秩序鱿墨特性: 受到攻击时减伤
    if enemy.ability_effects and damage > 0:
        ability_ctx = {"skill": skill, "damage": damage}
        ability_result = EffectExecutor.execute_ability(
            state, enemy, current, Timing.ON_TAKE_HIT,
            enemy.ability_effects, enemy_team, ability_ctx,
        )
        if ability_result.get("damage_reduction", 0) > 0:
            damage = int(damage * (1.0 - ability_result["damage_reduction"]))

    # 技能自带减伤 (防御类/状态类技能)
    dmg_reduction = result.get("_damage_reduction", 0)
    if dmg_reduction > 0:
        # 这是自身的减伤, 应用于对方对自己造成的伤害 (不适用于此处)
        pass

    # 造成伤害
    if damage > 0 and not enemy.is_fainted:
        enemy.current_hp -= damage
        if enemy.current_hp <= 0:
            enemy.current_hp = 0
            enemy.status = StatusType.FAINTED
    if enemy.ability_state.pop("guard_transform_pending", None):
        _transform_to_guard_queen(enemy)

    # 击败检查 & 击败时效果
    if enemy.is_fainted:
        # 感染病: 击败时中毒转印记
        for tag in _iter_flat_tags(skill.effects):
            if tag.type == E.CONVERT_POISON_TO_MARK and tag.params.get("on") == "kill":
                marks = state.marks_b if team == "a" else state.marks_a
                marks["poison_mark"] = marks.get("poison_mark", 0) + enemy.poison_stacks
                enemy.poison_stacks = 0

        # 特性: 被击败时 (圣羽翼王飓风)
        if enemy.ability_effects:
            EffectExecutor.execute_ability(
                state, enemy, current, Timing.ON_BE_KILLED,
                enemy.ability_effects, enemy_team,
            )

        # 特性: 力竭时 (迷迷箱怪虚假宝箱)
        if enemy.ability_effects:
            EffectExecutor.execute_ability(
                state, enemy, current, Timing.ON_FAINT,
                enemy.ability_effects, enemy_team,
            )

    if result.get("_self_ko") and not current.is_fainted:
        current.current_hp = 0
        current.status = StatusType.FAINTED

    # 脱离（泡沫幻影应对成功等触发的主动脱离）
    # 记录到 state 供 server.py 检查，让玩家手动选择换上哪只（不随机）
    if result.get("force_switch"):
        alive = [i for i, p in enumerate(team_list) if not p.is_fainted and i != idx]
        if alive:
            current.on_switch_out()
            # 存储待处理的换人请求，server.py 负责让玩家选择
            if not hasattr(state, "_pending_switch_requests"):
                state._pending_switch_requests = []
            state._pending_switch_requests.append({
                "team": team,
                "reason": "force_switch",  # 主动脱离
                "alive": alive,
            })
            # 临时用第一个存活精灵占位，等玩家选择后更新
            if team == "a":
                state.current_a = alive[0]
            else:
                state.current_b = alive[0]
    elif current.ability_state.pop("force_switch_after_action", None):
        alive = [i for i, p in enumerate(team_list) if not p.is_fainted and i != idx]
        if alive:
            current.on_switch_out()
            new_idx = random.choice(alive)
            if team == "a":
                state.current_a = new_idx
            else:
                state.current_b = new_idx

    # 强制敌方脱离 (吓退)
    if result.get("force_enemy_switch"):
        eidx = state.current_b if team == "a" else state.current_a
        enemy_list_ref = state.team_b if team == "a" else state.team_a
        alive = [i for i, p in enumerate(enemy_list_ref) if not p.is_fainted and i != eidx]
        if alive:
            enemy.on_switch_out()
            new_idx = random.choice(alive)
            if team == "a":
                state.current_b = new_idx
            else:
                state.current_a = new_idx

    # 驱散印记 (倾泻: 未被防御时)
    if result.get("_dispel_if_not_blocked"):
        # 检查对方是否使用了防御/减伤技能
        was_blocked = False
        if enemy_skill and enemy_skill.effects:
            was_blocked = _has_tag_type(enemy_skill.effects, E.DAMAGE_REDUCTION)
        elif enemy_skill and enemy_skill.damage_reduction > 0:
            was_blocked = True
        if not was_blocked:
            state.marks_a.clear()
            state.marks_b.clear()

    # 传动
    drive_value = result.get("_drive_value", 0)
    if drive_value > 0:
        EffectExecutor.execute_drive(state, current, enemy, skill, drive_value, team)

    # 特性: 使用技能后触发 (千棘盔溶解扩散/琉璃水母扩散侵蚀)
    if current.ability_effects:
        EffectExecutor.execute_ability(
            state, current, enemy, Timing.ON_USE_SKILL,
            current.ability_effects, team,
            context={"skill": skill},
        )

    # 技能自身的永久变化（每次使用后）
    for tag in _iter_flat_tags(getattr(skill, "effects", [])):
        if tag.type == E.PERMANENT_MOD and tag.params.get("trigger") == "per_use":
            _apply_permanent_mod(current, skill, tag.params, force=True)


    # 条件增益: 嘲弄 (敌方本回合替换精灵)
    cond_buff = result.get("_conditional_enemy_switch_buff")
    if cond_buff:
        enemy_switched = (state.switch_this_turn_b if team == "a" else state.switch_this_turn_a)
        if enemy_switched:
            from src.effect_engine import _apply_buff
            _apply_buff(current, cond_buff)

    # 疾风连袭: 重放迅捷技能
    if result.get("_replay_agility"):
        EffectExecutor.execute_agility_entry(state, current, enemy, team)

    # 疾风连袭: 将重放的迅捷技能能耗分摊到本技能
    if result.get("_agility_cost_share"):
        divisor = result["_agility_cost_share"]
        for s in current.skills:
            if s.agility:
                current.energy += s.energy_cost // divisor
                break

    # 毒液渗透: 动态能耗减免（每层敌方中毒 -1 能耗）
    energy_refund = result.get("_energy_refund", 0)
    if energy_refund > 0:
        delta = -energy_refund
        if current.ability_state.get("cost_invert"):
            delta = -delta
        skill.energy_cost = max(0, skill.energy_cost + delta)

    current.ability_state["last_skill_turn"] = state.turn
    current.ability_state["last_skill_category"] = skill.category.value


def _is_first_action(state: BattleState, team: str, action: Action,
                     enemy_team: str, enemy_action: Action) -> bool:
    """判断当前行动是否先于对手"""
    if team == "a":
        action_a, action_b = action, enemy_action
    else:
        action_a, action_b = enemy_action, action
    order = _compare_action_order(state, action_a, action_b)
    if team == "a":
        return order == -1
    return order == 1


def get_priority(state: BattleState, team: str, action: Action) -> int:
    """获取先手等级。默认 0，+1 必定先于 0，-1 慢于 0。"""
    if action[0] < 0:
        return 0
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    if action[0] >= len(team_list[idx].skills):
        return 0
    pokemon = team_list[idx]
    skill = pokemon.skills[action[0]]
    return skill.priority_mod + getattr(pokemon, "priority_stage", 0)


def check_winner(state: BattleState) -> Optional[str]:
    """检查胜负: 先失去4点MP(降到0)的玩家败北"""
    if state.mp_a <= 0:
        return "b"
    if state.mp_b <= 0:
        return "a"
    return None


# ============================================================
# 队伍构建 - 从精灵数据库+技能数据库自动获取属性
# ============================================================
class TeamBuilder:

    TYPE_MAP = {
        "普通": Type.NORMAL, "火": Type.FIRE, "水": Type.WATER, "草": Type.GRASS,
        "电": Type.ELECTRIC, "冰": Type.ICE, "格斗": Type.FIGHTING, "毒": Type.POISON,
        "地面": Type.GROUND, "飞行": Type.FLYING, "超能": Type.PSYCHIC, "虫": Type.BUG,
        "幽灵": Type.GHOST, "龙": Type.DRAGON, "恶": Type.DARK,
        "钢": Type.STEEL, "妖精": Type.FAIRY, "机械": Type.STEEL, "萌": Type.FAIRY,
        "翼": Type.FLYING, "武": Type.FIGHTING, "幽": Type.GHOST, "幻": Type.PSYCHIC,
        "光": Type.LIGHT,
    }

    @staticmethod
    def _p(name: str, skill_names: list) -> Pokemon:
        """根据精灵名称从数据库获取六维数据，构造Pokemon对象"""
        from src.pokemon_db import get_pokemon
        from src.skill_db import load_ability_effects

        data = get_pokemon(name)
        if data:
            ptype_str = data["属性"]
            ability = data["特性"]
            hp = int(data["生命值"])
            atk = int(data["物攻"])
            dfn = int(data["物防"])
            spatk = int(data["魔攻"])
            spdef = int(data["魔防"])
            spd = int(data["速度"])
        else:
            print(f"[WARN] 精灵 '{name}' 未在数据库中找到，使用默认属性")
            ptype_str = "普通"
            ability = "未知"
            hp, atk, dfn, spatk, spdef, spd = 500, 350, 350, 350, 350, 350

        type_enum = TeamBuilder.TYPE_MAP.get(ptype_str, Type.NORMAL)
        skills = [get_skill(n) for n in skill_names]

        # 加载特性效果
        ability_effects = load_ability_effects(ability) if ability else []

        p = Pokemon(name=name, pokemon_type=type_enum,
                    hp=hp, attack=atk, defense=dfn,
                    sp_attack=spatk, sp_defense=spdef,
                    speed=spd, ability=ability, skills=skills)
        p.ability_effects = ability_effects
        # 初始化被动标记（对流等需要在加载时就设置）
        for ae in ability_effects:
            for tag in ae.effects:
                if tag.type == E.COST_INVERT:
                    p.ability_state["cost_invert"] = True
        return p

    @staticmethod
    def create_toxic_team() -> List[Pokemon]:
        return [
            TeamBuilder._p("千棘盔", ["毒雾", "泡沫幻影", "疫病吐息", "打湿"]),
            TeamBuilder._p("影狸", ["嘲弄", "恶意逃离", "毒液渗透", "感染病"]),
            TeamBuilder._p("裘卡", ["阻断", "崩拳", "毒囊", "防御"]),
            TeamBuilder._p("琉璃水母", ["甩水", "天洪", "泡沫幻影", "以毒攻毒"]),
            TeamBuilder._p("迷迷箱怪", ["风墙", "啮合传递", "双星", "偷袭"]),
            TeamBuilder._p("海豹船长", ["力量增效", "水刃", "斩断", "听桥"]),
        ]

    @staticmethod
    def create_wing_team() -> List[Pokemon]:
        return [
            TeamBuilder._p("燃薪虫", ["火焰护盾", "引燃", "倾泻", "抽枝"]),
            TeamBuilder._p("圣羽翼王", ["水刃", "力量增效", "疾风连袭", "扇风"]),
            TeamBuilder._p("翠顶夫人", ["力量增效", "水刃", "水环", "泡沫幻影"]),
            TeamBuilder._p("迷迷箱怪", ["双星", "啮合传递", "偷袭", "吓退"]),
            TeamBuilder._p("秩序鱿墨", ["风墙", "能量刃", "力量增效", "倾泻"]),
            TeamBuilder._p("声波缇塔", ["轴承支撑", "齿轮扭矩", "地刺", "啮合传递"]),
        ]

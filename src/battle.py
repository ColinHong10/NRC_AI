"""
洛克王国战斗模拟系统 - 战斗引擎 + 队伍构建
"""

import sys
import os
import random
from typing import Tuple, Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.models import (
    Pokemon, Skill, BattleState, Type, SkillCategory,
    StatusType, StatType, get_type_effectiveness
)
from src.skill_db import get_skill, SPECIAL_TYPES


# ============================================================
# 伤害计算
# ============================================================
class DamageCalculator:

    @staticmethod
    def calculate(attacker: Pokemon, defender: Pokemon, skill: Skill,
                  power_override: int = 0) -> int:
        power = power_override or skill.power
        if power <= 0:
            return 0

        if skill.skill_type in SPECIAL_TYPES:
            atk = attacker.effective_spatk()
            dfn = defender.effective_spdef()
        else:
            atk = attacker.effective_atk()
            dfn = defender.effective_def()

        if dfn < 1:
            dfn = 1

        # 基础伤害 = 攻击/防御 * 威力 * 0.9
        base = (atk / dfn) * power * 0.9

        # 属性克制
        eff = get_type_effectiveness(skill.skill_type, defender.pokemon_type)

        # 本系加成
        stab = 1.5 if skill.skill_type == attacker.pokemon_type else 1.0

        # 连击
        hits = skill.hit_count

        damage = base * eff * stab * hits
        return max(1, int(damage))


# ============================================================
# 技能执行
# ============================================================
def apply_skill(attacker: Pokemon, defender: Pokemon, skill: Skill,
                is_counter: bool = False, counter_category: SkillCategory = None) -> int:
    """执行技能，返回造成的伤害"""

    # --- 自身增益 ---
    attacker.apply_self_buff(skill)

    # --- 敌方减益 ---
    defender.apply_enemy_debuff(skill)

    # --- 回复HP ---
    if skill.self_heal_hp > 0:
        heal = int(attacker.hp * skill.self_heal_hp)
        attacker.current_hp = min(attacker.hp, attacker.current_hp + heal)

    # --- 回复/偷取能量 ---
    if skill.self_heal_energy > 0:
        attacker.gain_energy(skill.self_heal_energy)
    if skill.steal_energy > 0:
        attacker.gain_energy(skill.steal_energy)
        defender.energy = max(0, defender.energy - skill.steal_energy)
    if skill.enemy_lose_energy > 0:
        defender.energy = max(0, defender.energy - skill.enemy_lose_energy)

    # --- 状态附加 ---
    if skill.poison_stacks > 0:
        defender.poison_stacks += skill.poison_stacks
    if skill.burn_stacks > 0:
        defender.burn_stacks += skill.burn_stacks
    if skill.freeze_stacks > 0:
        defender.freeze_stacks += skill.freeze_stacks
    if skill.freeze_stacks >= 3:
        defender.status = StatusType.FROZEN

    # --- 伤害计算 ---
    power = skill.power

    # 应对效果：威力倍率
    if is_counter and counter_category:
        if counter_category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
            # 对方用攻击，我的应对效果
            pass  # 防御技能主要减伤，攻击技能看应对状态
        if counter_category == SkillCategory.STATUS:
            if skill.counter_status_power_mult > 1:
                power = int(power * skill.counter_status_power_mult)
        if counter_category == SkillCategory.DEFENSE:
            if skill.counter_defense_power_mult > 1:
                power = int(power * skill.counter_defense_power_mult)

    if power <= 0 and skill.counter_physical_power_mult > 0:
        return 0

    damage = DamageCalculator.calculate(attacker, defender, skill, power_override=power)

    # --- 防御减伤 ---
    if skill.damage_reduction > 0:
        # 如果这是防御技能且对方在攻击，减少受到的伤害
        pass  # 减伤在execute_turn中处理

    # --- 吸血 ---
    drain = skill.life_drain
    if is_counter and counter_category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
        if skill.counter_physical_drain > 0:
            drain = max(drain, skill.counter_physical_drain)
    if drain > 0:
        heal = int(damage * drain)
        attacker.current_hp = min(attacker.hp, attacker.current_hp + heal)

    return damage


def apply_defense_response(defender: Pokemon, attacker: Pokemon,
                           def_skill: Skill, atk_skill: Skill,
                           damage: int) -> Tuple[int, bool]:
    """处理防御技能的应对效果，返回(最终伤害, 是否完全防御)"""
    final_damage = damage

    # 减伤
    if def_skill.damage_reduction > 0:
        final_damage = int(damage * (1.0 - def_skill.damage_reduction))

    # 应对攻击的额外效果
    if def_skill.counter_physical_drain > 0:
        heal = int(final_damage * def_skill.counter_physical_drain)
        defender.current_hp = min(defender.hp, defender.current_hp + heal)
    if def_skill.counter_physical_energy_drain > 0:
        attacker.energy = max(0, attacker.energy - def_skill.counter_physical_energy_drain)
    if def_skill.counter_physical_self_atk > 0:
        defender.atk_mod += def_skill.counter_physical_self_atk
    if def_skill.counter_physical_enemy_def > 0:
        attacker.def_mod -= def_skill.counter_physical_enemy_def
    if def_skill.counter_physical_enemy_atk > 0:
        attacker.atk_mod -= def_skill.counter_physical_enemy_atk

    # 应对反伤
    if def_skill.counter_damage_reflect > 0:
        reflect = int(final_damage * def_skill.counter_damage_reflect)
        attacker.current_hp -= reflect

    return max(0, final_damage), def_skill.damage_reduction >= 1.0


def apply_counter_status(attacker: Pokemon, defender: Pokemon,
                         atk_skill: Skill, def_skill: Skill) -> int:
    """攻击技能应对状态技能的额外效果"""
    extra = 0
    if def_skill.category == SkillCategory.STATUS:
        if atk_skill.counter_status_enemy_lose_energy > 0:
            defender.energy = max(0, defender.energy - atk_skill.counter_status_enemy_lose_energy)
            extra += atk_skill.counter_status_enemy_lose_energy
        if atk_skill.counter_physical_self_atk > 0:
            attacker.atk_mod += atk_skill.counter_physical_self_atk
        if atk_skill.counter_status_poison_stacks > 0:
            defender.poison_stacks += atk_skill.counter_status_poison_stacks
    return extra


# ============================================================
# 回合执行
# ============================================================
Action = Tuple[int, ...]  # (skill_idx,) | (-1,) 汇合聚能 | (-2, switch_idx) 换人


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


def apply_action(state: BattleState, team: str, action: Action) -> Optional[str]:
    """执行动作，返回技能名(用于日志)"""
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    enemy_list = state.team_b if team == "a" else state.team_a
    eidx = state.current_b if team == "a" else state.current_a
    current = team_list[idx]
    defender = enemy_list[eidx]

    if action[0] == -2:
        if team == "a":
            state.current_a = action[1]
        else:
            state.current_b = action[1]
        return f"换人->{team_list[action[1]].name}"

    if action[0] == -1:
        current.gain_energy(5)
        return "汇合聚能"

    skill = current.skills[action[0]]
    current.energy -= skill.energy_cost

    if skill.force_switch:
        # 脱离
        alive = [i for i, p in enumerate(team_list) if not p.is_fainted and i != idx]
        if alive:
            new_idx = random.choice(alive)
            if team == "a":
                state.current_a = new_idx
            else:
                state.current_b = new_idx

    if skill.category == SkillCategory.DEFENSE:
        # 防御技能不造成直接伤害，效果在应对时处理
        return skill.name

    if skill.power > 0 and not defender.is_fainted:
        damage = apply_skill(current, defender, skill)
        defender.current_hp -= damage
        if defender.current_hp <= 0:
            defender.current_hp = 0
            defender.status = StatusType.FAINTED

    return skill.name


def auto_switch(state: BattleState) -> None:
    """自动换人：如果当前精灵倒下，切换到第一个存活精灵"""
    if state.team_a[state.current_a].is_fainted:
        alive = [i for i, p in enumerate(state.team_a) if not p.is_fainted]
        if alive:
            state.current_a = alive[0]
    if state.team_b[state.current_b].is_fainted:
        alive = [i for i, p in enumerate(state.team_b) if not p.is_fainted]
        if alive:
            state.current_b = alive[0]


def turn_end_effects(state: BattleState) -> None:
    """回合结束：中毒/灼烧伤害"""
    for p in state.team_a + state.team_b:
        if p.is_fainted:
            continue
        if p.poison_stacks > 0:
            dmg = p.hp // 16 * min(p.poison_stacks, 5)
            p.current_hp -= dmg
        if p.burn_stacks > 0:
            dmg = p.hp // 16 * min(p.burn_stacks, 5)
            p.current_hp -= dmg
        # 解冻概率
        if p.status == StatusType.FROZEN and p.freeze_stacks <= 0:
            p.status = StatusType.NORMAL
        if p.current_hp <= 0:
            p.current_hp = 0
            p.status = StatusType.FAINTED

    # 减少冷却
    for p in state.team_a + state.team_b:
        for k in list(p.cooldowns.keys()):
            if p.cooldowns[k] > 0:
                p.cooldowns[k] -= 1


def resolve_counter(attacker: Pokemon, defender: Pokemon,
                    atk_skill: Skill, def_skill: Skill, damage: int) -> int:
    """解析应对交互，返回最终伤害"""
    if def_skill.category == SkillCategory.DEFENSE:
        if atk_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
            # 攻击 vs 防御 → 防御减伤+应对效果
            final_dmg, _ = apply_defense_response(defender, attacker, def_skill, atk_skill, damage)
            return final_dmg
        # 防御 vs 状态 → 状态的应对防御效果
        if def_skill.counter_defense_self_atk > 0:
            defender.atk_mod += def_skill.counter_defense_self_atk
        if def_skill.counter_defense_enemy_def > 0:
            attacker.def_mod -= def_skill.counter_defense_enemy_def

    elif def_skill.category == SkillCategory.STATUS:
        if atk_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
            # 攻击 vs 状态 → 攻击的应对状态效果
            apply_counter_status(attacker, defender, atk_skill, def_skill)
        elif atk_skill.category == SkillCategory.DEFENSE:
            # 防御 vs 状态 → 状态的应对防御效果
            if def_skill.counter_defense_enemy_def > 0:
                attacker.def_mod -= def_skill.counter_defense_enemy_def

    elif def_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
        if atk_skill.category == SkillCategory.STATUS:
            # 状态 vs 攻击 → 状态无特殊效果
            pass

    return damage


def execute_full_turn(state: BattleState, action_a: Action, action_b: Action) -> None:
    """执行完整回合"""
    p_a = state.team_a[state.current_a]
    p_b = state.team_b[state.current_b]

    # 速度判定
    spd_a = p_a.effective_speed() * (1.0 + get_priority(state, "a", action_a))
    spd_b = p_b.effective_speed() * (1.0 + get_priority(state, "b", action_b))

    if spd_a >= spd_b:
        first_team, second_team = "a", "b"
        first_act, second_act = action_a, action_b
    else:
        first_team, second_team = "b", "a"
        first_act, second_act = action_b, action_a

    # 先手行动
    _execute_with_counter(state, first_team, first_act, second_team, second_act)
    auto_switch(state)

    if check_winner(state):
        return

    # 后手行动
    _execute_with_counter(state, second_team, second_act, first_team, first_act)
    auto_switch(state)

    turn_end_effects(state)
    auto_switch(state)
    state.turn += 1


def _execute_with_counter(state: BattleState, team: str, action: Action,
                          enemy_team: str, enemy_action: Action) -> None:
    """执行行动+应对解析"""
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    enemy_list = state.team_b if team == "a" else state.team_a
    eidx = state.current_b if team == "a" else state.current_a
    current = team_list[idx]
    enemy = enemy_list[eidx]

    # 换人
    if action[0] == -2:
        if team == "a":
            state.current_a = action[1]
        else:
            state.current_b = action[1]
        return

    # 汇合聚能
    if action[0] == -1:
        current.gain_energy(5)
        return

    skill = current.skills[action[0]]
    if current.energy < skill.energy_cost:
        current.gain_energy(5)  # 能量不够时视为汇合聚能
        return
    current.energy -= skill.energy_cost

    if skill.force_switch:
        alive = [i for i, p in enumerate(team_list) if not p.is_fainted and i != idx]
        if alive:
            new_idx = random.choice(alive)
            if team == "a":
                state.current_a = new_idx
            else:
                state.current_b = new_idx
        return  # 脱离后不再执行后续效果

    # 获取对方技能(用于应对判定)
    enemy_skill = None
    if enemy_action[0] >= 0 and not enemy.is_fainted:
        enemy_skill = enemy.skills[enemy_action[0]]

    # 防御技能：直接应用自身效果
    if skill.category == SkillCategory.DEFENSE:
        current.apply_self_buff(skill)
        if skill.self_heal_hp > 0:
            heal = int(current.hp * skill.self_heal_hp)
            current.current_hp = min(current.hp, current.current_hp + heal)
        if skill.self_heal_energy > 0:
            current.gain_energy(skill.self_heal_energy)
        return

    # 状态技能：应用效果
    if skill.category == SkillCategory.STATUS:
        current.apply_self_buff(skill)
        enemy.apply_enemy_debuff(skill)
        if skill.self_heal_hp > 0:
            heal = int(current.hp * skill.self_heal_hp)
            current.current_hp = min(current.hp, current.current_hp + heal)
        if skill.self_heal_energy > 0:
            current.gain_energy(skill.self_heal_energy)
        if skill.steal_energy > 0:
            current.gain_energy(skill.steal_energy)
            enemy.energy = max(0, enemy.energy - skill.steal_energy)
        if skill.enemy_lose_energy > 0:
            enemy.energy = max(0, enemy.energy - skill.enemy_lose_energy)
        if skill.poison_stacks > 0:
            enemy.poison_stacks += skill.poison_stacks
        if skill.burn_stacks > 0:
            enemy.burn_stacks += skill.burn_stacks
        if skill.freeze_stacks > 0:
            enemy.freeze_stacks += skill.freeze_stacks
        if skill.force_switch:
            alive = [i for i, p in enumerate(team_list) if not p.is_fainted and i != idx]
            if alive:
                new_idx = random.choice(alive)
                if team == "a":
                    state.current_a = new_idx
                else:
                    state.current_b = new_idx
        return

    # 攻击技能：先应用 buff/debuff 效果
    current.apply_self_buff(skill)
    enemy.apply_enemy_debuff(skill)

    # 状态附加（攻击技能也可能附带中毒等效果）
    if skill.poison_stacks > 0:
        enemy.poison_stacks += skill.poison_stacks
    if skill.burn_stacks > 0:
        enemy.burn_stacks += skill.burn_stacks
    if skill.freeze_stacks > 0:
        enemy.freeze_stacks += skill.freeze_stacks
        if enemy.freeze_stacks >= 3:
            enemy.status = StatusType.FROZEN

    # 能量效果
    if skill.steal_energy > 0:
        current.gain_energy(skill.steal_energy)
        enemy.energy = max(0, enemy.energy - skill.steal_energy)
    if skill.enemy_lose_energy > 0:
        enemy.energy = max(0, enemy.energy - skill.enemy_lose_energy)

    # 计算伤害
    if skill.power <= 0 or enemy.is_fainted:
        # 无威力攻击技能仍然应用了上面的效果，但不造成伤害
        if skill.self_heal_hp > 0:
            heal = int(current.hp * skill.self_heal_hp)
            current.current_hp = min(current.hp, current.current_hp + heal)
        if skill.self_heal_energy > 0:
            current.gain_energy(skill.self_heal_energy)
        return

    damage = DamageCalculator.calculate(current, enemy, skill)

    # 应对解析
    if enemy_skill and not enemy.is_fainted:
        damage = resolve_counter(current, enemy, skill, enemy_skill, damage)

    enemy.current_hp -= damage
    if enemy.current_hp <= 0:
        enemy.current_hp = 0
        enemy.status = StatusType.FAINTED

    # 吸血
    if skill.life_drain > 0:
        heal = int(damage * skill.life_drain)
        current.current_hp = min(current.hp, current.current_hp + heal)

    # 回复HP
    if skill.self_heal_hp > 0:
        heal = int(current.hp * skill.self_heal_hp)
        current.current_hp = min(current.hp, current.current_hp + heal)
    if skill.self_heal_energy > 0:
        current.gain_energy(skill.self_heal_energy)


def get_priority(state: BattleState, team: str, action: Action) -> float:
    """获取先手修正"""
    if action[0] < 0:
        return 0
    team_list = state.team_a if team == "a" else state.team_b
    idx = state.current_a if team == "a" else state.current_b
    skill = team_list[idx].skills[action[0]]
    return skill.priority_mod * 0.1


def check_winner(state: BattleState) -> Optional[str]:
    if all(p.is_fainted for p in state.team_a):
        return "b"
    if all(p.is_fainted for p in state.team_b):
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
        "岩石": Type.ROCK, "幽灵": Type.GHOST, "龙": Type.DRAGON, "恶": Type.DARK,
        "钢": Type.STEEL, "妖精": Type.FAIRY, "机械": Type.STEEL, "萌": Type.FAIRY,
        "翼": Type.FLYING, "武": Type.FIGHTING, "幽": Type.GHOST, "幻": Type.PSYCHIC,
        "光": Type.ELECTRIC,
    }

    @staticmethod
    def _p(name: str, skill_names: list) -> Pokemon:
        """根据精灵名称从数据库获取六维数据，构造Pokemon对象"""
        from src.pokemon_db import get_pokemon

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
            # 找不到时使用默认值
            print(f"[WARN] 精灵 '{name}' 未在数据库中找到，使用默认属性")
            ptype_str = "普通"
            ability = "未知"
            hp, atk, dfn, spatk, spdef, spd = 500, 350, 350, 350, 350, 350

        type_enum = TeamBuilder.TYPE_MAP.get(ptype_str, Type.NORMAL)
        skills = [get_skill(n) for n in skill_names]
        return Pokemon(name=name, pokemon_type=type_enum,
                       hp=hp, attack=atk, defense=dfn,
                       sp_attack=spatk, sp_defense=spdef,
                       speed=spd, ability=ability, skills=skills)

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

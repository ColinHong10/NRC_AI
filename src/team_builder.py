"""
洛克王国战斗模拟系统 - 队伍构建模块

提供 TeamBuilder 类用于创建标准对战队伍。
"""

from typing import List, Dict, Optional

from src.models import Pokemon, Type
from src.pokemon_db import get_pokemon, calc_combat_stats
from src.skill_db import get_skill, load_ability_effects
from src.effect_models import E


class TeamBuilder:
    """队伍构建器 - 用于创建标准对战队伍"""

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
    def _p(name: str, skill_names: list,
           iv_config: Optional[Dict[str, int]] = None,
           nature: str = "坦率") -> Pokemon:
        """
        根据精灵名称从数据库获取种族值，计算战斗五维构造 Pokemon 对象。

        参数:
          name: 精灵名称
          skill_names: 技能名称列表
          iv_config: 个体值配置 {"hp":60,"atk":60,"spatk":0,"def":0,"spdef":0,"speed":60}
                     默认全 0
          nature: 性格名称（25 种性格之一），默认"坦率"（无修正）
        """
        data = get_pokemon(name)
        if data:
            ptype_str = data["属性"]
            ability = data["特性"]
            # 从种族值计算战斗五维（保留小数）
            stats = calc_combat_stats(
                base_hp=data["生命种族值"],
                base_atk=data["物攻种族值"],
                base_spatk=data["魔攻种族值"],
                base_def=data["物防种族值"],
                base_spdef=data["魔防种族值"],
                base_speed=data["速度种族值"],
                iv_config=iv_config,
                nature_name=nature,
            )
            hp = stats["hp"]
            atk = stats["atk"]
            dfn = stats["def"]
            spatk = stats["spatk"]
            spdef = stats["spdef"]
            spd = stats["speed"]
        else:
            print(f"[WARN] 精灵 '{name}' 未在数据库中找到，使用默认属性")
            ptype_str = "普通"
            ability = "未知"
            hp, atk, dfn, spatk, spdef, spd = 500.0, 350.0, 350.0, 350.0, 350.0, 350.0

        type_enum = TeamBuilder.TYPE_MAP.get(ptype_str, Type.NORMAL)
        skills = [get_skill(n) for n in skill_names]

        # 加载特性效果
        ability_effects = load_ability_effects(ability) if ability else []

        # 构造 Pokemon 对象
        p = Pokemon(
            name=name, pokemon_type=type_enum,
            hp=hp, attack=atk, defense=dfn,
            sp_attack=spatk, sp_defense=spdef,
            speed=spd, ability=ability, skills=skills,
        )

        # 初始化个体值和性格
        if iv_config:
            p.iv_hp = iv_config.get("hp", 0)
            p.iv_atk = iv_config.get("atk", 0)
            p.iv_spatk = iv_config.get("spatk", 0)
            p.iv_def = iv_config.get("def", 0)
            p.iv_spdef = iv_config.get("spdef", 0)
            p.iv_speed = iv_config.get("speed", 0)
        p.nature = nature
        p.ability_effects = ability_effects
        # 初始化被动标记（PASSIVE 特性需要在加载时就设置，确保立即生效）
        for ae in ability_effects:
            for tag in ae.effects:
                if tag.type == E.COST_INVERT:
                    p.ability_state["cost_invert"] = True
                elif tag.type == E.IMMUNE_ZERO_ENERGY_ATTACKER:
                    p.ability_state["immune_zero_energy_attacker"] = True
                elif tag.type == E.IMMUNE_LOW_COST_ATTACK:
                    p.ability_state["immune_low_cost_attack"] = tag.params.get("cost_threshold", 1)
                elif tag.type == E.FIXED_HIT_COUNT_ALL:
                    p.ability_state["fixed_hit_count_all"] = tag.params.get("count", 2)
                elif tag.type == E.HIT_COUNT_PER_POISON:
                    p.ability_state["hit_count_per_poison"] = True
                elif tag.type == E.FAINT_NO_MP_LOSS:
                    p.ability_state["faint_no_mp_loss"] = True
                elif tag.type == E.EXTRA_POISON_TICK:
                    p.ability_state["extra_poison_tick"] = True
                elif tag.type == E.HEAL_PER_TURN:
                    p.ability_state["heal_per_turn_pct"] = tag.params.get("heal_pct", 0.12)
                elif tag.type == E.SHARE_GAINS:
                    p.ability_state["share_gains"] = True
                elif tag.type == E.HALF_METEOR_FULL_DAMAGE:
                    p.ability_state["half_meteor_full_damage"] = True
                elif tag.type == E.CHARGE_FREE_SKILL:
                    p.ability_state["charge_free_skill"] = True
                elif tag.type == E.COST_CHANGE_DOUBLE:
                    p.ability_state["cost_change_double"] = True
                elif tag.type == E.TURN_END_REPEAT:
                    delta = tag.params.get("delta", 1)
                    p.ability_state["turn_end_repeat"] = p.ability_state.get("turn_end_repeat", 0) + delta
                elif tag.type == E.TURN_END_SKIP:
                    delta = tag.params.get("delta", 1)
                    p.ability_state["turn_end_skip"] = p.ability_state.get("turn_end_skip", 0) + delta
                elif tag.type == E.BUFF_EXTRA_LAYERS:
                    p.ability_state["buff_extra_layers"] = tag.params.get("extra", 2)
                # ── 萌化被动 ──
                elif tag.type == E.CUTE_NO_CAP:
                    p.ability_state["cute_no_cap"] = True
                elif tag.type == E.CUTE_HIT_PER_STACK:
                    p.ability_state["cute_hit_per_stack"] = tag.params.get("per", 2)
        return p

    @staticmethod
    def create_toxic_team() -> List[Pokemon]:
        """创建毒队（Team A）"""
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
        """创建翼王队（Team B）"""
        return [
            TeamBuilder._p("燃薪虫", ["火焰护盾", "引燃", "倾泻", "抽枝"]),
            TeamBuilder._p("圣羽翼王", ["水刃", "力量增效", "疾风连袭", "扇风"]),
            TeamBuilder._p("翠顶夫人", ["力量增效", "水刃", "水环", "泡沫幻影"]),
            TeamBuilder._p("迷迷箱怪", ["双星", "啮合传递", "偷袭", "吓退"]),
            TeamBuilder._p("秩序鱿墨", ["风墙", "能量刃", "力量增效", "倾泻"]),
            TeamBuilder._p("声波缇塔", ["轴承支撑", "齿轮扭矩", "地刺", "啮合传递"]),
        ]

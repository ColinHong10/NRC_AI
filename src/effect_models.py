"""
效果原语体系 — 类型定义与数据结构

所有技能和特性的效果都拆解为 EffectTag 列表。
EffectTag = (效果类型, 参数字典, 触发条件, 子效果列表)
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Any


# ============================================================
# 效果类型枚举
# ============================================================
class E(Enum):
    """效果原语类型 (Effect Type)。简写 E 方便数据层引用。"""

    # ── 基础伤害 / 回复 ──
    DAMAGE = auto()                  # 造成伤害 (物伤/魔伤由技能 category 决定)
    HEAL_HP = auto()                 # 回复自身生命  params: {"pct": 0.5} = 50%最大HP
    HEAL_ENERGY = auto()             # 回复能量      params: {"amount": 1}
    STEAL_ENERGY = auto()            # 偷取能量      params: {"amount": 1}
    ENEMY_LOSE_ENERGY = auto()       # 敌方失去能量  params: {"amount": 1}
    LIFE_DRAIN = auto()              # 吸血          params: {"pct": 0.5} = 伤害的50%
    GRANT_LIFE_DRAIN = auto()        # 获得持续吸血  params: {"pct": 0.5}

    # ── 属性修改 ──
    SELF_BUFF = auto()               # 自身增益  params: {"atk":1.0, "spatk":0.7, "speed":80}
                                     #   百分比用小数(1.0=+100%), 速度用整数(+80=speed_mod)
    SELF_DEBUFF = auto()             # 自身减益  params 同上, 值为正数(自动转为 down)
    ENEMY_DEBUFF = auto()            # 敌方减益  params 同上, 值为正数(自动取反)

    # ── 状态附加 ──
    POISON = auto()                  # 中毒  params: {"stacks": 2}
    BURN = auto()                    # 灼烧  params: {"stacks": 4}
    FREEZE = auto()                  # 冻伤  params: {"stacks": 1}
    LEECH = auto()                   # 寄生  params: {"stacks": 1}
    METEOR = auto()                  # 星陨  params: {"stacks": 1}

    # ── 印记系统 (全队共享, 换人不消失) ──
    # 正面印记：同一阵营同时仅存1种，新覆盖旧
    # 负面印记：可多种共存
    POISON_MARK = auto()             # 中毒印记(负面)  params: {"stacks": 1}
    MOISTURE_MARK = auto()           # 湿润印记(正面)  params: {"stacks": 1}
    DRAGON_MARK = auto()             # 龙噬印记(正面)  params: {"stacks": 1}  释放基础能耗==5技能时攻击+40%
    WIND_MARK = auto()               # 风起印记(正面)  params: {"stacks": 1}  先手攻击时威力+20%
    CHARGE_MARK = auto()             # 蓄电印记(正面)  params: {"stacks": 1}  入场首回合技能威力+10
    SOLAR_MARK = auto()              # 光合印记(正面)  params: {"stacks": 1}  回合结束能量+1
    ATTACK_MARK = auto()             # 攻击印记(正面)  params: {"stacks": 1}  威力提升10%
    SLOW_MARK = auto()               # 减速印记(负面)  params: {"stacks": 1}  降低速度10%
    SLUGGISH_MARK = auto()           # 迟缓印记(正面)  params: {"stacks": 1}  后手攻击时威力+30%
    SPIRIT_MARK = auto()             # 降灵印记(负面)  params: {"stacks": 1}  换上场失去1能量
    METEOR_MARK = auto()             # 星陨印记(负面)  params: {"stacks": 1}  造成伤害时消耗,每层30威力魔伤
    THORN_MARK = auto()              # 荆刺印记(负面)  params: {"stacks": 1}  敌方入场失去6%HP
    MOMENTUM_MARK = auto()           # 蓄势印记(正面)  params: {"stacks": 1}  攻击技能威力+30%且能耗+1，可叠加

    # ── 印记特殊操作 ──
    DISPEL_ENEMY_MARKS = auto()      # 驱散敌方印记  params: {}
    CONVERT_MARKS_TO_BURN = auto()   # 印记→灼烧转换  params: {"ratio": 3}
    DISPEL_MARKS_TO_BURN = auto()    # 驱散所有印记,每层→灼烧  params: {"burn_per_mark": 5}
    CONSUME_MARKS_HEAL = auto()      # 驱散敌方印记+回血  params: {"heal_pct_per_mark": 0.1}
    MARKS_TO_METEOR = auto()         # 印记层数→星陨  params: {}
    STEAL_MARKS = auto()             # 偷取敌方印记  params: {}
    ENERGY_COST_PER_ENEMY_MARK = auto()  # 每层敌方印记能耗-1  params: {}

    # ── 机制 ──
    DAMAGE_REDUCTION = auto()        # 减伤       params: {"pct": 0.7} = 减70%
    FORCE_SWITCH = auto()            # 自身脱离   params: {} (选择随机队友)
    FORCE_ENEMY_SWITCH = auto()      # 强制敌方脱离 params: {}
    AGILITY = auto()                 # 迅捷标记   params: {} (入场时自动释放)
    INTERRUPT = auto()               # 打断被应对技能 params: {}

    # ── 动态计算 ──
    POWER_DYNAMIC = auto()           # 动态威力   params: {"condition":"first_strike","bonus_pct":0.5}
                                     #   条件: "first_strike"=先于敌方攻击, "per_poison"=每层中毒+N
    ENERGY_COST_DYNAMIC = auto()     # 动态能耗   params: {"per":"enemy_poison","reduce":1}
                                     #   每层中毒能耗-1
    PERMANENT_MOD = auto()           # 永久修改   params: {"target":"cost","delta":-6} 或
                                     #                    {"target":"power","delta":90}
                                     #   条件: 直接生效 / per_counter / per_position_change
    SKILL_MOD = auto()               # 技能维度修正 params: {"target":"self","stat":"power_pct","value":0.4}
    NEXT_ATTACK_MOD = auto()         # 下一次攻击修正 params: {"power_bonus":70} / {"power_pct":1.0}
    CLEANSE = auto()                 # 清除增减益/状态 params: {"target":"self","mode":"buffs|debuffs|all"}
    SELF_KO = auto()                 # 结算后自身力竭 params: {}
    RESET_SKILL_COST = auto()        # 技能能耗重置为基础值 params: {}
    ENERGY_ALL_IN = auto()           # 消耗所有能量，威力按消耗量缩放
                                     # params: {"power_per_energy": 30}
                                     # 实际威力 = 当前能量 × power_per_energy

    # ── 位置 / 传动 ──
    POSITION_BUFF = auto()           # 位置增益  params: {"positions":[0,2],"buff":{"atk":1.0}}
                                     #   仅当技能在指定位置时额外获得增益
    DRIVE = auto()                   # 传动      params: {"value": 1}
                                     #   使用后向后移动N位触发目标技能的被动效果
    PASSIVE_ENERGY_REDUCE = auto()   # 被动: 相邻技能能耗-N  params: {"reduce":1,"range":"adjacent"}

    # ── 转化 / 驱散 ──
    CONVERT_BUFF_TO_POISON = auto()  # 将敌方所有增益转化为中毒层数  params: {}
    CONVERT_POISON_TO_MARK = auto()  # 中毒→中毒印记  params: {"on":"kill"} 击败时
    DISPEL_MARKS = auto()            # 驱散双方印记  params: {"condition":"not_blocked"}
    CONDITIONAL_BUFF = auto()        # 条件增益  params: {"condition":"enemy_switch","buff":{"speed":70}}
                                     #   或 {"condition":"per_enemy_poison","buff":{"spatk":0.3}}
    DISPEL_BUFFS = auto()            # 驱散增益  params: {"target":"enemy"|"self"}
    DISPEL_DEBUFFS = auto()          # 驱散减益  params: {"target":"enemy"|"self"}

    # ── 应对容器 (子效果) ──
    COUNTER_ATTACK = auto()          # 应对攻击  sub_effects=[...] 当对手用攻击技能时触发
    COUNTER_STATUS = auto()          # 应对状态  sub_effects=[...] 当对手用状态技能时触发
    COUNTER_DEFENSE = auto()         # 应对防御  sub_effects=[...] 当对手用防御技能时触发

    # ── 特殊机制 ──
    MIRROR_DAMAGE = auto()           # 反弹伤害 params: {"source":"countered_skill"} 威力=被应对技能
    ENEMY_ENERGY_COST_UP = auto()    # 敌方攻击技能能耗+N  params: {"amount":6,"filter":"attack"}
    COUNTER_OVERRIDE = auto()        # 应对时替换效果 params: {"replace":"poison","from":2,"to":6}
    WEATHER = auto()                # 设置天气  params: {"type":"sunny"|"rain"|"sandstorm"|"hail","turns":5}

    # ── 特性专用原语 ──
    ABILITY_COMPUTE = auto()         # 运行时计算并存入 ability_state
                                     # params: {"action": "count_poison_skills"|"shared_wing_skills"}
    ABILITY_INCREMENT_COUNTER = auto()  # 计数器+1（海豹船长）
    TRANSFER_MODS = auto()           # 离场时传递属性修正（翠顶夫人洁癖）
    BURN_NO_DECAY = auto()           # 标记: 灼烧本回合不衰减（燃薪虫煤渣草）
    POWER_MULTIPLIER_BUFF = auto()   # 独立威力提升乘法层 params: {"multiplier": 1.5}

    # ── 特性专用原语（数据驱动） ──
    THREAT_SPEED_BUFF = auto()              # 预警/哨兵: 敌方有击杀威胁时速度加成 params: {"speed": 0.5, "force_switch": false}
    COUNTER_ACCUMULATE_TRANSFORM = auto()   # 保卫: 应对成功计数→变身 params: {"threshold": 2, "category_filter": "防御"}
    DELAYED_REVIVE = auto()                 # 不朽: 力竭后延迟复活 params: {"turns": 3}
    COPY_SWITCH_STATE = auto()              # 贪婪: 敌方换人时复制状态 params: {}
    COST_INVERT = auto()                    # 对流: 能耗增减反转（被动标记）params: {}

    # ── 复合 / 特殊 ──
    REPLAY_AGILITY = auto()          # 重放迅捷技能 params: {} (疾风连袭)
    ENERGY_COST_ACCUMULATE = auto()  # 每次使用后能耗+N  params: {"delta":1}
    AGILITY_COST_SHARE = auto()      # 迅捷技能能耗之和的1/2加到本技能 params: {}

    # ── TIER 1 特性专用原语 ──
    COUNTER_SUCCESS_DOUBLE_DAMAGE = auto()      # 应对成功后伤害翻倍（圣火骑士）
    COUNTER_SUCCESS_BUFF_PERMANENT = auto()     # 应对成功后增益永久化 params: {"atk": 0.2, "spatk": 0}
    COUNTER_SUCCESS_POWER_BONUS = auto()        # 应对成功后威力永久+N params: {"delta": 20}
    COUNTER_SUCCESS_COST_REDUCE = auto()        # 应对成功后能耗永久-N params: {"delta": 5}
    COUNTER_SUCCESS_SPEED_PRIORITY = auto()     # 应对成功后速度+1优先级（野性感官）params: {}
    FIRST_STRIKE_POWER_BONUS = auto()           # 先手攻击威力加成 params: {"bonus_pct": 0.75}
    FIRST_STRIKE_HIT_COUNT = auto()             # 先手攻击连击数+1（咔咔冲刺）params: {}
    FIRST_STRIKE_AGILITY = auto()               # 首个技能获得迅捷（起飞加速）params: {}
    AUTO_SWITCH_ON_ZERO_ENERGY = auto()         # 能量为0时自动换人（警惕）params: {}
    AUTO_SWITCH_AFTER_ACTION = auto()           # 每个回合结束后自动换人（防过载保护）params: {}


    # ── TIER 2 特性专用原语 ──
    # Team Synergy (4)
    TEAM_SYNERGY_BUG_SWARM_ATTACK = auto()       # 虫群突袭: +15% stats per other bug params: {"bonus_pct": 0.15}
    TEAM_SYNERGY_BUG_SWARM_INSPIRE = auto()      # 虫群鼓舞: +10% stats per other bug params: {"bonus_pct": 0.1}
    TEAM_SYNERGY_BRAVE_IF_BUGS = auto()          # 壮胆: +50% attack if bugs in team params: {"bonus_pct": 0.5}
    TEAM_SYNERGY_BUG_KILL_AFF = auto()           # 振奋虫心: +5 aff on team kill params: {"aff_bonus": 5}
    
    # Stat Scaling (4)
    STAT_SCALE_DEFENSE_PER_ENERGY = auto()       # 囤积: +10% defense per energy params: {"bonus_pct_per_energy": 0.1}
    STAT_SCALE_HITS_PER_HP_LOST = auto()         # 嫁祸: +2 hits per 25% HP lost params: {"hits_per_quarter": 2}
    STAT_SCALE_ATTACK_DECAY = auto()             # 全神贯注: +100% attack, -20% per action params: {"init_bonus": 1.0, "decay_per_action": 0.2}
    STAT_SCALE_METEOR_MARKS_PER_TURN = auto()    # 吸积盘: +2 meteor marks per turn params: {"marks_per_turn": 2}
    
    # Mark-Based (5)
    MARK_POWER_PER_METEOR = auto()               # 坠星/观星: +15% power per meteor mark params: {"bonus_pct_per_mark": 0.15}
    MARK_FREEZE_TO_METEOR = auto()               # 月牙雪糕: Freeze = meteor mark params: {"convert_freeze_to_mark": 1}
    MARK_STACK_NO_REPLACE = auto()               # 吟游之弦: Marks stack (don't replace) params: {}
    MARK_STACK_DEBUFFS = auto()                  # 灰色肖像: Stack enemy debuffs +3 params: {"stack_bonus": 3}
    
    # Damage Type Modifiers (6)
    DAMAGE_MOD_NON_STAB = auto()                 # 涂鸦: +50% non-STAB power params: {"bonus_pct": 0.5}
    DAMAGE_MOD_NON_LIGHT = auto()                # 目空: +25% non-light power params: {"bonus_pct": 0.25}
    DAMAGE_MOD_NON_WEAKNESS = auto()             # 绒粉星光: +100% vs non-weakness params: {"bonus_pct": 1.0}
    DAMAGE_MOD_POLLUTANT_BLOOD = auto()          # 天通地明: +100% vs pollutant blood params: {"bonus_pct": 1.0}
    DAMAGE_MOD_LEADER_BLOOD = auto()             # 月光审判: +100% vs leader blood params: {"bonus_pct": 1.0}
    DAMAGE_RESIST_SAME_TYPE = auto()             # 偏振: -40% from same-type attacks params: {"resist_pct": 0.4}

    # Healing/Sustain (2)
    HEAL_PER_TURN = auto()                       # 生长: Recover 12% per turn params: {"heal_pct": 0.12}
    HEAL_ON_GRASS_SKILL = auto()                 # 深层氧循环: Recover 15% on grass skill params: {"heal_pct": 0.15}
    
    # Energy Cost Modification (1)
    SKILL_COST_REDUCTION_TYPE = auto()           # 缩壳: -2 cost on defense skills params: {"cost_reduction": 2, "skill_type": "defense"}
    
    # Status Application (2)
    POISON_STAT_DEBUFF = auto()                  # 毒牙: Poison = -40% spatk/spdef params: {"spatk_reduction": 0.4, "spdef_reduction": 0.4}
    POISON_ON_SKILL_APPLY = auto()               # 毒腺: 4-layer poison on low-cost params: {"poison_stacks": 4, "cost_threshold": 5}
    
    # Entry Effects (1)
    FREEZE_IMMUNITY_AND_BUFF = auto()            # 吉利丁片: +20% defense, freeze immune params: {"def_bonus": 0.2}

    # ── 通用特性原语 ──
    EXTRA_FREEZE_ON_FREEZE = auto()     # 加个雪球: 使敌方获得冻结时额外+N层  params: {"extra": 2}
    FAINT_NO_MP_LOSS = auto()           # 诈死: 力竭时不扣MP  params: {}
    ON_SKILL_ELEMENT_BUFF = auto()      # 使用某系技能后获得buff  params: {"element":"火","buff":{"atk":0.2,"spatk":0.2}}
    ON_SKILL_ELEMENT_POISON = auto()    # 使用某系技能后敌方中毒  params: {"element":"草","stacks":2}
    ON_SKILL_ELEMENT_COST_REDUCE = auto()  # 使用某系技能后全能耗-N  params: {"element":"水","reduce":1}
    ON_SKILL_ELEMENT_HEAL = auto()      # 使用某系技能后回血  params: {"element":"草","heal_pct":0.1}
    ON_SKILL_ELEMENT_ENEMY_ENERGY = auto()  # 使用某系技能后敌方失能量  params: {"element":"恶","amount":2}
    CARRY_SKILL_POWER_BONUS = auto()    # 携带某条件技能威力+N%  params: {"condition":"cost_eq","value":1,"bonus_pct":0.5}
    CARRY_SKILL_COST_REDUCE = auto()    # 携带某类技能能耗-N  params: {"category":"defense","reduce":2}
    CARRY_ELEMENT_COUNT_BUFF = auto()   # 每携带N个某系技能获得效果  params: {"element":"水","per_skill":{"cost_reduce":1,"target_element":"地"}}
    ON_KILL_BUFF = auto()               # 击败敌方后获得buff  params: {"buff":{"atk":0.5,"spatk":0.5}}
    RECOIL_DAMAGE = auto()              # 每受到攻击反弹固定伤害  params: {"power":50,"category":"physical"}
    ENTRY_BUFF = auto()                 # 入场时获得buff  params: {"buff":{"atk":1.0},"duration":1}
    ON_ENTER_GRANT_DRAIN = auto()       # 入场时获得吸血  params: {"pct": 0.5}
    ENEMY_ALL_COST_UP = auto()          # 在场时敌方全技能能耗+N  params: {"amount": 1}
    ENTRY_FREEZE_EXTRA = auto()         # 入场时冻结+额外效果  params: {"freeze":2,"extra_cost_up":1}
    LEAVE_HEAL_ALLY = auto()            # 离场后替换精灵回血  params: {"heal_pct":0.2}
    LEAVE_BUFF_ALLY = auto()            # 离场后替换精灵获得buff  params: {"buff":{"atk":0.2,"spatk":0.2}}
    LEAVE_ENERGY_REFILL = auto()        # 离场时回复能量  params: {"amount": 10}
    ENERGY_REGEN_PER_TURN = auto()      # 回合结束回复能量  params: {"amount": 3}
    STEAL_ALL_ENEMY_ENERGY = auto()     # 回合结束偷取敌方全队能量  params: {"amount": 1}
    ENEMY_SWITCH_DEBUFF = auto()        # 敌方换人后对入场者施加效果  params: {"poison": 5} 或 {"energy_loss": 3}
    ENEMY_SWITCH_SELF_COST_REDUCE = auto()  # 敌方换人时自己获得能耗减  params: {"reduce": 3}
    ON_INTERRUPT_COOLDOWN = auto()      # 打断敌方时被打断技能进入冷却  params: {"turns": 2}
    LOW_COST_SKILL_POWER_BONUS = auto() # 能耗≤N的技能威力+M%  params: {"cost_threshold":1,"bonus_pct":0.5}
    ENERGY_COST_CONDITION_BUFF = auto() # 使用能耗为N的技能时获得buff  params: {"cost":3,"buff":{"atk":0.2,"def":0.2}}
    ENEMY_TECH_TOTAL_POWER = auto()     # 敌方技能总能耗越多自己越强  params: {"bonus_pct_per_cost": 0.1}
    HALF_METEOR_FULL_DAMAGE = auto()    # 星陨只消耗一半层数但满伤  params: {}

    # ── 新增特性原语 (第六批) ──
    SPECIFIC_SKILL_POWER_BONUS = auto()  # 共鸣: 携带的指定名称技能威力+N  params: {"skill_name": "虫鸣", "power_bonus": 20}
    ENERGY_NO_CAP = auto()               # 多人宿舍: 能量可超过上限（无上限） params: {}
    HP_FOR_ENERGY = auto()               # 石头大餐: 能量不足时每缺1点消耗5%HP代替 params: {}
    SHUFFLE_SKILLS_REDUCE_LAST = auto()  # 盲拧: 回合开始打乱技能顺序,4号位能耗-4 params: {"cost_reduce": 4}
    WEATHER_CONDITIONAL_BUFF = auto()    # 得寸进尺: 天气条件下获得buff params: {"weather": "rain", "buff": {"atk": 1.0, "spatk": 1.0}}
    FAINTED_ALLIES_BUFF = auto()         # 悲悯/悼亡: 每有1只力竭精灵双攻+N% params: {"buff_per": {"atk": 0.3, "spatk": 0.3}, "scope": "allies"|"all"}
    ON_SUPER_EFFECTIVE_BUFF = auto()     # 最好的伙伴: 造成克制伤害后buff+回能 params: {"buff": {"atk":0.2}, "energy": 2}
    ENEMY_ELEMENT_DIVERSITY_POWER = auto()  # 血型吸引: 敌方每携带1种系别威力+N params: {"power_per_type": 10}
    KILL_MP_PENALTY = auto()             # 付给恶魔的赎价: 击败敌方-1MP/被击败自己-1MP params: {}

    # ── 新增特性原语 (第五批) ──
    HIT_COUNT_PER_POISON = auto()       # 侵蚀: 敌方每有1层中毒连击+1  params: {}
    FIRST_ACTION_HIT_BONUS = auto()     # 噼啪！: 入场首次行动使用次数+1  params: {}
    FIXED_HIT_COUNT_ALL = auto()        # 无差别过滤: 所有精灵连击数固定为2  params: {"count": 2}
    EXTRA_POISON_TICK = auto()          # 复方汤剂: 回合结束中毒额外触发1次  params: {}
    CONDITIONAL_ENTRY_BUFF_TOTAL_COST = auto()  # 保守派: 总能耗<4时双防+80%  params: {"cost_threshold": 4, "buff": {"def": 0.8, "spdef": 0.8}}
    CONDITIONAL_ENTRY_BUFF_MP = auto()  # 图书守卫者: MP=1时双攻+50%  params: {"mp_value": 1, "buff": {"atk": 0.5, "spatk": 0.5}}
    IMMUNE_ZERO_ENERGY_ATTACKER = auto()  # 惊吓: 能量=0的精灵无法对自己造伤  params: {}
    IMMUNE_LOW_COST_ATTACK = auto()     # 逐魂鸟: 能耗≤1的攻击技能无法对自己造伤  params: {"cost_threshold": 1}
    ENTRY_SELF_DAMAGE = auto()          # 铃兰晚钟: 入场时失去一半当前HP  params: {}
    ENERGY_DRAIN_BY_COST_DIFF = auto()  # 石天平: 回合结束敌方失去"己方本回合技能能耗-敌方能耗"的能量  params: {}
    ENTRY_BUFF_PER_SKILL_COUNT = auto()  # 全局计数特性: 入场时按己方技能使用次数给加成
                                          # params: {"count_key":"水"|"状态"|..., "per_count":{...效果描述}}
                                          # per_count 支持: cost_reduce(int), power_pct(float), buff(dict), grant_agility(bool)
                                          # element_filter: 只对某系技能生效

    # ── 第七批特性原语 ──
    TURN_END_REPEAT = auto()             # 双向光速: 回合结束效果触发次数+1  params: {"delta": 1}
    TURN_END_SKIP = auto()               # 陨落: 回合结束效果触发次数-1  params: {"delta": 1}
    COST_CHANGE_DOUBLE = auto()          # 倾轧: 能耗变化效果翻倍  params: {}
    NOISE_DEBUFF = auto()                # 泛音列: 使用状态技能后敌方攻击技能能耗+3持续3回合  params: {"cost_up": 3, "turns": 3}
    SKILL_SLOT_LOCK = auto()             # 正位宝剑/宝剑王牌: 限制可用技能位置  params: {"allowed_slots": [0]} 或 [0,2]
    BUFF_EXTRA_LAYERS = auto()           # 营养液泡: 获得增益时额外+N层  params: {"extra": 2}
    BARREL_STATE = auto()                # 木桶戏法: 离场后替换精灵以木桶状态登场  params: {}

    # ── 迸发子系统 ──
    BURST_POWER_BONUS = auto()           # 电流刺激: 迸发技能威力+N  params: {"bonus": 40}
    BURST_ENEMY_COST_UP = auto()         # 超负荷: 迸发技能让敌方全能耗+1  params: {"amount": 1}
    BURST_ELEMENT_COST_REDUCE = auto()   # 生物电: 指定系迸发能耗-N  params: {"element": "电", "reduce": 2}
    BURST_EXTEND = auto()                # 连续负荷: 迸发效果延长1回合  params: {"extend": 1}

    # ── 奉献子系统 ──
    DEVOTION_GRANT_RANDOM = auto()       # 花精灵: 回合结束随机获得1种奉献1层  params: {}
    DEVOTION_ON_HIT = auto()             # 坚韧铠甲: 受攻击时随机获得1种奉献1层  params: {}

    # ── 传动重构 ──
    DRIVE_POSITION_SHIFT = auto()        # 翼轴: 1号位技能获得迅捷+传动1  params: {"slot": 0, "agility": True, "drive": 1}
    DRIVE_ON_POSITION_CHANGE = auto()    # 机械变式: 技能位置变化时能耗-1  params: {"reduce": 1}

    # ── 蓄力相关 ──
    CHARGE_COST_REDUCE = auto()          # 洄游: 每次蓄力全技能能耗永久-1  params: {"reduce": 1}
    CHARGE_FREE_SKILL = auto()           # 嫉妒: 蓄力状态下可用任一技能  params: {}

    # ── 其他特殊 ──
    SHARE_GAINS = auto()                 # 系统发育: 获得能量/生命时分配给场下精灵  params: {}
    CONTRACT_ENTRY = auto()              # 契约的形状: 入场时根据咕噜球类型触发效果  params: {"ball": "绝缘球"}
    BLOODLINE_ENTRY = auto()             # 稀兽花宝: 入场时根据系别触发效果  params: {"element": "萌"}


# ============================================================
# 触发时机枚举 (用于特性)
# ============================================================
class Timing(Enum):
    """特性触发时机"""
    ON_ENTER = auto()            # 入场时
    ON_LEAVE = auto()            # 离场时 (主动换人/脱离)
    ON_FAINT = auto()            # 自身力竭时
    ON_KILL = auto()             # 击败敌方时
    ON_BE_KILLED = auto()        # 被敌方击败时
    ON_TURN_START = auto()       # 回合开始（行动前）
    ON_TURN_END = auto()         # 回合结束时
    ON_USE_SKILL = auto()        # 使用技能后 (可按系别过滤)
    ON_COUNTER_SUCCESS = auto()  # 应对成功时
    ON_ENEMY_SWITCH = auto()     # 敌方换人时
    ON_ALLY_COUNTER = auto()     # 己方任意精灵应对成功时 (海豹船长)
    PASSIVE = auto()             # 常驻被动 (在场时持续生效)
    ON_TAKE_HIT = auto()         # 受到攻击时 (秩序鱿墨)
    ON_BATTLE_START = auto()     # 战斗开始/首次入场时 (千棘盔溶解扩散)


# ============================================================
# 效果标签
# ============================================================
class EffectTag:
    """
    效果原语标签。

    Attributes:
        type:        效果类型 (E 枚举)
        params:      参数字典 (不同效果类型有不同参数)
        condition:   触发条件 (可选, 仅特性需要)
        sub_effects: 子效果列表 (应对容器用)
    """
    __slots__ = ("type", "params", "condition", "sub_effects")

    def __init__(
        self,
        type: E,
        params: Optional[Dict[str, Any]] = None,
        condition: Optional[Dict[str, Any]] = None,
        sub_effects: Optional[List["EffectTag"]] = None,
    ):
        self.type = type
        self.params = params or {}
        self.condition = condition or {}
        self.sub_effects = sub_effects or []

    def __repr__(self):
        parts = [f"E.{self.type.name}"]
        if self.params:
            parts.append(f"params={self.params}")
        if self.condition:
            parts.append(f"cond={self.condition}")
        if self.sub_effects:
            parts.append(f"sub={self.sub_effects}")
        return f"EffectTag({', '.join(parts)})"

    def copy(self) -> "EffectTag":
        return EffectTag(
            type=self.type,
            params=dict(self.params),
            condition=dict(self.condition),
            sub_effects=[e.copy() for e in self.sub_effects],
        )


# ============================================================
# 特性效果定义
# ============================================================
class AbilityEffect:
    """
    特性效果 = 触发时机 + 条件过滤 + 效果标签列表。

    Attributes:
        timing:   触发时机 (Timing 枚举)
        filter:   过滤条件 {"element": "水系"} = 仅水系技能触发
        effects:  效果标签列表
    """
    __slots__ = ("timing", "filter", "effects")

    def __init__(
        self,
        timing: Timing,
        effects: List[EffectTag],
        filter: Optional[Dict[str, Any]] = None,
    ):
        self.timing = timing
        self.effects = effects
        self.filter = filter or {}

    def __repr__(self):
        return f"AbilityEffect(timing={self.timing.name}, filter={self.filter}, effects={self.effects})"

    def copy(self) -> "AbilityEffect":
        return AbilityEffect(
            timing=self.timing,
            effects=[e.copy() for e in self.effects],
            filter=dict(self.filter),
        )


# ============================================================
# 技能触发时机枚举
# ============================================================
class SkillTiming(Enum):
    """技能效果触发时机 — 让技能具备和特性一样的显式阶段语义。"""
    PRE_USE    = auto()  # 使用前：能耗调整、威力修正、自身 buff
    ON_USE     = auto()  # 使用时：主体伤害、状态附加、减伤
    ON_HIT     = auto()  # 命中后（有伤害才触发）：吸血、击败时效果
    ON_COUNTER = auto()  # 应对时：替代 COUNTER_ATTACK/STATUS/DEFENSE 容器
    IF         = auto()  # 条件满足时：敌换宠、血量阈值、上回合状态
    POST_USE   = auto()  # 使用后：反噬自损、传动、敏捷、能耗累加


# ============================================================
# 技能效果定义
# ============================================================
class SkillEffect:
    """
    技能效果 = 触发时机 + 条件过滤 + 效果标签列表。
    与 AbilityEffect 同构，但使用 SkillTiming 枚举。

    filter 键值:
      category      "attack"/"status"/"defense" — 应对匹配类型
      enemy_switch   True — 敌方本回合换宠
      first_strike   True — 先手时
      self_hp_lt     0.5  — 己方HP低于50%
      self_hp_gt     0.5  — 己方HP高于50%
      per            "enemy_poison" — 按层数缩放
      on_kill        True — 击败敌方时
      energy_zero_after True — 使用后能量为0
      prev_counter_success True — 上回合应对成功
      counter        True — 在应对阶段触发（偷袭3倍威力）
    """
    __slots__ = ("timing", "effects", "filter")

    def __init__(
        self,
        timing: SkillTiming,
        effects: List[EffectTag],
        filter: Optional[Dict[str, Any]] = None,
    ):
        self.timing = timing
        self.effects = effects
        self.filter = filter or {}

    def __repr__(self):
        return f"SkillEffect(timing={self.timing.name}, filter={self.filter}, effects={self.effects})"

    def copy(self) -> "SkillEffect":
        return SkillEffect(
            timing=self.timing,
            effects=[e.copy() for e in self.effects],
            filter=dict(self.filter),
        )

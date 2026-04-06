# 洛克王国战斗模拟器 — 技能和特性配置系统详解

## 一、核心架构概览

整个效果系统基于 **EffectTag 原语体系** 和 **双层配置** (skills + abilities)：

### 配置文件结构
- **effect_models.py**: 定义所有枚举和数据结构
- **effect_data.py**: 手工配置的技能和特性效果（SKILL_EFFECTS, ABILITY_EFFECTS）
- **skill_effects_generated.py**: 自动生成的技能效果（需要更新时通过脚本生成）
- **effect_engine.py**: 效果执行引擎（所有原语的 handler 注册表）
- **battle.py**: 战斗流程，印记应用等
- **models.py**: 数据模型（BattleState、Pokemon、Skill 等）

---

## 二、效果类型枚举 (E Enum)

### 基础伤害/回复
```python
E.DAMAGE              # 造成伤害 (物伤/魔伤由技能 category 决定)
E.HEAL_HP             # 回复自身生命 params: {"pct": 0.5}
E.HEAL_ENERGY         # 回复能量 params: {"amount": 1}
E.STEAL_ENERGY        # 偷取能量
E.ENEMY_LOSE_ENERGY   # 敌方失去能量
E.LIFE_DRAIN          # 吸血 params: {"pct": 0.5}
```

### 属性修改
```python
E.SELF_BUFF           # 自身增益 params: {"atk":1.0, "spatk":0.7, "speed":80}
E.SELF_DEBUFF         # 自身减益
E.ENEMY_DEBUFF        # 敌方减益 params: {"def": 1.2} (正数自动取反)
```

### 状态附加 (个体状态，换人清除)
```python
E.POISON              # 中毒 params: {"stacks": 2}
E.BURN                # 灼烧 params: {"stacks": 4}
E.FREEZE              # 冻伤
E.LEECH               # 寄生
E.METEOR              # 星陨
```

### 印记系统 (全队共享，换人不消失) ⭐
```python
E.POISON_MARK         # 中毒印记 params: {"stacks": 1}
E.MOISTURE_MARK       # 湿润印记 params: {"stacks": 1, "target": "self"}
```

### 机制效果
```python
E.DAMAGE_REDUCTION    # 减伤 params: {"pct": 0.7}
E.FORCE_SWITCH        # 自身脱离
E.FORCE_ENEMY_SWITCH  # 强制敌方脱离
E.AGILITY             # 迅捷标记（入场时自动释放）
E.INTERRUPT           # 打断被应对技能
```

### 动态计算
```python
E.POWER_DYNAMIC       # 动态威力 params: {"condition":"first_strike","bonus_pct":0.5}
E.ENERGY_COST_DYNAMIC # 动态能耗 params: {"per":"enemy_poison","reduce":1}
E.PERMANENT_MOD       # 永久修改 params: {"target":"cost","delta":-6}
E.NEXT_ATTACK_MOD     # 下一次攻击修正
```

### 位置/传动
```python
E.POSITION_BUFF       # 位置增益（仅特定位置）
E.DRIVE               # 传动 params: {"value": 1}
E.PASSIVE_ENERGY_REDUCE # 被动: 相邻技能能耗-N
```

### 转化/驱散
```python
E.CONVERT_BUFF_TO_POISON    # 敌方增益→中毒层数
E.CONVERT_POISON_TO_MARK    # 中毒→中毒印记 params: {"on":"kill"}
E.DISPEL_MARKS              # 驱散双方印记
E.CONDITIONAL_BUFF          # 条件增益
E.DISPEL_BUFFS              # 驱散增益
E.DISPEL_DEBUFFS            # 驱散减益
```

### 应对容器 (子效果)
```python
E.COUNTER_ATTACK      # 应对攻击，当对手用攻击技能时触发
E.COUNTER_STATUS      # 应对状态，当对手用状态技能时触发
E.COUNTER_DEFENSE     # 应对防御，当对手用防御技能时触发
```

### 特性专用
```python
E.ABILITY_COMPUTE                 # 运行时计算
E.ABILITY_INCREMENT_COUNTER       # 计数器+1
E.TRANSFER_MODS                   # 传递属性修正
E.BURN_NO_DECAY                   # 灼烧不衰减
E.THREAT_SPEED_BUFF               # 预警/哨兵
E.COUNTER_ACCUMULATE_TRANSFORM    # 保卫变身
E.DELAYED_REVIVE                  # 不朽复活
E.COPY_SWITCH_STATE               # 贪婪复制状态
E.COST_INVERT                     # 对流能耗反转
```

---

## 三、触发时机 (Timing & SkillTiming)

### 特性触发时机 (Timing Enum)
```python
Timing.ON_ENTER              # 入场时
Timing.ON_LEAVE              # 离场时（主动换人/脱离）
Timing.ON_FAINT              # 自身力竭时
Timing.ON_KILL               # 击败敌方时
Timing.ON_BE_KILLED          # 被敌方击败时
Timing.ON_TURN_START         # 回合开始（行动前）
Timing.ON_TURN_END           # 回合结束时
Timing.ON_USE_SKILL          # 使用技能后（可按系别过滤）
Timing.ON_COUNTER_SUCCESS    # 应对成功时
Timing.ON_ENEMY_SWITCH       # 敌方换人时
Timing.ON_ALLY_COUNTER       # 己方任意精灵应对成功时
Timing.PASSIVE               # 常驻被动（在场时持续生效）
Timing.ON_TAKE_HIT           # 受到攻击时
Timing.ON_BATTLE_START       # 战斗开始/首次入场时
```

### 技能触发时机 (SkillTiming Enum)
```python
SkillTiming.PRE_USE    # 使用前：能耗调整、威力修正、自身 buff
SkillTiming.ON_USE     # 使用时：主体伤害、状态附加、减伤
SkillTiming.ON_HIT     # 命中后（有伤害才触发）：吸血、击败时效果
SkillTiming.ON_COUNTER # 应对时：替代 COUNTER_ATTACK/STATUS/DEFENSE 容器
SkillTiming.IF         # 条件满足时：敌换宠、血量阈值、上回合状态
SkillTiming.POST_USE   # 使用后：反噬自损、传动、敏捷、能耗累加
```

---

## 四、配置工厂函数

### 效果标签工厂 (effect_data.py)
```python
def T(etype: E, _params: dict = None, **params) -> EffectTag:
    """快捷构造单个 EffectTag"""
    # 用法示例：
    T(E.POISON, stacks=2)                    # → E.POISON, {"stacks": 2}
    T(E.SELF_BUFF, atk=1.0, spatk=0.7)       # → E.SELF_BUFF, {"atk": 1.0, "spatk": 0.7}
    T(E.MOISTURE_MARK, stacks=1, target="self")  # → 湿润印记给自己

def SE(timing: SkillTiming, effects, **filt) -> SkillEffect:
    """快捷构造 SkillEffect (技能效果)"""
    # 用法示例：
    SE(SkillTiming.ON_USE, [T(E.DAMAGE)])
    SE(SkillTiming.ON_COUNTER, [], category="attack")
    SE(SkillTiming.IF, [T(E.SELF_BUFF, speed=0.7)], enemy_switch=True)

def AE(timing: Timing, effects: list, **filter_kw) -> AbilityEffect:
    """快捷构造 AbilityEffect (特性效果)"""
    # 用法示例：
    AE(Timing.ON_TURN_END, [T(E.HEAL_ENERGY, amount=6)])
    AE(Timing.ON_USE_SKILL, [T(E.POISON, stacks=5)], element="水")
```

---

## 五、现实配置示例

### 示例1：打湿 (自己获得1层湿润印记)
```python
"打湿": [
    SE(SkillTiming.ON_USE, [T(E.MOISTURE_MARK, stacks=1, target="self")]),
]
```

**关键点**:
- `target="self"` 指定印记给自己（默认给敌方）
- 湿润印记存储在 `state.marks_a` 或 `state.marks_b`（全队共享）
- 每回合行动前通过 `_apply_moisture_mark()` 消耗印记并永久减少能耗

### 示例2：疫病吐息 (敌方获得1层中毒印记)
```python
"疫病吐息": [
    SE(SkillTiming.ON_USE, [T(E.POISON_MARK, stacks=1)]),
]
```

### 示例3：毒液渗透 (动态能耗 + 伤害 + 中毒)
```python
"毒液渗透": [
    SE(SkillTiming.PRE_USE, [T(E.ENERGY_COST_DYNAMIC, per="enemy_poison", reduce=1)]),
    SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.POISON, stacks=1)]),
]
```

**动态能耗原理**:
1. 在 `battle.py` 的 `execute_turn_for_team()` 中计算实际能耗
2. 检查 `skill.effects` 中是否有 `E.ENERGY_COST_DYNAMIC`
3. 若 `per="enemy_poison"`，则 `actual_cost -= enemy.poison_stacks * reduce`
4. 若特性有 `cost_invert`，则增减反转

### 示例4：感染病 (击败时中毒→印记)
```python
"感染病": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
    SE(SkillTiming.ON_HIT, [T(E.CONVERT_POISON_TO_MARK, on="kill")], on_kill=True),
]
```

**击败条件判断** (effect_engine.py):
```python
if filt.get("on_kill"):
    damage_dealt = ctx.result.get("damage", 0)
    target_dead = ctx.target.is_fainted or (
        damage_dealt > 0 and ctx.target.current_hp <= damage_dealt
    )
```

### 示例5：以毒攻毒 (每层敌方中毒+30% 魔攻)
```python
"以毒攻毒": [
    SE(SkillTiming.PRE_USE, [T(E.CONDITIONAL_BUFF, condition="per_enemy_poison", 
                                                   buff={"spatk": 0.3})]),
]
```

**条件增益处理** (effect_engine.py):
```python
elif condition == "per_enemy_poison":
    stacks = ctx.target.poison_stacks
    if stacks > 0:
        scaled_buff = {k: v * stacks for k, v in buff.items()}
        _apply_buff(ctx.user, scaled_buff)
```

### 示例6：火焰护盾 (减伤70% + 应对攻击给4层灼烧)
```python
"火焰护盾": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
    SE(SkillTiming.ON_COUNTER, [T(E.BURN, stacks=4)], category="attack"),
]
```

**应对类别过滤**:
- `category="attack"`: 仅对敌方攻击类技能触发
- `category="status"`: 仅对敌方状态类技能触发
- `category="defense"`: 仅对敌方防御类技能触发

### 示例7：特性 — 溶解扩散 (千棘盔)
```python
"溶解扩散": [
    AE(Timing.ON_BATTLE_START,
       [T(E.ABILITY_COMPUTE, action="count_poison_skills")]),
    AE(Timing.ON_USE_SKILL,
       [T(E.POISON, stacks_per_poison_skill=True)],
       element="水"),
]
```

**特性过滤**:
- `element="水"`: 仅当使用水系技能时触发
- 其他过滤: `element=["水", "武"]` (多系别)

### 示例8：特性 — 蚀刻 (裘卡)
```python
"蚀刻": [
    AE(Timing.ON_TURN_END,
       [T(E.CONVERT_POISON_TO_MARK, ratio=2)]),
]
```

**转换逻辑** (effect_engine.py):
```python
def _h_convert_poison_to_mark(tag: EffectTag, ctx: Ctx) -> None:
    ratio = tag.params.get("ratio", 0)
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    stacks = ctx.target.poison_stacks
    converted = stacks // ratio  # 每2层转1层
    if converted > 0:
        ctx.target.poison_stacks -= converted * ratio
        marks["poison_mark"] = marks.get("poison_mark", 0) + converted
```

---

## 六、DOT 效果 (持续伤害状态) 配置模式

### 中毒 (E.POISON)
- 个体状态，换人清除
- 配置: `T(E.POISON, stacks=1)` → `pokemon.poison_stacks += 1`
- 每回合伤害: 3% HP（由 battle.py 处理）
- 中毒印记是全队共享版本 (E.POISON_MARK)

### 灼烧 (E.BURN)
- 个体状态，换人清除
- 配置: `T(E.BURN, stacks=4)` → `pokemon.burn_stacks += 4`
- 每回合伤害: 4% HP，每回合衰减（min=1）
- 特殊: 煤渣草特性可阻止衰减

### 配置示例:
```python
# 引燃: 10层灼烧
"引燃": [
    SE(SkillTiming.ON_USE, [T(E.BURN, stacks=10)]),
]

# 火焰护盾: 防御后应对攻击给4层灼烧
"火焰护盾": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
    SE(SkillTiming.ON_COUNTER, [T(E.BURN, stacks=4)], category="attack"),
]
```

---

## 七、能量系统配置

### 能量成本定义 (models.py Skill)
```python
@dataclass
class Skill:
    energy_cost: int        # 基础能耗 (0-10)
    _base_energy_cost: int  # 保存原始值（用于重置）
```

### 能耗修改途径

#### 1. 技能自身动态能耗 (PRE_USE 阶段)
```python
SE(SkillTiming.PRE_USE, [T(E.ENERGY_COST_DYNAMIC, per="enemy_poison", reduce=1)]),
```

执行位置 (battle.py):
```python
actual_cost = max(0, skill.energy_cost + getattr(current, "skill_cost_mod", 0))
for tag in _iter_flat_tags(getattr(skill, "effects", [])):
    if tag.type == E.ENERGY_COST_DYNAMIC:
        per = tag.params.get("per", "")
        reduce = tag.params.get("reduce", 0)
        if per == "enemy_poison":
            refund = enemy.poison_stacks * reduce
            actual_cost = max(0, actual_cost - refund)
```

#### 2. 永久能耗修改 (PERMANENT_MOD)
```python
SE(SkillTiming.ON_COUNTER, [T(E.PERMANENT_MOD, target="cost", delta=-4)], category="status"),
```

示例: 水刃应对状态时永久-4能耗

#### 3. 被动全队能耗减少 (PASSIVE_ENERGY_REDUCE)
```python
SE(SkillTiming.ON_USE, [
    T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="self"),
    T(E.PASSIVE_ENERGY_REDUCE, reduce=1, range="adjacent"),
]),
```

#### 4. 湿润印记能耗减少 (MOISTURE_MARK)
```python
"打湿": [
    SE(SkillTiming.ON_USE, [T(E.MOISTURE_MARK, stacks=1, target="self")]),
]
```

处理逻辑 (battle.py `_apply_moisture_mark()`):
```python
def _apply_moisture_mark(state: BattleState) -> None:
    """每层为己方全队所有技能能耗永久 -1"""
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
        marks["moisture_mark"] = 0  # 消耗印记
```

**执行时机**: 每回合开始时 (`execute_full_turn()` 的 `_apply_moisture_mark()`)

#### 5. 特性能耗修改
```python
"快充": [
    AE(Timing.ON_LEAVE, [T(E.HEAL_ENERGY, amount=10)]),
]
```

---

## 八、印记系统 (Marks) 详解

### 数据结构
```python
@dataclass
class BattleState:
    marks_a: Dict[str, float] = field(default_factory=dict)  # A队全队共享Buff
    marks_b: Dict[str, float] = field(default_factory=dict)  # B队全队共享Buff
    # 结构: {"atk": 0.3, "def": 0.2, "poison_mark": 3, ...}
```

### 印记类型

| 印记名 | 代码 | 效果 | 应用方式 |
|------|------|------|---------|
| 中毒印记 | `E.POISON_MARK` | 全队共享中毒 | 配置技能/特性时 |
| 湿润印记 | `E.MOISTURE_MARK` | 全队能耗-N | 回合开始应用 |

### 印记处理器

#### POISON_MARK Handler
```python
def _h_poison_mark(tag: EffectTag, ctx: Ctx) -> None:
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    marks["poison_mark"] = marks.get("poison_mark", 0) + tag.params.get("stacks", 1)
```

**特点**: 总是给敌方全队（无 `target` 参数）

#### MOISTURE_MARK Handler
```python
def _h_moisture_mark(tag: EffectTag, ctx: Ctx) -> None:
    tgt = tag.params.get("target", "enemy")
    if tgt == "self":
        marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    else:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    marks["moisture_mark"] = marks.get("moisture_mark", 0) + tag.params.get("stacks", 1)
```

**特点**: 支持 `target="self"` 给自己全队或 `target="enemy"` 给敌方

### 印记消费示例

#### 感染病 (击败时中毒→中毒印记)
```python
"感染病": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE)]),
    SE(SkillTiming.ON_HIT, [T(E.CONVERT_POISON_TO_MARK, on="kill")], on_kill=True),
]
```

处理逻辑:
```python
def _h_convert_poison_to_mark(tag: EffectTag, ctx: Ctx) -> None:
    on = tag.params.get("on", "")
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    if on == "kill" and ctx.target.is_fainted:
        stacks = ctx.target.poison_stacks
        marks["poison_mark"] = marks.get("poison_mark", 0) + stacks
        ctx.target.poison_stacks = 0
```

#### 蚀刻 (每2层中毒转1层印记)
```python
"蚀刻": [
    AE(Timing.ON_TURN_END, [T(E.CONVERT_POISON_TO_MARK, ratio=2)]),
]
```

处理逻辑:
```python
elif ratio > 0:
    stacks = ctx.target.poison_stacks
    converted = stacks // ratio
    if converted > 0:
        ctx.target.poison_stacks -= converted * ratio
        marks["poison_mark"] = marks.get("poison_mark", 0) + converted
```

---

## 九、应对系统 (Counter) 配置

### 应对容器类型
```python
E.COUNTER_ATTACK   # 应对攻击类技能
E.COUNTER_STATUS   # 应对状态类技能
E.COUNTER_DEFENSE  # 应对防御类技能
```

### 应对配置示例

#### 泡沫幻影 (减伤 + 应对攻击脱离)
```python
"泡沫幻影": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.7)]),
    SE(SkillTiming.ON_COUNTER, [T(E.FORCE_SWITCH)], category="attack"),
]
```

#### 毒囊 (攻击 + 中毒，应对状态改为6层)
```python
"毒囊": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE), T(E.POISON, stacks=2)]),
    SE(SkillTiming.ON_COUNTER, [T(E.COUNTER_OVERRIDE, replace="poison", **{"from": 2, "to": 6})], 
       category="status"),
]
```

#### 听桥 (减伤60% + 应对攻击反弹)
```python
"听桥": [
    SE(SkillTiming.ON_USE, [T(E.DAMAGE_REDUCTION, pct=0.6)]),
    SE(SkillTiming.ON_COUNTER, [T(E.MIRROR_DAMAGE, source="countered_skill")], category="attack"),
]
```

### 应对判定逻辑 (battle.py)
```python
def _skill_has_counter_for(skill_a, skill_b) -> bool:
    """检查 skill_a 是否有对 skill_b 类型的应对"""
    cat_map = {
        SkillCategory.PHYSICAL: "attack",
        SkillCategory.MAGICAL: "attack",
        SkillCategory.STATUS: "status",
        SkillCategory.DEFENSE: "defense",
    }
    enemy_cat = cat_map.get(skill_b.category, "")
    # 检查 skill_a 是否有相应 ON_COUNTER 效果...
```

---

## 十、关键运行时变量和流程

### Pokemon 字段
```python
# 个体状态（换人清除）
poison_stacks: int          # 中毒层数
burn_stacks: int            # 灼烧层数
freeze_stacks: int          # 冻伤
leech_stacks: int           # 寄生
frostbite_damage: int       # 冻伤累计不可恢复伤害（不清除）

# 属性修正（拆分方向）
atk_up/atk_down: float      # 物攻提升/降低
def_up/def_down: float      # 物防提升/降低
spatk_up/spatk_down: float  # 魔攻提升/降低
spdef_up/spdef_down: float  # 魔防提升/降低
speed_up/speed_down: float  # 速度提升/降低

# 能力阶段
power_multiplier: float     # 独立威力提升乘法层
skill_power_bonus: int      # 威力加法修正
skill_cost_mod: int         # 能耗修正

# 特性运行时状态
ability_effects: List[AbilityEffect]    # 特性效果列表
ability_state: Dict[str, Any]           # 运行时状态字典
  - poison_skill_count: 携带毒系技能数
  - threat_speed_bonus_active: 预警/哨兵标记
  - cost_invert: 对流标记
  - last_skill_turn: 上次使用技能的回合
  - last_skill_category: 上次技能的类别
```

### BattleState 字段
```python
marks_a/marks_b: Dict[str, float]      # 全队印记
  - "poison_mark": N
  - "moisture_mark": N

counter_count_a/counter_count_b: int   # 全队应对计数
switch_this_turn_a/b: bool             # 本回合是否换人
```

### EffectExecutor 执行上下文
```python
class Ctx:
    state: BattleState               # 战斗状态
    user: Pokemon                    # 使用者
    target: Pokemon                  # 目标
    skill: Skill                     # 技能
    result: Dict                     # 结果字典（handler 在此写入结果）
    is_first: bool                   # 是否先手
    team: str                        # 队伍 ("a"/"b")
    enemy_skill: Skill               # 敌方技能
    damage: int                      # 伤害值
```

### result 字典常用键
```python
result = {
    "damage": int,                       # 造成伤害
    "_damage_reduction": float,          # 减伤百分比
    "_power_mult": float,                # 威力乘数
    "_power_bonus": int,                 # 威力加法
    "_energy_refund": int,               # 能耗返还
    "_dispel_if_not_blocked": bool,      # 未被防御时驱散
    "force_switch": bool,                # 强制脱离
    "counter_effects": List[EffectTag],  # 应对效果列表
    # ... 更多
}
```

---

## 十一、自动生成脚本说明

文件: `scripts/generate_skill_effects.py`

用途: 根据技能描述文本自动生成 `skill_effects_generated.py`

**手工配置流程**:
1. 如果技能比较复杂，在 `effect_data.py` 的 `SKILL_EFFECTS` 中手工配置
2. 简单技能通过脚本自动生成到 `skill_effects_generated.py`
3. `skill_db.py` 的 `load_skills()` 会合并两个字典

---

## 十二、技能配置清单

### 新增技能时的检查列表

- [ ] **步骤1**: 确定技能属于哪个类别
  - 攻击类: 物攻/魔攻 + DAMAGE 效果
  - 防御类: DAMAGE_REDUCTION + ON_COUNTER
  - 状态类: 无 DAMAGE 或只有 BUFF 效果

- [ ] **步骤2**: 确定效果触发时机
  - PRE_USE: 能耗修正、威力修正、入场 buff
  - ON_USE: 主要伤害、状态附加、减伤
  - ON_HIT: 击败时效果、吸血（有伤害才触发）
  - ON_COUNTER: 应对效果
  - POST_USE: 反噬、传动、能耗累加

- [ ] **步骤3**: 检查是否有应对
  - 防御/状态技能通常有 ON_COUNTER 子效果
  - 指定 category: "attack"/"status"/"defense"

- [ ] **步骤4**: 检查是否涉及印记/能量
  - 印记: 使用 POISON_MARK/MOISTURE_MARK
  - 能量: 使用 HEAL_ENERGY/ENEMY_LOSE_ENERGY/ENERGY_COST_DYNAMIC

- [ ] **步骤5**: 测试并验证
  - 在 `src/effect_engine.py` 中有对应 handler
  - 在 `tests/` 中添加单元测试

---

## 十三、常见模式速查

### 模式: 给敌方状态
```python
T(E.POISON, stacks=2)
T(E.BURN, stacks=4)
T(E.FREEZE, stacks=1)
T(E.LEECH, stacks=1)
```

### 模式: 给敌方印记
```python
T(E.POISON_MARK, stacks=1)
```

### 模式: 给自己印记或能耗减少
```python
T(E.MOISTURE_MARK, stacks=1, target="self")
```

### 模式: 动态威力
```python
T(E.POWER_DYNAMIC, condition="first_strike", bonus_pct=0.5)
T(E.POWER_DYNAMIC, condition="per_enemy_poison", bonus_per_stack=10)
T(E.POWER_DYNAMIC, condition="counter", multiplier=3.0)
```

### 模式: 动态能耗
```python
T(E.ENERGY_COST_DYNAMIC, per="enemy_poison", reduce=1)
```

### 模式: 应对
```python
SE(SkillTiming.ON_COUNTER, [T(E.BURN, stacks=4)], category="attack")
SE(SkillTiming.ON_COUNTER, [T(E.FORCE_SWITCH)], category="attack")
SE(SkillTiming.ON_COUNTER, [T(E.INTERRUPT)], category="status")
```

### 模式: 特性在特定时机
```python
AE(Timing.ON_ENTER, [effects])
AE(Timing.ON_LEAVE, [effects])
AE(Timing.ON_TURN_END, [effects])
AE(Timing.ON_USE_SKILL, [effects], element="水")
```

---

## 十四、总结

| 概念 | 存储位置 | 清除条件 | 备注 |
|------|---------|---------|------|
| 个体状态 | `pokemon.{poison,burn}_stacks` | 换人时 | 中毒/灼烧/寄生 |
| 属性修正 | `pokemon.{atk,def,spatk,...}_{up,down}` | 换人时 | 拆分方向计算 |
| 全队印记 | `state.marks_{a,b}` | 不清除 | POISON_MARK/MOISTURE_MARK |
| 能耗修正 | `skill.energy_cost` | 技能永久改变或回合重置 | PERMANENT_MOD/ENERGY_COST_DYNAMIC |
| 威力修正 | `pokemon.{power_multiplier,skill_power_bonus,...}` | 换人时 | 多层叠加 |


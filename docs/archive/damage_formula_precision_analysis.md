# 伤害公式精度分析

**Date**: 2026-04-07  
**Status**: 规划阶段  
**Priority**: P0（最高）

---

## 1. 当前伤害公式分解

### 1.1 完整公式

```
伤害 = 基础伤害 × 属性克制 × 本系加成 × 天气修正 × 连击 × 威力提升buff
    = [(攻/防) × 威力 × 0.9] × 克制倍率 × 本系加成(1.5/1.0) × 天气倍率 × 连击数 × 威力提升buff
```

**要点**：
- 各乘法层严格按此顺序应用
- 都是乘法，没有加法混合
- 最后 `max(1, int(...))` 向下取整且最少 1 点伤害

### 1.2 代码实现位置

**File**: `src/battle.py:206-268` (DamageCalculator.calculate)

| 公式项 | 代码行 | 精确计算 |
|-------|-------|--------|
| **base** | 239-246 | `(攻/防) × 威力 × 0.9` |
| **eff** (属性克制) | 248-249 | `get_type_effectiveness(skill_type, def_type)` |
| **stab** (本系加成) | 251-252 | `1.5 if skill_type == attacker_type else 1.0` |
| **weather_mult** | 254-259 | 天气表查询 + Type 枚举转换 |
| **hits** | 262 | `skill.hit_count` |
| **power_mult_buff** | 265 | `attacker.power_multiplier` |
| **final dmg** | 267 | 所有项相乘，向下取整 |

### 1.3 能力等级计算

**Code**: `src/battle.py:239-240`

```python
ability_level = (1.0 + atk_up + def_down) / max(0.1, 1.0 + atk_down + def_up)
```

**关键**：
- 分子 = 1 + 我方攻升 + 敌方防降
- 分母 = 1 + 我方攻降 + 敌方防升
- 分母最小 0.1（保护除数）

**字段含义**（按技能类别选择）：
- 物理：`atk_up/atk_down/def_up/def_down`
- 魔法：`spatk_up/spatk_down/spdef_up/spdef_down`

---

## 2. 威力提升系统

### 2.1 威力加成 vs 威力百分比

**Source**: `src/effect_engine.py:350-366`

```python
power = (
    skill.power                          # 基础威力
    + ctx.user.skill_power_bonus         # 威力加成(+N)
    + ctx.user.next_attack_power_bonus   # 下一次攻击威力加成
    + ctx.result.get("_power_bonus", 0)  # 技能内部 power bonus
)

power_mult = (
    1.0
    + ctx.user.skill_power_pct_mod       # 威力百分比 mod(+20% = +0.2)
    + ctx.user.next_attack_power_pct     # 下一次攻击威力百分比
    + (ctx.result.get("_power_mult", 1.0) - 1.0)  # 技能内部倍数
)

if power_mult != 1.0:
    power = int(power * power_mult)
```

**要点**：
- `skill_power_bonus` → 加到基础威力 → 再乘以倍数
- `skill_power_pct_mod` → 乘以威力（是百分比）
- `power_multiplier_buff` → 最终乘法层（完全独立）

### 2.2 三层威力修正的优先级

1. **PRE_USE**: 调整基础威力（bonus）+ 倍数（pct_mod）
2. **ON_USE**: DamageCalculator 直接用修正后的威力
3. **最终**: `× power_multiplier_buff`（独立乘法层）

---

## 3. 属性克制体系

### 3.1 18 系属性完整映射

**Source**: `src/types.py` (Type 枚举) + 克制表

当前已验证的克制表：
- 来源：游戏内克制图表 xlsx
- 修正：40 处与宝可梦默认数据差异
- 新增：Type.LIGHT（洛克王国独有）

**验证清单**：
- [ ] 18 系共 324 个克制关系（18×18）
- [ ] 每个关系确认倍率（通常 0.5, 1.0, 2.0）
- [ ] 特殊情况（双属性处理）？

### 3.2 双属性防御处理

**当前实现**：
```python
eff = get_type_effectiveness(skill_type, defender.pokemon_type)
```

**关键问题**：
- 是否只用主属性？
- 如何处理双属性？（分别克制再相乘？）
- 游戏内是否存在双属性精灵？

---

## 4. 天气系统

### 4.1 三种天气及其效果

**Source**: `src/battle.py:209-212`

| 天气 | 技能威力修正 | 其他效果 |
|-----|-----------|--------|
| `rain` | 水系 +50% | 无 |
| `sandstorm` | 无 | 回合伤害（详见 turn_end） |
| `snow` | 无 | 回合伤害（详见 turn_end） |

**验证清单**：
- [ ] 雨天是否仅对水系有 1.5x？
- [ ] 沙暴/雪天的回合伤害公式正确吗？
- [ ] 天气持续回合数计算正确吗？

### 4.2 天气应用流程

1. `execute_full_turn()` 调用 `execute_skill()`
2. `execute_skill()` 传入当前天气给 DamageCalculator
3. DamageCalculator 查表获得天气倍率
4. 伤害 × 天气倍率

**潜在问题**：
- 天气是否在该回合中途变化？
- 是否需要检查技能执行前/后天气状态？

---

## 5. 减伤系统

### 5.1 DAMAGE_REDUCTION 原语

**Source**: `src/effect_engine.py:514`

```python
def _h_damage_reduction(tag: EffectTag, ctx: Ctx) -> None:
    reduction_pct = tag.params.get("pct", 0)
    ctx.result["_damage_reduction"] = ctx.result.get("_damage_reduction", 0) + reduction_pct
```

**计算位置**：
- 在 handler 中累加 `_damage_reduction`
- 在伤害最终计算时应用：`最终伤害 = 伤害 × (1 - 总减伤)`

### 5.2 应对伤害的减伤

**问题**：
- [ ] 应对时的减伤是否包含在减伤系统中？
- [ ] 反弹伤害是否受减伤影响？
- [ ] 多层减伤（buff + 防御技能）如何叠加？

---

## 6. 已知系数及验证状态

### 6.1 固定系数

| 系数 | 值 | 含义 | 验证状态 |
|-----|---|------|--------|
| 基础伤害系数 | 0.9 | (攻/防) × 威力 × 0.9 | ⚠️ 需确认 |
| 本系加成 | 1.5x | 同系技能威力加成 | ✅ |
| 雨天水系 | 1.5x | 雨天水系技能威力 | ⚠️ 需确认 |
| 克制加成 | 2.0x | 被克制技能威力加成 | ⚠️ 需确认 |
| 被克制 | 0.5x | 克制对方技能威力 | ⚠️ 需确认 |

### 6.2 需要验证的比例

- [ ] **0.9 系数** — 是固定的吗？能修改吗？
- [ ] **连击计数** — 是否 > 1 时全部伤害累加？
- [ ] **威力百分比** — +20% 是 1.2 倍还是什么？

---

## 7. 伤害公式精度校准计划

### 7.1 基准测试集构建

**目标**: 20-50 组游戏内真实伤害数据

**选择标准**：
- 不同属性组合（克制、被克制、无关系）
- 不同能力等级（无修改、有升降）
- 不同天气状态
- 不同连击数（1x vs 多次）

**每组数据包含**：
```
攻击方精灵:
  - 名称
  - 属性
  - 攻击力
  - 能力等级修改(atk_up, def_down等)
  - 任何威力 buff

技能:
  - 名称
  - 威力
  - 属性
  - 类型(物理/魔法)
  - 连击数

防御方精灵:
  - 名称
  - 属性
  - 防御力
  - 能力等级修改

战斗环境:
  - 天气
  - 其他状态

游戏内实测伤害: [记录值]
模拟器计算伤害: [计算值]
误差: [%]
```

### 7.2 验证流程

1. **构建 20 个基础测试用例**
   - 最基础的伤害（无 buff、无能力修改）
   - 验证基础公式 (攻/防) × 威力 × 0.9 是否正确

2. **逐层添加复杂性**
   - 能力等级修改 → 验证等级计算
   - 属性克制 → 验证克制倍率
   - 天气状态 → 验证天气倍率
   - 连击 → 验证连击累加

3. **边界情况**
   - 极低攻击 (1 atk vs 高防) → 伤害最少 1
   - 极高威力 + buff → 浮点数溢出？
   - 多层减伤 → 是否正确求和

### 7.3 误差接受标准

| 误差范围 | 处理方案 |
|--------|--------|
| ≤ 1% | 浮点精度，接受 |
| 1-5% | 可能是系数精度，调查 |
| > 5% | 公式有根本错误，停下调查 |

---

## 8. 关键疑点及查证清单

### Q1: 威力加成与倍数的详细流程

- [ ] `skill_power_bonus` 何时应用？（PRE_USE 还是 ON_USE？）
- [ ] `skill_power_pct_mod` 是否在加成之前或之后应用？
- [ ] `power_multiplier_buff` 何时最终应用？（伤害计算后）

### Q2: 应对系统中的伤害计算

- [ ] 应对技能的伤害是否用同一套公式？
- [ ] 应对伤害 × 2 or × 3 的倍数在何处应用？
- [ ] 应对时的威力修正优先级？

### Q3: 多目标技能的伤害

- [ ] 多目标技能是否对每个目标分别计算伤害？
- [ ] 是否有群体伤害惩罚（群体技能伤害 -25%）？

### Q4: 状态效果中的伤害（如灼烧）

- [ ] 状态伤害是否也用此公式？
- [ ] 能力等级是否影响状态伤害？

---

## 9. 下一步行动

### 立即（本会话，规划）

- [ ] 确认 0.9 系数的含义
- [ ] 列举 20 个基础测试用例模板
- [ ] 制定数据采集策略

### 下个会话（执行）

- [ ] 采集 20+ 游戏内实测伤害数据
- [ ] 在模拟器中逐一计算并对比
- [ ] 根据偏差调整公式系数

### 长期

- [ ] 所有 500+ 技能的伤害验证
- [ ] 特性对伤害的影响验证
- [ ] 应对系统的伤害倍数验证

---

## 附录：伤害计算源代码引用

### A.1 能力等级字段

**File**: `src/models.py:Pokemon`

```python
atk_up: float = 0
atk_down: float = 0
def_up: float = 0
def_down: float = 0
spatk_up: float = 0
spatk_down: float = 0
spdef_up: float = 0
spdef_down: float = 0
```

**清零时机**: `on_switch_out()` 方法中清零所有修改

### A.2 天气状态存储

**File**: `src/models.py:BattleState`

```python
weather: str = ""
weather_turns: int = 0
```

### A.3 属性克制表

**File**: `src/types.py`

完整的 18 × 18 克制矩阵已在代码中实现。


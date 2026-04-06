# 特性(Ability)优先级矩阵

**Date**: 2026-04-07  
**Status**: 规划阶段  
**Priority**: P1（高优先）

---

## 1. 当前配置状态

**已配置**: 31 个特性  
**需补全**: 170+ 个特性（游戏中存在）

### 1.1 已配置的 31 个特性

| # | 特性名 | 触发时机 | 功能 | 复杂度 |
|---|-------|--------|------|-------|
| 1 | 溶解扩散 | ON_BATTLE_START, ON_USE_SKILL | 中毒计数 + 水系技能附加中毒 | 中 |
| 2 | 下黑手 | ON_ENEMY_SWITCH | 敌方换人附加中毒 | 低 |
| 3 | 蚀刻 | ON_TURN_END | 中毒转印记 | 中 |
| 4 | 扩散侵蚀 | ON_USE_SKILL | 印记数换中毒 | 中 |
| 5 | 虚假宝箱 | ON_FAINT | 力竭时敌方减益 | 低 |
| 6 | 身经百练 | ON_ALLY_COUNTER, ON_ENTER | 应对计数 + 动态威力 | 高 |
| 7 | 专注力 | ON_BATTLE_START, ON_ENTER | 物攻+100% | 低 |
| 8 | 乘风连击 | ON_USE_SKILL | 翼系技能+连击数 | 低 |
| 9 | 养分内循环 | ON_TURN_END | 回复6能量 | 低 |
| 10 | 养分重吸收 | ON_TURN_END | 回复3能量 | 低 |
| 11 | 快充 | ON_LEAVE | 离场回复10能量 | 低 |
| 12 | 小偷小摸 | ON_ENEMY_SWITCH | 敌方换人失去2能量 | 低 |
| 13 | 做噩梦 | ON_ENEMY_SWITCH | 敌方换人失去3能量 | 低 |
| 14 | 不移 | ON_BATTLE_START, ON_ENTER | 纯攻击技能+30% | 中 |
| 15 | 勇敢 | ON_BATTLE_START, ON_ENTER | 高耗技能+40% | 中 |
| 16 | 挺起胸脯 | ON_BATTLE_START, ON_ENTER | 物防+100% | 低 |
| 17 | 快锤 | ON_BATTLE_START, ON_ENTER | 武系技能+20% | 中 |
| 18 | 暴食 | ON_USE_SKILL | 食物系技能特殊处理 | 中 |
| 19 | 冰钻 | ON_USE_SKILL | 冰系技能冻伤概率 | 低 |
| 20 | 冻土 | ON_USE_SKILL | 冰系技能冻伤概率 | 低 |
| 21 | 煤渣草 | ON_TURN_END | 灼烧不衰减 | 低 |
| 22 | 飓风 | ON_TURN_END | 风系技能特殊处理 | 中 |
| 23 | 洁癖(翠顶夫人) | ON_LEAVE | 离场传递修改 | 高 |
| 24 | 绝对秩序 | ON_TURN_START | 阻止换人? | 高 |
| 25 | 向心力 | PASSIVE | 位置相关增益 | 高 |
| 26 | 预警 | PASSIVE | 有威胁时速度加成 | 高 |
| 27 | 哨兵 | PASSIVE | 类似预警 | 高 |
| 28 | 保卫 | ON_COUNTER_SUCCESS | 应对计数→变身 | 高 |
| 29 | 不朽 | ON_FAINT | 力竭后延迟复活 | 高 |
| 30 | 贪婪 | ON_ENEMY_SWITCH | 复制敌方状态 | 高 |
| 31 | 对流 | PASSIVE | 能耗增减反转 | 中 |

---

## 2. 主流特性优先级分类

根据"竞技场常见度"和"实现复杂度"分级：

### 🔴 P0-高频-低复杂 (立即实现)

这些特性在主流阵容中高频出现，实现难度低，应立即补全。

| 特性 | 出现率 | 主要使用精灵 | 实现要点 |
|-----|-------|----------|--------|
| **光合作用** | 90% | 草系全阵 | ON_TURN_END 回复15HP |
| **威胁** | 85% | 格斗系主控 | ON_TURN_START 减敌速 |
| **干燥皮肤** | 80% | 毒系防守 | ON_TURN_END 受伤回复 |
| **再生** | 75% | 各系防守 | ON_LEAVE 回复33% HP |
| **隔离** | 70% | 特殊防守 | PASSIVE 降敌特防 |
| **紧张感** | 65% | 速度队 | PASSIVE 降敌速 |

### 🟠 P0-中频-中复杂 (需要特殊机制)

这些需要新的 EffectTag 类型或复杂的条件判断。

| 特性 | 出现率 | 主要使用精灵 | 需要的机制 |
|-----|-------|----------|----------|
| **极限盾** | 60% | 防守型 | ON_TAKE_HIT 减伤 |
| **威吓** | 55% | 攻击型 | ON_ENTER 降敌攻 |
| **再生力** | 50% | 坦克型 | ON_TAKE_HIT 按伤害回复 |
| **复眼** | 45% | 命中率队 | 技能命中率修正 |
| **蓄电池** | 40% | 电系队 | ON_TAKE_HIT 吸收电伤 |

### 🟡 P1-低频-低复杂 (补全基础库)

这些出现率不高，但实现简单，可逐个补全。

| 特性 | 功能 | 实现难度 |
|-----|------|--------|
| **圣盾** | 减伤25% | 低 |
| **坚硬** | 防住一击 | 低 |
| **同步** | 复制敌方状态 | 中 |
| **静电** | 麻痹接触攻击者 | 低 |
| **中毒孢子** | 中毒概率 | 低 |

### 🔵 P2-特殊-高复杂 (后续)

这些涉及复杂的游戏机制或尚未开发的系统。

| 特性 | 机制 | 复杂度 |
|-----|------|-------|
| **绝对秩序** | 阻止换人 | 高 |
| **不朽** | 延迟复活 | 高 |
| **保卫** | 应对变身 | 高 |
| **贪婪** | 状态复制 | 高 |
| **向心力** | 位置相关 | 高 |

---

## 3. 特性实现模板

每个特性的实现标准流程：

### 步骤 1: 配置 (effect_data.py)

```python
"特性名": [
    AE(Timing.xxx, [T(E.EffectType, params...)]),
    # 可能有多个 Timing
],
```

**涉及的 Timing 选项**：
- ON_ENTER — 入场时
- ON_LEAVE — 离场时  
- ON_FAINT — 自身力竭
- ON_TAKE_HIT — 受到攻击
- ON_USE_SKILL — 使用技能后
- ON_TURN_START — 回合开始
- ON_TURN_END — 回合结束
- ON_ENEMY_SWITCH — 敌方换人
- PASSIVE — 常驻被动
- ON_COUNTER_SUCCESS — 应对成功

### 步骤 2: Handler (effect_engine.py)

若需新的 EffectTag 类型，添加 handler 函数：

```python
def _h_xxx(tag: EffectTag, ctx: Ctx) -> None:
    """特性逻辑实现"""
    param1 = tag.params.get("param1", default_val)
    # 修改 ctx.user / ctx.target / ctx.state
    # 结果写入 ctx.result["key"] = value
```

**Context 对象 (Ctx)** 包含：
- `state: BattleState` — 完整战斗状态
- `user: Pokemon` — 特性拥有者
- `target: Pokemon` — 目标（敌方或队友）
- `team: str` — "a" 或 "b"
- `result: dict` — 效果结果记录

### 步骤 3: 测试 (tests/)

创建对应的测试用例：

```python
def test_特性名():
    state = setup_test_battle(...)
    # 触发特性
    execute_ability(state, user, target, Timing.xxx, ability_effects, team)
    # 验证结果
    assert condition_met(state)
```

---

## 4. EffectTag 类型补充需求

要实现上述 TOP 20 特性，需要添加以下 EffectTag 类型（如尚未实现）：

| EffectTag 类型 | 含义 | 参数 | 优先级 |
|---|---|---|---|
| HEAL_HP_ON_TAKE_HIT | 受伤回复 | `pct`: 回复百分比 | P0 |
| REDUCE_SPEED | 降低速度 | `amount`, `pct` | P0 |
| REDUCE_ATTACK | 降低攻击 | `amount`, `pct` | P0 |
| IMMUNITY_STATUS | 状态免疫 | `status`: 状态类型 | P0 |
| BYPASS_ABILITY | 忽视特性 | `target_ability` | P1 |
| DELAYED_REVIVE_MARK | 延迟复活 | `turns`, `hp_pct` | P2 |
| COPY_STATE_ON_SWITCH | 换人时复制状态 | 无 | P2 |
| PREVENT_SWITCH | 防止换人 | 无 | P2 |

---

## 5. 当前缺口分析

### 5.1 已实现的 EffectTag 类型

当前 `effect_models.py` 中的 E 枚举定义了 100+ 种效果类型，包括：
- 伤害/回复: DAMAGE, HEAL_HP, HEAL_ENERGY, STEAL_ENERGY, LIFE_DRAIN
- 状态: POISON, BURN, FREEZE, LEECH, METEOR
- 印记: POISON_MARK, MOISTURE_MARK
- Buff/Debuff: SELF_BUFF, SELF_DEBUFF, ENEMY_DEBUFF
- 机制: FORCE_SWITCH, INTERRUPT, AGILITY, COUNTER_ATTACK/STATUS/DEFENSE
- 修正: POWER_DYNAMIC, PERMANENT_MOD, SKILL_MOD, NEXT_ATTACK_MOD
- 驱散: CLEANSE, DISPEL_MARKS, CONVERT_BUFF_TO_POISON
- 天气: WEATHER

### 5.2 需要新增的类型

- [ ] HEAL_HP_PERCENT_ON_TURN_END — 回合结束回复百分比HP
- [ ] DAMAGE_REDUCTION_PASSIVE — 常驻减伤 buff
- [ ] SPEED_REDUCTION_AURA — 光环式速度降低
- [ ] STATUS_IMMUNITY — 状态免疫

---

## 6. 实现优先级排序

### TOP 10 优先实现

按"出现率 × 复杂度权重"排序：

1. **光合作用** — 回合结束回复15HP (ON_TURN_END)
2. **威胁** — 回合开始敌速-10% (ON_TURN_START)
3. **干燥皮肤** — 受伤回复(ON_TAKE_HIT)
4. **再生** — 离场回复33% (ON_LEAVE)
5. **隔离** — 敌特防-10% (PASSIVE)
6. **紧张感** — 敌速-10% (PASSIVE)
7. **极限盾** — 受伤减伤25% (ON_TAKE_HIT)
8. **威吓** — 入场敌攻-30% (ON_ENTER)
9. **再生力** — 受伤回复50% (ON_TAKE_HIT)
10. **复眼** — 命中率+10%(PASSIVE)

---

## 7. 下一步行动

### 本会话（规划）

- [x] 列出已配置的 31 个特性
- [ ] 从游戏 Wiki 获取完整 170+ 特性列表
- [x] 标记 TOP 20 高频特性
- [x] 识别所需新增 EffectTag 类型

### 下个会话（执行）

- [ ] 实现 TOP 10 特性（步骤 1-3）
- [ ] 补充所需的 EffectTag 类型
- [ ] 新增 ON_TAKE_HIT timing 支持
- [ ] 构建特性测试套件

### 长期

- [ ] 补全 TOP 30 特性
- [ ] 补全 TOP 50 特性
- [ ] 所有 170+ 特性完整覆盖


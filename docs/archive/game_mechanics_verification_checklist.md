# 游戏机制验证清单

**Date**: 2026-04-07  
**Status**: 规划阶段  
**Priority**: P0（关键路径）

---

## 1. 换宠系统 (Switching Mechanism)

### 1.1 状态清除

**测试**: 精灵 A 有 Buff/Debuff → 换人到精灵 B → 验证状态是否清除

| 效果类型 | 是否清除 | 代码行 | 验证状态 |
|--------|--------|-------|--------|
| Buff (atk_up etc) | ✅ YES | battle.py:on_switch_out() | ✓ 已实现 |
| Debuff (atk_down etc) | ✅ YES | battle.py:on_switch_out() | ✓ 已实现 |
| 中毒/灼烧等状态 | ✅ YES | battle.py:on_switch_out() | ✓ 已实现 |
| 印记 (poison_mark) | ❌ NO | BattleState.marks_a/b | ✓ 正确行为 |
| 能量 | ⚠️ 保留 | battle.py:auto_switch() | ✓ 需确认 |

**验证方法**:
```python
def test_switch_clears_debuffs():
    state = setup_battle(...)
    state.team_a[0].atk_up = 2.0  # 加攻
    auto_switch(state)  # 换人
    assert state.team_a[0].atk_up == 0, "Buff should be cleared"
```

### 1.2 特性触发

**测试**: 换人时是否正确触发 ON_ENTER 和 ON_LEAVE 特性

| Timing | 触发条件 | 当前实现 | 验证状态 |
|--------|--------|--------|--------|
| ON_LEAVE | 精灵离场时 | battle.py:auto_switch() | ⚠️ 需检查 |
| ON_ENTER | 精灵入场时 | battle.py:auto_switch() | ⚠️ 需检查 |
| ON_BATTLE_START | 战斗开始 | battle.py:_trigger_battle_start_effects() | ✓ 已实现 |

**验证方法**:
```python
def test_on_enter_trigger():
    state = setup_battle(...)
    # 精灵具有 ON_ENTER 特性，应该在切换时触发
    auto_switch(state)
    # 验证特性效果已应用
```

---

## 2. 应对系统 (Counter Mechanism)

### 2.1 分类识别

**测试**: 应对系统是否正确识别敌方技能类型

| 技能类型 | 应对容器 | 匹配逻辑 | 验证状态 |
|--------|--------|--------|--------|
| 物理攻击技能 | COUNTER_ATTACK | category="attack" | ✓ 已实现 |
| 状态技能 | COUNTER_STATUS | category="status" | ✓ 已实现 |
| 防御技能 | COUNTER_DEFENSE | category="defense" | ✓ 已实现 |

**验证方法**:
```python
def test_counter_classification():
    # 敌方使用物理攻击 → 应该触发 COUNTER_ATTACK
    # 敌方使用状态技能 → 应该触发 COUNTER_STATUS
    # 验证容器效果被正确应用
```

### 2.2 优先级和顺序

**问题**: 同一回合多个应对机制触发时的顺序

**测试场景**:
- 精灵A同时有：反弹伤害 + 防御减伤 + 反击
- 敌方B进行攻击
- 验证应用顺序：
  1. 是否先计算反弹？
  2. 然后减伤？
  3. 最后反击？

**验证方法**:
```python
def test_counter_order():
    state = setup_battle(
        attacker_b_has=[MIRROR_DAMAGE, DAMAGE_REDUCTION, COUNTER_ATTACK],
        defender_a=Pokemon(...)
    )
    # 执行 B 的攻击
    # 验证伤害计算顺序
    expected_damage = calc_expected_with_order()
    assert actual_damage == expected_damage
```

### 2.3 多层应对链

**问题**: 应对被再次应对时是否处理正确

**测试**: A 使用技能 → B 应对 → A 再应对 B 的应对技能

---

## 3. 先手系统 (Priority/Speed System)

### 3.1 先手等级优先级

**公式**: 先手等级 > 速度 > 随机

**测试**:

| 条件 | 预期结果 | 验证状态 |
|-----|--------|--------|
| A 先手+2 vs B 先手0 | A 先出手（无论速度）| ⚠️ 需测试 |
| A 先手0 速度100 vs B 先手0 速度50 | A 先出手 | ⚠️ 需测试 |
| 都相同 | 50%随机 | ⚠️ 需测试 |

**验证方法**:
```python
def test_priority_override():
    # 低速+高先手 应该胜过 高速+低先手
    result = compare_action_order(state, 
        action_a=(skill_with_priority_2,),
        action_b=(skill_with_priority_0,))
    assert result == -1  # A 先手
```

### 3.2 风起印记 (First-strike Mark)

**声称功能**: 先手时威力 +N%

**测试**:
- [ ] 先手攻击应该获得威力加成
- [ ] 非先手攻击不应该获得加成
- [ ] 加成百分比是否正确

---

## 4. 能量系统 (Energy/Agility)

### 4.1 迅捷重放 (Agility Replay)

**测试**: 使用迅捷技能后是否在回合开始时自动重放

| 条件 | 预期行为 | 验证状态 |
|-----|--------|--------|
| 上回合用迅捷 | 本回合回合开始前再用一次 | ⚠️ 需测试 |
| 多个迅捷 | 是否依次重放？还是随机一个？| ❌ 不清楚 |
| 迅捷后能量不足 | 是否聚能再用？| ❌ 不清楚 |

**验证方法**:
```python
def test_agility_replay():
    state = setup_battle(...)
    # 使用迅捷技能
    result = execute_skill(state, agility_skill)
    assert result["agility_marked"] == True
    
    # 进入下一回合
    # 验证是否自动重放迅捷
    assert agility_replayed(state)
```

### 4.2 能量动态减少

**测试**: 按条件减少能量消耗

| 技能特性 | 能量消耗修改 | 验证状态 |
|--------|-----------|--------|
| 每层中毒 -1 | poison_stacks=2 → cost-2 | ⚠️ 需测试 |
| 湿润印记 -N | marks["moisture_mark"]=3 → cost-3 | ✓ 已实现 |
| 对流特性反转 | 原减少 → 增加 | ⚠️ 需测试 |

---

## 5. 天气系统 (Weather System)

### 5.1 三种天气

**当前实现**：沙暴、雪天、雨天（晴天已删除）

| 天气 | 技能威力修正 | 回合伤害 | 持续机制 | 验证状态 |
|-----|-----------|--------|--------|--------|
| 雨天 | 水系 +50% | 无 | turns 递减 | ⚠️ 需测试 |
| 沙暴 | 无 | 每回合伤害 | turns 递减 | ⚠️ 需测试 |
| 雪天 | 无 | 每回合伤害 | turns 递减 | ⚠️ 需测试 |

### 5.2 天气转换

**测试**: 旧天气消失时是否正确触发新天气

| 场景 | 预期行为 | 验证状态 |
|-----|--------|--------|
| 天气turns=1 → 下一回合 | 天气消失 | ⚠️ 需测试 |
| 新天气覆盖旧天气 | 计数重置 | ⚠️ 需测试 |

---

## 6. 回合流程 (Turn Flow)

### 6.1 行动顺序

**预期顺序**:
1. 判定先手（先手等级 > 速度）
2. A 方执行技能/换人
3. B 方执行技能/换人
4. 结算伤害/状态
5. 回合结束特性触发
6. 状态伤害（灼烧、中毒等）

**测试**:
```python
def test_turn_order():
    # 日志应该按此顺序输出
    expected_order = [
        "先手判定",
        "A队行动",
        "B队行动", 
        "伤害结算",
        "回合结束特性",
        "状态伤害",
    ]
    actual_order = extract_log_order(state)
    assert actual_order == expected_order
```

### 6.2 聚能机制

**测试**: 无有效技能时是否执行聚能 (-1 行动)

| 条件 | 预期行为 | 验证状态 |
|-----|--------|--------|
| 所有技能CD中 | 自动聚能 | ✓ 已实现 |
| 能量不足 + CD中 | 自动聚能 | ✓ 已实现 |
| 聚能后恢复5能量 | 能量 += 5 | ✓ 需检查数值 |

---

## 7. 状态效果系统 (Status Effects)

### 7.1 五种主要状态

| 状态 | 每回合效果 | 转换规则 | 验证状态 |
|-----|---------|--------|--------|
| 中毒 | 伤害 | 可转印记 | ⚠️ 需测试 |
| 灼烧 | 伤害+攻击半减 | 灼烧不衰减特性 | ⚠️ 需测试 |
| 冻伤 | 冻结不动 | 超级威力解冻 | ❌ 未实现 |
| 寄生 | 吸收伤害 | 参数需确认 | ❌ 不清楚 |
| 星陨 | 伤害+防御降低 | 参数需确认 | ⚠️ 需测试 |

### 7.2 状态衰减

**测试**: 每回合是否衰减 1 层

| 状态 | 自然衰减 | 清除技能 | 特性清除 | 验证状态 |
|-----|--------|--------|--------|--------|
| 中毒 | ✅ -1 /turn | 毒液清除等 | 清除技能 | ⚠️ 需测试 |
| 灼烧 | ⚠️ 可能不衰减 | - | 特性控制 | ⚠️ 需测试 |

---

## 8. 印记系统 (Mark/Seal System)

### 8.1 印记持久性

**测试**: 印记在换宠时是否保留

| 场景 | 预期行为 | 验证状态 |
|-----|--------|--------|
| 敌方A换B | 中毒印记保留 | ✓ 已实现 |
| 敌方全灭后 | 印记是否清除？ | ❌ 不清楚 |

### 8.2 印记触发

**测试**: 印记是否在正确时机应用效果

| 印记类型 | 应用时机 | 验证状态 |
|--------|--------|--------|
| 湿润印记 | 回合开始时减能耗 | ✓ 已实现 |
| 中毒印记 | 搭配特性效果 | ⚠️ 需测试 |

---

## 9. 验收清单

### 最高优先 (P0)

- [ ] 换宠清除状态但保留印记
- [ ] 应对系统正确分类三类技能
- [ ] 先手等级 > 速度判定
- [ ] 迅捷重放正常工作
- [ ] 天气威力修正应用正确
- [ ] 回合流程顺序正确

### 次优先 (P1)

- [ ] 多层应对链正确处理
- [ ] 能量动态减少各种条件
- [ ] 状态衰减正常
- [ ] 印记驱散条件判定

### 后续 (P2)

- [ ] 冻伤/寄生状态完整实现
- [ ] 星陨完整实现

---

## 10. 测试执行计划

### 下个会话

1. **准备**: 为每个清单项编写测试用例
2. **执行**: `pytest tests/test_mechanics_*.py -v`
3. **记录**: 通过/失败情况
4. **修复**: 根据失败情况修正代码

### 预期输出

- ✅ 通过 13+ 个测试（P0 项目）
- ⚠️ 标记 5+ 个需要修正的项
- ❌ 识别 3+ 个未实现的机制


# 洛克王国 AI 项目 — 快速参考卡

## 📊 一句话总结

**架构优秀的战斗模拟器**（8K 行核心代码，95%+ 技能覆盖），细节需完善（文档分散、数据未校准）。**总体评分 4/5**。

---

## 🎯 项目当前阶段

```
阶段一: 战斗数据高度复刻      [████████░░] 80% ← 当前
  ✅ 伤害公式、特性、天气、行动顺序、状态系统
  ❌ 待验证：真实游戏数据对照（P0 缺口）

阶段二: AI 自我成长            [░░░░░░░░░░] 0%
阶段三: 游戏实时指导            [░░░░░░░░░░] 0%
```

---

## 🏗️ 系统架构一览

```
数据层           配置层              执行层              应用层
────────────────────────────────────────────────────────────
models.py   →  effect_data.py   →  effect_engine.py   →  battle.py
  Pokemon       技能配置              效果执行              战斗流程
  Skill         特性配置              75+ handlers         队伍构建
  Type          应对配置              状态管理             行动决策
  EffectTag     
                                      skill_db.py         mcts.py
                                      pokemon_db.py       server.py
                                                          main.py
```

**核心特点**: 
- ✅ **数据驱动**: 特性/技能完全由配置表驱动，battle.py 零硬编码
- ✅ **模块解耦**: effect_engine 通过注册表分派，易扩展
- ⚠️ **大文件**: effect_engine.py (2016 行) 可分模块

---

## 📁 文件速查表

### 需要改动代码？→ src/

| 文件 | 何时改？ |
|------|---------|
| battle.py | 战斗流程、行动执行 |
| effect_engine.py | 效果逻辑（75+ handlers） |
| effect_data.py | **新增技能/特性** ← 通常在这里 |
| mcts.py | AI 算法 |
| server.py | Web 后端 |

### 需要检查数据？→ data/

| 文件 | 内容 | 可靠性 |
|------|------|--------|
| nrc.db | 461 精灵 × 495 技能 | ✅ 确认 |
| skills_raw.json | 技能详情 | ⚠️ 需验证 |
| pokemon_stats.xlsx | 精灵六维 | ⚠️ 需验证 |

### 需要添加测试？→ tests/

- test_battle_fixes.py — 战斗系统
- test_ability_clarifications.py — 特性系统
- test_skill_runtime_mappings.py — 技能系统

### 需要启动？

```bash
# Web 界面
python3 run_web.py               # 打开 http://localhost:8765

# CLI 批量模拟
python3 start.py

# 数据初始化（仅首次）
python3 scripts/init_db.py
```

---

## 📈 数据库快查

### 精灵表结构
```sql
SELECT * FROM pokemon LIMIT 1;
-- Columns: id, name, type1, type2, hp, atk, def, spatk, spdef, speed, ability
```

### 技能表结构
```sql
SELECT * FROM skill LIMIT 1;
-- Columns: id, name, type, category, power, accuracy, pp, effect
```

### 学习关系 (21,331 条)
```sql
SELECT * FROM pokemon_skill WHERE pokemon_id = 1;
-- 查询某精灵学会的所有技能
```

### 快速查询示例
```bash
# 登录数据库
sqlite3 data/nrc.db

# 统计精灵数
sqlite> SELECT COUNT(*) FROM pokemon;  -- 461

# 统计技能数
sqlite> SELECT COUNT(*) FROM skill;     -- 495

# 查某精灵
sqlite> SELECT * FROM pokemon WHERE name = '毒液泛泛';
```

---

## ⚙️ 添加新技能（标准流程）

### 步骤 1: 在 effect_data.py 配置

```python
# effect_data.py - SKILL_EFFECTS 字典中添加

"技能名": [
    SE(SkillTiming.ON_USE, [
        T(E.DAMAGE),                          # 造成伤害
        T(E.SELF_BUFF, atk=0.2),             # 攻击+20%
    ]),
],
```

### 步骤 2: 添加测试

```python
# tests/test_new_skill.py
def test_新技能():
    # 使用 Battle 类进行测试
    battle = ...
    assert battle.player_team[0].current_hp < 原HP
```

### 步骤 3: 验证

```bash
pytest tests/ -v
```

**所需时间**: 5 分钟（简单技能）

---

## ⭐ 添加新特性（标准流程）

### 步骤 1: 在 effect_data.py 配置

```python
# effect_data.py - ABILITY_DATA 字典中添加

"特性名": [
    AE(Timing.ON_ENTER, [T(E.WEATHER, weather='rain')]),  # 入场下雨
    AE(Timing.ON_TURN_END, [T(E.HEAL_HP, pct=0.125)]),   # 每回合回复
],
```

### 步骤 2: 在 effect_engine.py 添加 handler（如需自定义）

```python
# effect_engine.py - _HANDLERS 字典中添加

def _h_特性名(tag, ctx):
    """特性逻辑"""
    ctx.user.apply_buff(...)  # 修改战场状态
```

### 步骤 3: 测试

```bash
pytest tests/test_ability_clarifications.py -v
```

**所需时间**: 10 分钟（含自定义逻辑）

---

## 🔍 快速诊断命令

```bash
# 检查测试是否全通过
pytest tests/ -v --tb=short

# 运行特定测试文件
pytest tests/test_battle_fixes.py -v

# 统计代码行数
wc -l src/*.py tests/*.py

# 检查效果覆盖
python3 scripts/audit_effect_coverage.py

# 数据库完整性检查
sqlite3 data/nrc.db "SELECT COUNT(*) FROM pokemon;"
```

---

## ❌ 常见问题速查

### Q: 新增技能但不生效？
A: 检查 SKILL_EFFECTS 配置是否在 effect_data.py 中，运行 `pytest` 验证

### Q: 特性没有触发？
A: 检查 Timing 是否正确（ON_ENTER/ON_TURN_END/ON_USE_SKILL 等）

### Q: 伤害数值不对？
A: 检查 damage_formula_precision_analysis.md，可能需要系数校准

### Q: Web UI 无法连接？
A: 检查 server.py 中的端口配置，默认 8765

### Q: 数据库报错？
A: 运行 `python3 scripts/init_db.py` 重新初始化

---

## 🎓 学习资源

### 新手入门
1. 阅读 README.md（快速开始）
2. 阅读 SKILLS_ABILITIES_CONFIG_GUIDE.md（配置指南）
3. 运行 Web UI（`python3 run_web.py`）

### 深入理解
1. docs/game_mechanics_verification_checklist.md — 游戏机制
2. docs/ability_priority_matrix.md — 特性优先级
3. docs/damage_formula_precision_analysis.md — 伤害公式

### 开发参考
1. src/effect_models.py — 效果枚举完整列表
2. tests/test_skill_runtime_mappings.py — 技能示例
3. SKILLS_ABILITIES_CONFIG_GUIDE.md — 配置语法

---

## 📌 关键数字

| 指标 | 值 |
|------|-----|
| 代码行数 | 8,235 (src + tests) |
| 测试覆盖 | 2,493 行，10 文件，100% 通过 |
| 效果原语 | 85+ 种 E 枚举 |
| 效果 handler | 75+ 个 |
| 手工技能配置 | 35 个 |
| 自动技能配置 | 460 个 |
| **技能覆盖** | **495/495 (100%)** |
| 配置特性 | 17 个 |
| 总特性数 | 170+（需配置） |
| 精灵总数 | 461 |
| 学习关系 | 21,331 条 |

---

## 🚨 立即待办

- [ ] 更新 ROADMAP.md（最后更新 2026-04-05）
- [ ] 清理 nrc.db-wal (3.0 MB)
- [ ] 删除 .DS_Store (10 KB)
- [ ] 游戏实测验证（P0 缺口）
- [ ] 补全主流特性配置（P1）

---

## 📞 快速导航

| 需要... | 去... |
|--------|------|
| 快速开始 | README.md |
| 架构设计 | SKILLS_ABILITIES_CONFIG_GUIDE.md |
| 项目进度 | ROADMAP.md |
| 技能示例 | src/effect_data.py 或 tests/ |
| 特性示例 | src/effect_data.py ABILITY_DATA |
| 战斗演示 | python3 run_web.py |
| 单位测试 | pytest tests/ -v |

---

**最后更新**: 2026-04-07  
**文档版本**: v1.0  
**项目评分**: ⭐⭐⭐⭐ (4/5)

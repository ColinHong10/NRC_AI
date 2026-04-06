# 项目文件完整清单

**生成时间**: 2026-04-07  
**总项目大小**: 131 MB (含 .git)  
**清单级别**: 详细库存

---

## 📂 核心代码 (src/) — 356 KB

### 战斗系统

| 文件 | 大小 | 行数 | 功能 | 关键类/函数 |
|------|------|------|------|-----------|
| **battle.py** | 52 KB | 1,320 | 战斗流程 + 队伍构建 | `Battle`, `TeamBuilder`, `execute_full_turn()` |
| **models.py** | 19 KB | 461 | 数据模型定义 | `Pokemon`, `Skill`, `BattleState`, `Type` |
| **effect_models.py** | 15 KB | 290 | 效果原语类型 | `E` (枚举 85+ 种), `EffectTag`, `Timing` |

### 效果执行

| 文件 | 大小 | 行数 | 功能 | 关键类/函数 |
|------|------|------|------|-----------|
| **effect_engine.py** | 78 KB | 2,016 | 效果执行引擎 | `EffectExecutor`, `_HANDLERS` (75+ handlers) |
| **effect_data.py** | 23 KB | 648 | 技能+特性配置 | `SKILL_EFFECTS`, `ABILITY_DATA`, 工厂函数 `T()`, `SE()` |
| **skill_effects_generated.py** | 39 KB | 793 | 自动生成技能 | `SKILL_EFFECTS_GENERATED` (460 技能) |

### 数据库

| 文件 | 大小 | 行数 | 功能 | 关键函数 |
|------|------|------|------|---------|
| **skill_db.py** | 5.2 KB | 163 | 技能数据库 | `load_skills()`, `get_skill()` |
| **pokemon_db.py** | 8.4 KB | 256 | 精灵数据库 + PvP 五维 | `load_pokemon_db()`, PvP 计算公式 |

### 主程序

| 文件 | 大小 | 行数 | 功能 | 关键函数 |
|------|------|------|------|---------|
| **main.py** | 23 KB | 571 | CLI 主程序 | 批量模拟、统计胜率 |
| **mcts.py** | 18 KB | 484 | MCTS AI + 经验学习 | `MCTS`, 对抗式搜索 |
| **server.py** | 49 KB | 1,232 | FastAPI WebSocket 后端 | FastAPI 应用、WebSocket 消息处理 |
| **__init__.py** | 33 B | 1 | 包初始化 | 空 |

---

## 🧪 测试 (tests/) — 104 KB

| 文件 | 大小 | 行数 | 测试范围 | 状态 |
|------|------|------|---------|------|
| test_skill_runtime_mappings.py | 24.5 KB | 622 | 技能效果运行时映射 | ✅ 通过 |
| test_battle_fixes.py | 23.9 KB | 556 | 战斗系统修复 | ✅ 通过 |
| test_ability_clarifications.py | 12.2 KB | 347 | 特性触发规则 | ✅ 通过 |
| test_turn_order_rules.py | 4.4 KB | 159 | 行动顺序系统 | ✅ 通过 |
| test_battle_triggers.py | 6.3 KB | 204 | 战斗事件触发 | ✅ 通过 |
| test_effect_generic_mechanics.py | 6.2 KB | 192 | 通用效果机制 | ✅ 通过 |
| test_generate_skill_effects_patterns.py | 8.0 KB | 188 | 技能生成模式 | ✅ 通过 |
| test_manual_high_value_skills.py | 3.5 KB | 127 | 高价值手工技能 | ✅ 通过 |
| test_server_skill_display.py | 1.7 KB | 56 | Web 前端集成 | ✅ 通过 |
| test_generated_skill_expansion.py | 1.4 KB | 42 | 生成技能扩展 | ✅ 通过 |

**总计**: 2,493 行测试代码 ✅ 全部通过

---

## 🛠️ 数据工具 (scripts/) — 88 KB

| 文件 | 大小 | 行数 | 功能 | 使用场景 |
|------|------|------|------|---------|
| **generate_skill_effects.py** | 45 KB | 1,261 | 技能效果自动转换器 | 从 DB description 批量生成 460 个技能配置 |
| **init_db.py** | 13 KB | 366 | 数据库初始化 | 从 .xlsx 文件导入精灵/技能数据到 nrc.db |
| **audit_effect_coverage.py** | 8.1 KB | 218 | 效果覆盖审计 | 统计未配置的技能数量 |
| **crawl_pokemon_skills.py** | 7.8 KB | 229 | 爬虫工具 | 抓取技能学习关系到 DB |
| **scrape_skills.py** | 9.8 KB | 143 | 技能页面爬虫 | 抓取技能详情 JSON |

**说明**: 这些都是一次性数据导入脚本，运行过后无需再用

---

## 📊 游戏数据 (data/) — 5.7 MB

### 核心数据库

| 文件 | 大小 | 类型 | 内容 | 优先级 | 说明 |
|------|------|------|------|--------|------|
| **nrc.db** | 2.0 MB | SQLite | 461 精灵 × 495 技能 × 21,331 学习关系 | 🔴 必需 | 主数据库，不可删除 |
| **nrc.db-wal** | 3.0 MB | 预写日志 | 数据库事务日志 | 🟡 临时 | ⚠️ 过大，需定期清理 |
| **nrc.db-shm** | 32 KB | 共享内存 | 并发控制临时数据 | 🟡 临时 | 可安全删除 |

### 原始数据文件

| 文件 | 大小 | 类型 | 内容 | 优先级 | 用途 |
|------|------|------|------|--------|------|
| **skills_raw.json** | 120 KB | JSON | 460 个技能详情 | 🟢 参考 | 技能数据源 |
| **skills.xlsx** | 36 KB | Excel | 技能参数表 | 🟢 参考 | 手工编辑参考 |
| **pokemon_stats.xlsx** | 64 KB | Excel | 精灵六维数据 | 🟢 参考 | 精灵数据源 |
| **skills_all.csv** | 44 KB | CSV | 技能列表 | 🟡 过时 | 导出列表，源在 DB |
| **洛克王国世界攻略_副本.xlsx** | 124 KB | Excel | 游戏攻略表 | 🟡 参考 | 外部攻略参考 |
| **crawl_progress.json** | 9.2 KB | JSON | 爬虫进度记录 | 🟡 过时 | 爬虫状态，已停用 |

### 原始爬虫数据

| 文件 | 大小 | 类型 | 内容 | 优先级 | 说明 |
|------|------|------|------|--------|------|
| **raw/skills_wiki.csv** | 211 KB | CSV | Wiki 爬虫原始数据 | 🟡 过时 | 爬虫备份，可归档 |

**DB 表结构**:
```
pokemon         461 行  精灵编号/名/属性/六维种族值/特性等
skill           495 行  技能编号/名/属性/分类/威力/命中/PP/描述
pokemon_skill  21,331 行  精灵 × 技能 学习关系
```

---

## 🌐 Web 前端 (web/) — 72 KB

| 文件 | 大小 | 功能 | 技术栈 |
|------|------|------|--------|
| **battle.html** | 40.9 KB | 实时战斗界面 | WebSocket + CSS Grid + 原生 JS |
| **team.html** | 26.1 KB | 队伍编辑器 | 精灵/技能/性格配置 UI |
| **index.html** | 247 B | 入口重定向 | 指向 /battle |

**评估**:
- ✅ 功能完整：战斗+队伍编辑都有
- ⚠️ 代码混合：HTML/CSS/JS 混在一个文件里，建议分离

---

## 📚 文档 (docs/ + 根目录) — ~50 KB

### 根目录

| 文件 | 大小 | 内容 | 状态 | 更新日期 |
|------|------|------|------|---------|
| **ROADMAP.md** | 7.9 KB | 项目路线图 + 进度 | ⚠️ 部分过时 | 2026-04-05 |
| **README.md** | 3.7 KB | 快速开始指南 | ✅ 完整 | 当前 |
| **SKILLS_ABILITIES_CONFIG_GUIDE.md** | 22 KB | 技能+特性配置指南 | ✅ 完整 | 当前 |

### docs/ 目录

| 文件 | 大小 | 内容 | 状态 | 更新日期 |
|------|------|------|------|---------|
| **next_session_executable_tasks.md** | 10.8 KB | 下次开工任务清单 | 🟡 待执行 | 2026-04-07 |
| **game_mechanics_verification_checklist.md** | 9.1 KB | 游戏机制核对清单 | ✅ 完整 | 2026-04-07 |
| **damage_formula_precision_analysis.md** | 8.9 KB | 伤害公式精度分析 | ✅ 完整 | 2026-04-07 |
| **ability_priority_matrix.md** | 8.3 KB | 特性优先级矩阵 | ✅ 完整 | 2026-04-07 |
| **pokemon_stat_calibration_plan.md** | 5.3 KB | 精灵数值校准计划 | ✅ 完整 | 2026-04-07 |
| **se_refactor_timing_decision.md** | 6.5 KB | SE (SkillTiming) 重构决策 | 🟡 存档 | 2026-04-07 |

---

## 🔧 配置和构建

### 根目录启动脚本

| 文件 | 大小 | 功能 |
|------|------|------|
| **run_web.py** | 807 B | 启动 Web UI (http://localhost:8765) |
| **start.py** | 307 B | 启动 CLI (python3 start.py) |
| **run.bat** | 558 B | Windows 批处理启动脚本 |

### 配置文件

| 文件 | 大小 | 功能 |
|------|------|------|
| **requirements.txt** | 66 B | Python 依赖列表 |
| **.gitignore** | 489 B | Git 排除规则 |
| **.DS_Store** | 10 KB | macOS 系统文件 (应删除) |

### 隐藏目录

| 目录 | 大小 | 功能 | 状态 |
|------|------|------|------|
| **.claude/** | <1 KB | Claude Code 本地配置 | ✅ 最小化 |
| **.workbuddy/** | ~5 KB | WorkBuddy 工作记忆 | ✅ 无冗余 |
| **.git/** | ~125 MB | 版本历史 (20+ commits) | ✅ 正常 |
| **.venv/** | dependencies | Python 虚拟环境 | ✅ 标准 |
| **.pytest_cache/** | 缓存 | pytest 缓存 | ✅ 自动生成 |

---

## 📁 外部参考 (信息/) — 140 KB

| 文件 | 大小 | 内容 | 优先级 | 建议 |
|------|------|------|--------|------|
| **洛克王国世界（图表）(1)/洛克王国世界攻略_副本.xlsx** | 124 KB | 游戏攻略表 | 🟡 参考 | 可移至 docs/reference/ |

---

## 📊 完整统计

### 按类型统计

```
Python 代码文件:
  src/        11 files    356 KB    8,235 lines
  tests/      10 files    104 KB    2,493 lines
  scripts/     5 files     88 KB    2,617 lines
  ─────────────────────────────────────────
  总计       26 files    548 KB   13,345 lines

文档文件:
  Markdown    11 files    ~50 KB    ~2,000 lines
  HTML        3 files     72 KB     (含 JS/CSS)

数据文件:
  SQLite      3 files   5.064 MB   (数据库 + 日志)
  Excel/CSV   4 files    268 KB    (参考数据)
  JSON        1 file     120 KB    (原始数据)

总计: 54 个文件，131 MB (含 .git)
```

### 按优先级统计

```
🔴 必需 (不可删除):
  - nrc.db (2.0 MB)
  - src/ 所有文件
  - tests/ 所有文件

🟢 重要 (可参考):
  - skills_raw.json (120 KB)
  - skills.xlsx (36 KB)
  - pokemon_stats.xlsx (64 KB)

🟡 可选 (可清理):
  - nrc.db-wal (3.0 MB) ⚠️ 需定期清理
  - nrc.db-shm (32 KB)
  - skills_all.csv (44 KB)
  - crawl_progress.json (9.2 KB)
  - raw/skills_wiki.csv (211 KB)
  - 信息/ (140 KB)
  - .DS_Store (10 KB) ⚠️ 应删除

💾 自动生成 (可忽略):
  - .pytest_cache/
  - .venv/
  - __pycache__/
```

---

## 🎯 推荐操作

### 立即清理 (15 分钟)

1. **删除 macOS 系统文件**
   ```bash
   git rm --cached .DS_Store
   echo ".DS_Store" >> .gitignore
   git commit -m "chore: remove .DS_Store"
   ```

2. **清理数据库临时文件**
   ```bash
   rm data/nrc.db-wal data/nrc.db-shm
   ```

3. **可选：删除过时爬虫数据**
   ```bash
   rm data/crawl_progress.json
   rm data/skills_all.csv
   rm -rf data/raw/
   ```

### 长期优化

1. 定期压缩 nrc.db（每周）
2. 文档整理到 docs/ 统一目录
3. 归档外部参考到 docs/reference/

---

## 文件完整度检查清单

- [x] 核心系统文件完整（src/ 12 files）
- [x] 测试文件完整（tests/ 10 files）
- [x] 数据库就位（data/nrc.db）
- [x] 文档完整度 80%（缺乏 API 文档和开发指南）
- [x] 前端 UI 完整（web/ 3 files）
- [x] 启动脚本完整（3 种平台）
- [x] 版本控制完整（.git 20+ commits）
- [x] 依赖清单完整（requirements.txt）


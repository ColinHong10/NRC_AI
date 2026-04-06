# 洛克王国 AI 战斗模拟器 — 项目结构完整审计

**生成时间**: 2026-04-07  
**项目总大小**: 131 MB (含 .git 历史)  
**主项目大小**: ~5.7 MB (不含 .git 和 .venv)

---

## 目录结构概览

```
.
├── src/                          [356 KB] 核心战斗系统
├── tests/                        [104 KB] 测试用例
├── scripts/                      [88 KB]  数据处理工具
├── data/                         [5.7 MB] 游戏数据（数据库 + 原始数据）
├── web/                          [72 KB]  前端 UI（HTML/CSS/JS）
├── docs/                         [~50 KB] 文档 + 路线图
├── .claude/                      [<1 KB] 本地配置
├── .workbuddy/                   [~5 KB] 工作记忆
├── 信息/                         [140 KB] 游戏攻略表（外部参考）
├── .git/                         [~125 MB] 版本历史
├── .venv/                        [dependencies]
└── .pytest_cache/                [缓存]
```

---

## 深度分析

### 1. SRC 目录 — 核心代码库 [356 KB]

| 文件 | 行数 | 大小 | 功能 | 状态 |
|------|------|------|------|------|
| **battle.py** | 1320 | 52 KB | 战斗引擎 + 队伍构建 + 行动执行 | ✅ 完整 |
| **effect_engine.py** | 2016 | 78 KB | 效果执行引擎（75+ 个 handler） | ✅ 完整 |
| **server.py** | 1232 | 49 KB | FastAPI WebSocket 后端 | ✅ 完整 |
| **effect_data.py** | 648 | 23 KB | 技能+特性结构化配置（35个手工技能） | ✅ 完整 |
| **skill_effects_generated.py** | 793 | 39 KB | 自动生成技能配置（460个） | ✅ 完整 |
| **effect_models.py** | 290 | 15 KB | 效果原语类型定义（85+ 种 E 枚举） | ✅ 完整 |
| **models.py** | 461 | 19 KB | 数据模型（Pokemon/Skill/BattleState） | ✅ 完整 |
| **mcts.py** | 484 | 18 KB | MCTS AI + 经验学习系统 | ✅ 完整 |
| **main.py** | 571 | 23 KB | CLI 主程序 + 批量模拟 | ✅ 完整 |
| **pokemon_db.py** | 256 | 8.4 KB | 精灵数据库加载 + PvP 五维计算 | ✅ 完整 |
| **skill_db.py** | 163 | 5.2 KB | 技能数据库加载 | ✅ 完整 |
| **__init__.py** | 1 | 33 B | 包初始化 | ✅ 无冗余 |

**核心代码统计**:
- 总代码行数: 8,235 行
- 平均文件大小: 32.4 KB
- 最大文件: effect_engine.py (78 KB)

**质量评估**:
- ✅ 架构清晰：数据层(models) → 数据驱动配置(effect_data) → 执行引擎(effect_engine) → 应用层(battle)
- ✅ 低耦合：effect_engine 通过 _HANDLERS 注册表分派，battle.py 无硬编码
- ✅ 可维护：新增技能只需在 effect_data.py 配置 1-2 行
- ⚠️ effect_engine.py 过大(2016 行)：75+ 个 handler 方法可考虑分模块

---

### 2. TESTS 目录 — 测试覆盖 [104 KB]

| 文件 | 行数 | 功能 | 覆盖范围 | 状态 |
|------|------|------|---------|------|
| test_skill_runtime_mappings.py | 622 | 技能效果运行时映射 | 核心技能逻辑 | ✅ |
| test_battle_fixes.py | 556 | 战斗修复验证 | 伤害公式、属性克制、天气系统 | ✅ |
| test_ability_clarifications.py | 347 | 特性触发规则 | 17 个特性配置 | ✅ |
| test_turn_order_rules.py | 159 | 行动顺序系统 | 先手/速度/随机 | ✅ |
| test_battle_triggers.py | 204 | 战斗事件触发 | ON_TURN/ON_ENTER/ON_LEAVE | ✅ |
| test_effect_generic_mechanics.py | 192 | 通用效果机制 | 状态/debuff/buff | ✅ |
| test_generate_skill_effects_patterns.py | 188 | 技能生成模式 | 自动转换器 | ✅ |
| test_manual_high_value_skills.py | 127 | 高价值手工技能 | 40 个核心技能 | ✅ |
| test_server_skill_display.py | 56 | Web 界面技能显示 | 前端集成 | ✅ |
| test_generated_skill_expansion.py | 42 | 生成技能扩展 | 460 个自动技能 | ✅ |

**测试统计**:
- 总行数: 2,493 行
- 测试文件: 10 个
- 全部通过 ✅

**评估**:
- ✅ 覆盖核心功能：战斗、技能、特性、行动顺序
- ✅ 混合测试：单元 + 集成 + 端到端
- ⚠️ 缺少数据校验测试：精灵六维数值与游戏对齐验证
- ⚠️ 缺少性能测试：MCTS 1000+ 对局性能基准

---

### 3. SCRIPTS 目录 — 数据工具 [88 KB]

| 文件 | 行数 | 功能 | 状态 | 使用场景 |
|------|------|------|------|---------|
| generate_skill_effects.py | 1261 | 技能效果自动转换器 | ✅ 完整 | 从 DB description 批量生成 460 个技能配置 |
| init_db.py | 366 | 数据库初始化 | ✅ 完整 | 从 xlsx 导入精灵/技能数据到 nrc.db |
| audit_effect_coverage.py | 218 | 效果覆盖审计 | ✅ 完整 | 统计未配置的技能数量 |
| crawl_pokemon_skills.py | 229 | 爬虫工具 | ✅ 完整 | 抓取技能学习关系到 DB |
| scrape_skills.py | 143 | 技能页面爬虫 | ✅ 完整 | 抓取技能详情（配合 crawl_pokemon_skills 使用） |

**评估**:
- ✅ 用途清晰：一次性数据导入工具
- ⚠️ generate_skill_effects.py 过大(1261 行)：功能单一但实现复杂，建议模块化
- ✅ 已停用脚本应该清理

---

### 4. DATA 目录 — 游戏数据库 [5.7 MB]

| 文件 | 大小 | 类型 | 内容 | 优先级 |
|------|------|------|------|--------|
| nrc.db | 2.0 MB | SQLite | 461 精灵 × 495 技能 × 21,331 学习关系 | 🔴 必需 |
| nrc.db-wal | 3.0 MB | 预写日志 | 数据库事务日志 | 🟡 临时 |
| nrc.db-shm | 32 KB | 共享内存 | 并发控制临时数据 | 🟡 临时 |
| skills_raw.json | 120 KB | JSON | 技能原始数据（460 个技能详情） | 🟢 参考 |
| skills.xlsx | 36 KB | Excel | 技能参数表（手工编辑） | 🟢 参考 |
| pokemon_stats.xlsx | 64 KB | Excel | 精灵六维数据（原始） | 🟢 参考 |
| skills_all.csv | 44 KB | CSV | 技能列表（导出用） | 🟡 过时 |
| 洛克王国世界攻略_副本.xlsx | 124 KB | Excel | 游戏攻略表（外部参考） | 🟡 参考 |
| crawl_progress.json | 9.2 KB | JSON | 爬虫进度记录 | 🟡 过时 |
| raw/skills_wiki.csv | 211 KB | CSV | Wiki 爬虫原始数据 | 🟡 过时 |

**数据库详情** (nrc.db):
```
表：
- pokemon          461 行，精灵编号/名/属性/六维种族值/特性
- skill            495 行，技能编号/名/属性/分类/威力/命中/PP/描述
- pokemon_skill    21,331 行，学习关系（精灵 × 技能）
```

**评估**:
- ✅ 核心数据齐备：nrc.db 包含全部游戏数据
- ⚠️ WAL 日志过大(3.0 MB)：数据库正在事务中或未完全清理
  ```bash
  # 建议定期清理：
  sqlite3 data/nrc.db "PRAGMA journal_mode=DELETE;"  # 改用同步模式
  # 或重新打包数据库以减小文件
  ```
- 🔴 数据陈旧性未知：最后更新日期为 2026-03-30 或更早
- 🔴 **缺少版本控制**：.db 二进制文件不应在 git 中存储（现已在 .gitignore 中排除）
- 🟡 冗余数据：skills.xlsx / pokemon_stats.xlsx / skills_all.csv 可考虑归档

---

### 5. DOCS 目录 — 文档 [~50 KB]

| 文件 | 大小 | 内容 | 状态 | 更新日期 |
|------|------|------|------|---------|
| ROADMAP.md | 7.9 KB | 项目路线图 + 进度 + 待办 | ⚠️ 部分过时 | 2026-04-05 |
| next_session_executable_tasks.md | 10.8 KB | 下次开工任务清单 | 🟡 待执行 | 2026-04-07 |
| game_mechanics_verification_checklist.md | 9.1 KB | 游戏机制核对清单 | 🟢 完整 | 2026-04-07 |
| damage_formula_precision_analysis.md | 8.9 KB | 伤害公式精度分析 | 🟢 完整 | 2026-04-07 |
| ability_priority_matrix.md | 8.3 KB | 特性优先级矩阵 | 🟢 完整 | 2026-04-07 |
| pokemon_stat_calibration_plan.md | 5.3 KB | 精灵数值校准计划 | 🟢 完整 | 2026-04-07 |
| se_refactor_timing_decision.md | 6.5 KB | SE (SkillTiming) 重构决策 | 🟡 存档 | 2026-04-07 |
| SKILLS_ABILITIES_CONFIG_GUIDE.md | 22 KB | 技能+特性配置指南 | ✅ 完整 | 当前 |
| README.md | 3.7 KB | 项目简介 + 快速开始 | ✅ 完整 | 当前 |

**文档评估**:

**✅ 优点**:
- 文档丰富：核心机制、配置指南、路线图都有
- 更新及时：大多数文档为 2026-04-07
- 结构清晰：按主题分类，易查找

**⚠️ 问题**:
1. **ROADMAP.md 过时**: 
   - 最后更新 2026-04-05，已有 2 天
   - "已知数据误差记录" 表格已完成但未更新 ROADMAP
   - 待完成部分与 docs/ 中的任务清单重复

2. **文档分散**:
   - ROADMAP.md 在项目根目录
   - 决策文档在 docs/ 目录
   - 配置指南在根目录
   - 建议统一收入 docs/ 或创建 docs/architecture/ 子目录

3. **缺少关键文档**:
   - 🔴 缺少"API 文档"（effect_engine, battle.py 接口）
   - 🔴 缺少"数据库 schema 文档"
   - 🔴 缺少"开发指南"（如何新增特性/技能）
   - 🔴 缺少"测试运行指南"

---

### 6. WEB 目录 — 前端 UI [72 KB]

| 文件 | 大小 | 内容 | 功能 |
|------|------|------|------|
| battle.html | 40.9 KB | 战斗界面 | WebSocket 实时对战，仿 Pokémon Showdown UI |
| team.html | 26.1 KB | 队伍编辑 | 队伍构建器（选择精灵/配置技能/设置性格） |
| index.html | 247 B | 入口 | 重定向到 battle.html |

**前端技术栈**:
- WebSocket 通信
- CSS Grid / Flexbox 布局
- 原生 JavaScript（无框架）
- 精灵用 emoji 占位（可升级为真实图片）

**评估**:
- ✅ 功能完整：战斗UI + 队伍编辑
- ✅ 轻量化：未使用 React/Vue，HTTP 传输小
- ⚠️ 代码分散：battle.html 40 KB 内含所有 HTML/CSS/JS，建议分离
- ⚠️ 缺少错误处理：WebSocket 断线重连不够完善
- ⚠️ 性能：每帧重绘全 DOM，可考虑虚拟 DOM 或 Canvas

---

### 7. 根目录文件

| 文件 | 大小 | 功能 | 状态 |
|------|------|------|------|
| ROADMAP.md | 7.9 KB | 项目路线图 | ⚠️ 需更新 |
| SKILLS_ABILITIES_CONFIG_GUIDE.md | 22 KB | 配置指南 | ✅ 完整 |
| README.md | 3.7 KB | 快速开始 | ✅ 完整 |
| run_web.py | 807 B | Web 启动脚本 | ✅ 完整 |
| start.py | 307 B | CLI 启动脚本 | ✅ 完整 |
| run.bat | 558 B | Windows 启动脚本 | ✅ 兼容 |
| requirements.txt | 66 B | 依赖列表 | ✅ 完整 |
| .gitignore | 489 B | Git 排除规则 | ✅ 完整 |
| .DS_Store | 10 KB | macOS 系统文件 | 🔴 应排除 |

**评估**:
- ⚠️ .DS_Store 不应纳入版本控制（已占 10 KB）

---

### 8. 隐藏目录

#### .claude/ [<1 KB]
- settings.local.json (586 B)：本地开发配置
- ✅ 最小化，无冗余

#### .workbuddy/ [~5 KB]
- memory/MEMORY.md：项目长期记忆
- memory/2026-03-31.md、2026-04-04.md：会话记录
- ✅ 工作工具产物，无冗余

#### .git/ [~125 MB]
- 版本历史 20+ commits
- ⚠️ 首次 clone 会下载 125 MB

---

### 9. 信息/ 目录 [140 KB] — 【建议归档】

内容：游戏攻略表外部参考
- 洛克王国世界（图表）(1)/洛克王国世界攻略_副本.xlsx

**评估**:
- 🟡 外部参考资料，与项目代码无关
- 💡 建议：移出项目目录或创建 docs/reference/ 专用目录

---

## 项目质量指标

| 指标 | 值 | 评级 |
|------|-----|------|
| **代码总行数** | 8,235 | ✅ 合理 |
| **代码vs测试比** | 3.3:1 | ✅ 健康 |
| **文件平均大小** | 32 KB | ✅ 良好 |
| **最大单文件** | 78 KB (effect_engine.py) | ⚠️ 可优化 |
| **测试覆盖** | 2,493 行 | ✅ 充分 |
| **文档完整度** | 80% | ⚠️ 部分过时 |
| **git 历史** | 20+ commits | ✅ 健康 |

---

## 🎯 清理建议

### P0 — 必须处理（影响项目运行）

1. **清理数据库临时文件** ⏰ 5 分钟
   ```bash
   # nrc.db-wal / nrc.db-shm 是数据库临时文件，可定期清理
   rm data/nrc.db-wal data/nrc.db-shm
   sqlite3 data/nrc.db "PRAGMA journal_mode=WAL;"  # 重新初始化
   ```

2. **更新 ROADMAP.md** ⏰ 30 分钟
   - 更新"最后更新时间"为 2026-04-07
   - 同步 docs/next_session_executable_tasks.md 的最新任务
   - 标记已完成的项目

3. **移除 .DS_Store** ⏰ 1 分钟
   ```bash
   echo ".DS_Store" >> .gitignore
   git rm --cached .DS_Store
   git commit -m "chore: remove .DS_Store"
   ```

### P1 — 应该处理（改进可维护性）

4. **创建标准文件结构** ⏰ 1 小时
   ```
   docs/
   ├── README.md                    # 文档首页
   ├── architecture/
   │   ├── overview.md              # 架构总览
   │   ├── effect-engine.md         # 效果引擎设计
   │   ├── battle-flow.md           # 战斗流程
   │   └── data-models.md           # 数据模型
   ├── guides/
   │   ├── adding-skill.md          # 如何新增技能
   │   ├── adding-ability.md        # 如何新增特性
   │   └── running-tests.md         # 如何运行测试
   ├── references/
   │   ├── effect-tag-reference.md  # EffectTag 完整列表
   │   └── effect-enum-reference.md # E 枚举完整列表
   └── progress/
       ├── roadmap.md               # 迁移 ROADMAP.md
       ├── next-tasks.md            # 迁移 next_session_executable_tasks.md
       └── known-issues.md          # 已知问题
   ```

5. **分离 effect_engine.py** ⏰ 2 小时
   - 当前 2016 行，handler 数 75+
   - 建议分模块：
     ```
     src/effects/
     ├── __init__.py              # 导出 EffectExecutor
     ├── base.py                  # Ctx, EffectExecutor 定义
     ├── handlers/
     │   ├── damage.py            # 伤害类 handler
     │   ├── status.py            # 状态类 handler
     │   ├── buff_debuff.py       # 增减益 handler
     │   ├── ability.py           # 特性 handler
     │   ├── drive.py             # 传动 handler
     │   └── marks.py             # 印记 handler
     └── _HANDLERS.py             # 注册表
     ```

6. **整理 scripts/** 目录 ⏰ 1 小时
   - 标记"已停用"脚本
   - 添加每个脚本的使用文档

### P2 — 可选（优化体验）

7. **分离 battle.html** ⏰ 2 小时
   - 拆分为 HTML/CSS/JS 三个文件
   - 使用模块化 JavaScript

8. **添加性能测试** ⏰ 2 小时
   - 基准测试：1000 场对局耗时
   - 内存占用峰值

9. **从版本控制中移除数据库**
   - 使用 git-lfs 或下载脚本
   - 减少 clone 大小

10. **归档外部参考** ⏰ 30 分钟
    - 信息/ 目录移至 docs/reference/

---

## 📋 ROADMAP 问题分析

### 当前状态
- **最后更新**: 2026-04-05（2 天前）
- **阶段**: 仍在阶段一（战斗数据高度复刻）

### 过时内容

1. **"本次完成的重大修正（2026-04-05）"**
   - ✅ 所有 6 项修正已验证完成
   - 应移至"已完成"历史区

2. **"待完成 🔴（阶段一核心缺口）"**
   - P0 — 真实伤害校准：5/5 子项未变更
   - P1 — 特性补全：仍为"17/170+"
   - P2 — 技能效果修正：无进展（但应对系统在代码中已部分实现）

3. **未同步的新文档**
   - docs/damage_formula_precision_analysis.md ✅ (2026-04-07)
   - docs/ability_priority_matrix.md ✅ (2026-04-07)
   - docs/pokemon_stat_calibration_plan.md ✅ (2026-04-07)
   - docs/next_session_executable_tasks.md ✅ (2026-04-07)
   
   这些都是决策/规划文档但 ROADMAP 中未反映

### 建议
- 将 ROADMAP.md 重定向为索引，指向 docs/ 具体文档
- 或更新 ROADMAP.md 为今日日期，补充最新任务

---

## 📊 项目代码质量总结

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构设计** | ⭐⭐⭐⭐⭐ | 数据驱动 + 注册表模式，低耦合 |
| **代码组织** | ⭐⭐⭐⭐ | 清晰但个别模块过大 |
| **测试覆盖** | ⭐⭐⭐⭐ | 10 个测试文件，2,493 行 |
| **文档完整** | ⭐⭐⭐ | 大多完整但部分过时 + 分散 |
| **性能** | ⭐⭐⭐ | 未有性能基准 |
| **可维护性** | ⭐⭐⭐⭐ | 易扩展但 effect_engine 可细化 |
| **数据验证** | ⭐⭐ | 缺少与游戏实测数据对照 |

**总体评级**: ⭐⭐⭐⭐ (4/5) — 架构良好，细节待完善

---

## 关键发现

### 🚨 数据问题
1. **nrc.db-wal 过大** (3.0 MB) — 需定期清理
2. **数据版本未知** — 最后更新时间不明确
3. **缺少游戏实测验证** — ROADMAP P0 项"真实伤害校准"仍未开始

### ✅ 系统优点
1. **架构清晰** — 从配置到执行，路径明确
2. **易于扩展** — 新增技能/特性流程标准化
3. **测试完整** — 核心系统都有测试覆盖
4. **Web UI 完整** — 可视化战斗系统已就绪

### ⚠️ 待改进项
1. **单个文件过大** — effect_engine.py (2016 行)
2. **文档分散** — 需统一收入 docs/
3. **缺乏性能基准** — 无法量化 MCTS 性能
4. **数据未版本化** — 游戏数据无版本控制
5. **缺少集成文档** — 如何将模拟器接入游戏


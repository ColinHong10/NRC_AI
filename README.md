# 洛克王国战斗 AI 模拟器 / Roco Kingdom Battle AI Simulator

基于蒙特卡洛树搜索（MCTS）的洛克王国（Roco Kingdom）对战模拟系统，支持 AI 自战、批量统计、玩家对战模式，以及 Web 图形化战斗界面。

A Monte Carlo Tree Search (MCTS) based battle simulator for Roco Kingdom, featuring AI vs AI, batch statistics, Player vs AI modes, and a web-based graphical battle UI.

---

## 目录 / Table of Contents

- [版本日志 / Changelog](#版本日志--changelog)
- [功能特性 / Features](#功能特性--features)
- [队伍配置 / Teams](#队伍配置--teams)
- [战斗规则 / Battle Rules](#战斗规则--battle-rules)
- [AI 算法 / AI Algorithm](#ai-算法--ai-algorithm)
- [效果标签引擎 / Effect Tag Engine](#效果标签引擎--effect-tag-engine)
- [Web 图形界面 / Web UI](#web-图形界面--web-ui)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [项目结构 / Project Structure](#项目结构--project-structure)

---

## 版本日志 / Changelog

### v2.0 (2026-04-04) -- Web 图形界面 + 全量技能数据 + 引擎重构

**新增功能：**

- **Web 图形战斗界面**：FastAPI + WebSocket 实时通信前端，仿 Pokemon Showdown 风格暗色主题。包含战场画布（HP 条/精灵占位/MP 点）、队伍预览条、技能面板、实时战斗播报，支持攻击抖动/受击闪光/防御护盾等 CSS 动画。
- **队伍编辑器**：开战前可搜索并自定义选择 6 只精灵及其配招，支持中英文关键词搜索、属性克制提示。
- **Wiki 技能数据爬取**：从 BiliGame Wiki 批量抓取全精灵技能表（精灵技能/血脉技能/可学技能），`pokemon_skill` 记录数从 8,808 增至 21,331（+142%），覆盖缠丝劲、闪击折返等此前缺失的技能。
- **精确战斗日志**：每回合输出格式化战报（"XX 使用 XX 对 YY 造成 N 点伤害，剩余 HP X"），按伤害/回复/状态/换人分色显示。

**引擎重构：**

- **效果标签引擎全面接管**：删除旧版 `parse_effect` 正则解析及 battle.py 中全部 fallback 路径，495 个技能统一走新引擎执行。加载优先级：手动配置（35 个）> 自动生成（460 个）。
- **Handler 注册表架构**：`effect_engine.py` 用 `_HANDLERS` 字典替代三处重复 if-elif 分发链，统一 `_apply_tag(tag, ctx)` 入口；技能效果、应对子效果、特性效果共用同一套 handler 集合。
- **工厂函数模式**：`effect_data.py` 引入 `T()`/`counter()`/`on_attack()`/`on_status()`/`on_defense()` 工厂函数与 `attack_on_status_interrupt()`/`defense_counter()` 等模板，新增技能配置通常只需 1 行代码。
- **特性系统纯数据驱动**：新增 `ABILITY_COMPUTE`/`ABILITY_INCREMENT_COUNTER`/`TRANSFER_MODS`/`BURN_NO_DECAY` 等标签，消除 `_handle_special_ability` 中的魔法字符串路由。
- **自动生成转换器**：`scripts/generate_skill_effects.py` 从数据库 description 字段批量生成 `skill_effects_generated.py`。

**Bug 修复：**

- 湿润印记写入后从未被读取 -> 新增 `_apply_moisture_mark()` 在每回合初统一处理
- 听桥 MIRROR_DAMAGE 使用错误技能重新计算伤害 -> 改为直接使用 `ctx.damage`（实际造成伤害值）
- 减伤效果在应对子效果之后应用 -> 移至应对之前，保证镜面反射等效果获得正确的减伤后数值
- 能量返还可能导致 MP 溢出上限 -> 先计算实际消耗再一次性扣减
- AI 决策异常时回退到固定动作 -> 改为随机选择合法动作，并输出完整 traceback 日志

### v1.5 (2026-04-03) -- 效果标签引擎 + 对抗式 MCTS

- 引入 `EffectTag` 枚举体系替代正则解析，结构化描述技能效果类型（伤害/治疗/状态/印记/传动/打断/永久修改等）
- 配置 35 个核心技能 + 12 个特性的效果标签
- MCTS 升级为对抗式（双方交替 UCB 选择），替换原有单人视角随机 rollout
- 使用 `BattleState.deep_copy()` 替代 `deepcopy`，性能提升约 3-5 倍
- 状态签名纳入 buff 层数信息，减少重复探索等价节点
- 新增被动换人机制：精灵倒下时选择上场精灵，不占用行动回合
- 安全修复：`eval()` 替换为 `ast.literal_eval()`
- 新增异常状态支持：中毒（叠层）、灼烧（叠层）、冻结、麻痹、睡眠

### v1.0 (2026-03-29) -- 初始版本

- 基于 CSV/Excel 数据库的精灵与技能加载系统
- 基础五维属性计算公式（HP / 攻击 / 防御 / 魔攻 / 魔防 / 速度）
- 18 属性克制矩阵（含本系加成 STAB 1.5x）
- 能量系统（技能消耗能量，不足时聚能回复 5 点）
- 单人视角 MCTS AI（150 次模拟/回合）
- 经验学习系统（ExperienceDB）：记录高胜率动作序列，rollout 阶段加权采样
- 终端菜单：单场对战 / 批量模拟 / 学习实验 / 玩家 vs AI
- 默认阵容：毒队（千棘盔/影狸/裘卡/琉璃水母/迷迷箱怪/海豹船长）vs 翼王队（燃薪虫/圣羽翼王/翠顶夫人/秩序魁墨/声波缇塔）

---

## 功能特性 / Features

**中文：**

- **MCTS AI**：双方均由蒙特卡洛树搜索驱动，采用对抗式 MCTS（双方交替 UCB 选择），默认每回合 150 次模拟
- **经验学习**：AI 积累对战记录，逐步优化决策策略
- **玩家对战**：终端交互界面 + Web 图形界面两种模式，支持手动控制队伍与 AI 对战
- **批量模拟**：一键运行多场对战，统计胜率与平均回合数
- **学习实验**：分阶段观察 AI 随经验积累的成长曲线
- **效果标签引擎**：结构化效果系统，495 个技能已配置效果标签，覆盖吸血/减伤/应对/连击/印记/传动/打断/永久修改等复杂效果
- **异常状态**：中毒（叠层）、灼烧（叠层）、冻结、麻痹、睡眠
- **被动换人**：精灵倒下时选择上场精灵，不占用行动回合
- **Web 图形界面**：仿 Showdown 风格实时战斗画面，支持自定义队伍、精确战报播报、防御动画、属性克制提示
- **完整技能数据库**：21,331 条精灵-技能关联记录，覆盖 Wiki 全量数据

**English：**

- **MCTS AI**: Both sides driven by Adversarial MCTS with alternating UCB selection; 150 simulations per turn by default
- **Experience Learning**: AI accumulates battle records and progressively improves decision-making
- **Player vs AI**: Terminal UI and Web graphical UI; manual control against the AI
- **Batch Simulation**: Run multiple battles at once; get win-rate and avg-round statistics
- **Learning Experiment**: Stage-by-stage observation of AI growth as experience accumulates
- **Effect Tag Engine**: Structured effect system with 495 configured skills; supports lifesteal, damage reduction, counters, multi-hit, marks, drive, interrupt, permanent mods
- **Status Effects**: Poison (stacking), Burn (stacking), Freeze, Paralysis, Sleep
- **Passive Switch on Faint**: Choose replacement when one faints — no turn cost
- **Web Graphical UI**: Showdown-style real-time battle screen with team builder, precise battle log, defense animation, type-advantage hints
- **Complete Skill Database**: 21,331 pokemon-skill association records from full Wiki crawl

---

## 队伍配置 / Teams

| 队伍 / Team | 成员 / Members |
|---|---|
| **A 队（毒队 / Toxic）** | 千棘盔、影狸、裘卡、琉璃水母、迷迷箱怪、海豹船长 |
| **B 队（翼王队 / Wing King）** | 燃薪虫、圣羽翼王、翠顶夫人、迷迷箱怪、秩序魁墨、声波缇塔 |

> Web 模式下玩家可通过队伍编辑器自由选择 6 只精灵及配招。

---

## 战斗规则 / Battle Rules

**中文：**

- **能量系统**：每个技能消耗能量，不足时自动使用「汇合聚能」回复 5 点
- **速度判定**：按速度数值决定先后手（除非技能带有「必定先手」属性）
- **必命中**：无命中率计算，技能必然命中
- **无暴击**：不存在暴击机制
- **换人**：己方精灵倒下时被动选择上场精灵（不消耗回合）；可主动换人（消耗行动机会）
- **效果标签引擎**：全部 495 个技能均走新引擎执行
- **特性系统**：支持入场/离场/回合结束/使用技能/被攻击/击败敌方等多时机触发

**English：**

- **Energy System**: Each skill costs energy; "Assemble & Charge" recovers 5 when insufficient
- **Speed Priority**: Action order determined by Speed stat (unless skill has forced priority)
- **Always Hit**: No accuracy rolls
- **No Critical Hits**: No crit mechanic
- **Switching**: Passive replacement on faint (no turn cost); manual switching consumes action
- **Effect Tag Engine**: All 495 skills execute through the new engine
- **Ability System**: Multiple trigger timings — on enter/leave, turn end, skill use, take hit, kill, etc.

### 伤害公式 / Damage Formula

```
Damage = (ATK / DEF) x 0.9 x Skill Power x Type Multiplier x STAB(1.5) x Stat Stage x (1 - Damage Reduction)
```

### 五维计算公式 / Stat Formula

```
HP     = [1.7 x Base + 0.85 x IV + 70] x (1 + Nature) + 100
Others = [1.1 x Base + 0.55 x IV + 10]  x (1 + Nature) + 50
```

- IV: 6 的倍数 (48~60), 6 项中 3 项有 IV，3 项 = 0；默认完美 IV = 60
- Nature: 1 项 +20%, 1 项 -10%，其余 0%

---

## AI 算法 / AI Algorithm

双方 AI 均采用 **对抗式蒙特卡洛树搜索（Adversarial MCTS）** 进行零和博弈优化：

1. **Selection**：双方交替按 UCB1 公式选择最优子节点
2. **Expansion**：扩展未探索的动作
3. **Simulation**：随机 rollout 至终局
4. **Backpropagation**：将结果反向更新节点价值

**性能优化**：
- 使用 `BattleState.deep_copy()` 替代 `deepcopy`，性能提升约 3-5 倍
- 状态签名包含 buff 层数信息，避免重复探索等价节点

**经验系统**（`ExperienceDB`）：
- 记录历史对战中高胜率的动作序列
- Rollout 阶段对高胜率动作给予更高采样权重
- AI 随对战场数增加逐步优化决策

---

## 效果标签引擎 / Effect Tag Engine

全新的结构化效果执行系统，完全替代原有正则解析方式：

```
src/effect_models.py       -->  E 枚举 + Timing 枚举 + EffectTag / AbilityEffect 数据类
src/effect_data.py         -->  工厂函数 T()/counter()/on_attack() 等 + 全部技能/特性配置
src/effect_engine.py       -->  _HANDLERS 注册表 + _apply_tag() 统一入口
src/skill_effects_generated.py  -->  自动生成的 460 个技能效果配置
src/battle.py              -->  战斗流程集成（印记处理/减伤顺序/能量计算修正）
scripts/generate_skill_effects.py -->  DB description -> generated code 转换器
```

**已支持的子系统：**

| 子系统 | 说明 |
|---|---|
| Marks（印记） | 毒印记、湿润印记等团队持久 Buff，每回合初统一结算 |
| Drive（传动） | 使用技能后的被动触发效果链 |
| Interrupt（打断） | 特定条件下中断敌方行动 |
| Permanent Mod（永久修改） | 不可被清除的属性变化 |
| Conditional Buff | 基于血量比例等条件的动态增益 |
| Mirror Damage（镜面反射） | 将受到的伤害反射给攻击方 |
| Moisture Mark（湿润印记） | 降低全体技能能量消耗 |

---

## Web 图形界面 / Web UI

技术栈：FastAPI + WebSocket 后端 + 纯 HTML/CSS/JS 前端

**启动方式：**

```bash
python run_web.py
# 自动打开浏览器 http://localhost:8765/battle
```

**通信协议（WebSocket）：**

| Command | 说明 |
|---|---|
| `start` | 使用默认毒队 vs 翼王队开始战斗 |
| `start_custom` | 使用 sessionStorage 中的自选队伍开始战斗 |
| `action` | 提交玩家行动（技能/换人） |
| `get_state` | 获取当前战斗状态 |
| `reset` | 重置战斗 |

**REST API：**

| Endpoint | 说明 |
|---|---|
| `GET /api/pokemon/list?q=` | 搜索精灵列表（支持名称/属性/特性关键词） |
| `GET /api/pokemon/skills?name=` | 获取指定精灵的可学技能列表 |

**界面组成：**
- 战场画布：HP 条、精灵占位（emoji）、MP 能量点
- 队伍预览条：双方 6 只精灵状态概览
- 技能面板：4 个技能按钮 + 聚能 + 换人（含属性克制提示）
- 战斗播报区：格式化实时战报，按事件类型分色
- 动画效果：攻击抖动、受击闪光、浮动伤害数字、防御护盾

**队伍编辑器（`/team` 页面）：**
- 全精灵列表本地过滤搜索
- 点击精灵卡片打开技能选择弹窗
- 校验 6 只唯一精灵，每只 4 个技能
- AI 对手可选毒队或翼王队

---

## 快速开始 / Quick Start

### 环境要求 / Requirements

- Python 3.8+
- Dependencies: `fastapi`, `uvicorn[standard]`, `websockets`, `openpyxl`, `pandas`, `beautifulsoup4`, `requests`

```bash
pip install -r requirements.txt
```

### 运行 / Run

```bash
# Option 1 -- Web 图形界面（推荐 / Recommended）
python run_web.py

# Option 2 -- 终端主菜单 / Terminal menu
python start.py

# Option 3 -- 直接运行 / Direct
python src/main.py
```

### Windows 双击启动 / Windows Double-click

双击 `run.bat` 即可启动终端版本。

### 终端菜单 / Terminal Menu

```
1. 单场对战（带经验）     Single battle (with experience)
2. 批量模拟 50 场         Batch simulation (50 games)
3. 学习实验 100 场        Learning experiment (100 games)
4. 快速测试 10 场         Quick test (10 games, no experience)
5. A vs B 20 场（无经验） A vs B: 20 games WITHOUT experience
6. A vs B 20 场（带经验） A vs B: 20 games WITH experience
7. 玩家 vs AI             PLAYER vs AI (with experience)
0. 退出并保存经验         Exit & save experience
```

---

## 项目结构 / Project Structure

```
NRC_AI/
|-- src/
|   |-- main.py                      # 主程序 & 终端菜单
|   |-- mcts.py                      # 对抗式 MCTS AI + 经验系统
|   |-- battle.py                    # 战斗逻辑 + 效果引擎集成
|   |-- models.py                    # 数据模型（Pokemon/Skill/Type/BattleState）
|   |-- pokemon_db.py                # 精灵数据库加载
|   |-- skill_db.py                  # 技能数据库加载
|   |-- effect_models.py             # 效果类型定义（E 枚举/Timing/EffectTag）
|   |-- effect_data.py               # 手动效果配置 + 工厂函数
|   |-- effect_engine.py             # 效果执行引擎（_HANDLERS 注册表）
|   |-- skill_effects_generated.py   # 自动生成的 460 个技能效果
|   |-- server.py                    # FastAPI + WebSocket 服务端
|-- web/
|   |-- battle.html                  # 图形战斗界面
|   |-- team.html                    # 队伍编辑器
|-- scripts/
|   |-- generate_skill_effects.py    # DB -> 生成效果代码转换器
|   |-- crawl_pokemon_skills.py      # Wiki 技能数据爬虫
|-- data/
|   |-- nrc.db                       # SQLite 主数据库（精灵/技能/关联表）
|   |-- skills.xlsx / skills_all.csv # 技能原始数据
|   |-- pokemon_stats.xlsx           # 精灵种族值数据
|   |-- skills_wiki.csv              # Wiki 爬取的技能原始数据
|-- run_web.py                       # Web 启动脚本
|-- start.py                         # 终端启动脚本
|-- run.bat                          # Windows 启动脚本
|-- requirements.txt                 # Python 依赖
```

---

## License

MIT

# 洛克王国战斗 AI 模拟器 / Rokugou Battle AI Simulator

> 基于蒙特卡洛树搜索（MCTS）的洛克王国对战模拟系统，支持 AI 自战、批量统计与玩家对战模式。
> A Monte Carlo Tree Search (MCTS) based battle simulator for Rokugou (洛克王国), featuring AI vs AI, batch statistics, and Player vs AI modes.

---

## 目录 / Table of Contents

- [功能特性 / Features](#功能特性--features)
- [队伍配置 / Teams](#队伍配置--teams)
- [战斗规则 / Battle Rules](#战斗规则--battle-rules)
- [AI 原理 / AI Algorithm](#ai-原理--ai-algorithm)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [项目结构 / Project Structure](#项目结构--project-structure)

---

## 功能特性 / Features

**中文：**
- 🤖 **MCTS AI**：双方均由蒙特卡洛树搜索驱动，支持可配置模拟次数
- 📚 **经验学习**：AI 积累对战记录，逐步优化决策策略
- ⚔️ **玩家对战**：交互式界面，支持玩家手动控制 A 队与 AI 对战
- 📊 **批量模拟**：一键运行多场对战，统计胜率与平均回合数
- 🔬 **学习实验**：分阶段观察 AI 随经验积累的成长曲线
- 💊 **丰富技能系统**：从 CSV/Excel 数据库加载技能，支持吸血、减伤、应对、连击等复杂效果
- 🌀 **异常状态**：中毒（叠层）、灼烧（叠层）、冻结、麻痹、睡眠

**English：**
- 🤖 **MCTS AI**: Both sides driven by Monte Carlo Tree Search with configurable simulation count
- 📚 **Experience Learning**: AI accumulates battle records and progressively improves decision-making
- ⚔️ **Player vs AI**: Interactive terminal UI for manual control of Team A against the AI
- 📊 **Batch Simulation**: Run multiple battles at once and get win-rate / avg-round statistics
- 🔬 **Learning Experiment**: Stage-by-stage observation of AI growth as experience accumulates
- 💊 **Rich Skill System**: Skills loaded from CSV/Excel DB with effects like life drain, damage reduction, counters, multi-hit
- 🌀 **Status Effects**: Poison (stacking), Burn (stacking), Freeze, Paralysis, Sleep

---

## 队伍配置 / Teams

| 队伍 / Team | 成员 / Members |
|---|---|
| **A 队（毒队）** | 千棘盔、影狸、裘卡、琉璃水母、迷迷箱怪、海豹船长 |
| **Team A (Toxic)** | Qianjikui, Yingli, Qiuka, Liulishuimu, Mimixiangguai, Haibao Chuanzhang |
| **B 队（翼王队）** | 燃薪虫、圣羽翼王、翠顶夫人、迷迷箱怪、秩序魁墨、声波缇塔 |
| **Team B (Wing King)** | Ranxinchong, Shengyu Yiwang, Cuiding Furen, Mimixiangguai, Zhixu Kuimo, Shengbo Tita |

---

## 战斗规则 / Battle Rules

**中文：**
- **能量系统**：每个技能消耗能量，能量不足时自动使用「汇合聚能」回复 5 点
- **速度判定**：按速度数值决定先后手（除非技能带有「必定先手」属性）
- **必命中**：无命中率计算，技能必然命中
- **无暴击**：不存在暴击机制
- **换人系统**：己方精灵倒下时自动换人；可主动换人（消耗行动机会）

**English：**
- **Energy System**: Each skill costs energy; when insufficient, the unit uses "Assemble & Charge" to recover 5 energy
- **Speed Priority**: Action order is determined by Speed stat (unless a skill has forced priority)
- **Always Hit**: No accuracy rolls — all moves land
- **No Critical Hits**: No crit mechanic exists
- **Switching**: Auto-switch when a Pokémon faints; manual switching costs the turn action

### 伤害公式 / Damage Formula

```
伤害 = 攻击/防御 × 0.9 × 技能威力 × 克制 × 本系(1.5) × 能力等级 × (1-减伤)
Damage = (ATK / DEF) × 0.9 × Skill Power × Type Multiplier × STAB(1.5) × Stat Stage × (1 − Damage Reduction)
```

---

## AI 原理 / AI Algorithm

**中文：**
双方 AI 均采用 **蒙特卡洛树搜索（MCTS）** 进行零和博弈优化：
1. **Selection**：按 UCB1 公式选择最优子节点
2. **Expansion**：扩展未探索的动作
3. **Simulation**：随机 rollout 至终局
4. **Backpropagation**：将结果反向更新节点价值

经验系统（`ExperienceDB`）会记录历史对战中高胜率的动作序列，在 rollout 阶段对这些动作给予更高采样权重，使 AI 随对战场数增加逐步"学聪明"。

**English：**
Both AIs use **Monte Carlo Tree Search (MCTS)** for zero-sum game optimization:
1. **Selection**: Choose best child via UCB1 formula
2. **Expansion**: Expand unvisited actions
3. **Simulation**: Random rollout to terminal state
4. **Backpropagation**: Update node values with the result

The experience system (`ExperienceDB`) records high-win-rate action sequences from past battles and assigns higher sampling weights during rollouts, allowing the AI to "learn" over successive games.

---

## 快速开始 / Quick Start

### 环境要求 / Requirements

- Python 3.8+
- 依赖库 / Dependencies: `openpyxl`, `pandas`

```bash
pip install -r requirements.txt
```

### 运行 / Run

```bash
# 方式一 / Option 1 — 直接运行主菜单 / Launch main menu
python start.py

# 方式二 / Option 2
python src/main.py
```

### Windows 双击启动 / Windows Double-click

直接双击 `run.bat` 即可启动。
Double-click `run.bat` to launch on Windows.

### 菜单说明 / Menu Options

```
1. 单场对战（带经验）     Watch single battle (with experience)
2. 批量模拟 50 场         Batch simulation (50 games)
3. 学习实验 100 场        Learning experiment (100 games)
4. 快速测试 10 场         Quick test (10 games, no experience)
5. A vs B 20 场（无经验） A vs B: 20 games WITHOUT experience
6. A vs B 20 场（带经验） A vs B: 20 games WITH experience
7. 玩家 vs AI ★          PLAYER vs AI (with experience) ★
0. 退出并保存经验         Exit & save experience
```

---

## 项目结构 / Project Structure

```
NRC_AI/
├── src/
│   ├── main.py          # 主程序 / Main program & menu
│   ├── mcts.py          # MCTS AI + 经验系统 / MCTS AI + Experience system
│   ├── battle.py        # 战斗逻辑 / Battle logic
│   ├── models.py        # 数据模型 / Data models (Pokémon, skills, type chart)
│   ├── pokemon_db.py    # 精灵数据库加载 / Pokémon DB loader
│   ├── skill_db.py      # 技能数据库加载 / Skill DB loader
│   └── __init__.py
├── data/
│   ├── skills_all.csv            # 技能数据 / Skill data
│   ├── pokemon_stats.xlsx        # 精灵属性 / Pokémon stats
│   └── experience/
│       ├── experience_team_a.md  # AI-A 经验记录 / AI-A experience log
│       └── experience_team_b.md  # AI-B 经验记录 / AI-B experience log
├── start.py             # 启动脚本 / Launch script
├── run.bat              # Windows 启动 / Windows launcher
└── requirements.txt
```

---

## License

MIT

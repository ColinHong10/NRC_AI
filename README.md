# 洛克王国战斗 AI 模拟器

基于蒙特卡洛树搜索（MCTS）的洛克王国自动对战模拟系统，支持 AI 自战、玩家对战、Web 图形界面。

---

## 依赖

```bash
pip install fastapi uvicorn[standard] openpyxl pandas beautifulsoup4 requests
```

---

## 启动

```bash
# Web 图形界面（推荐）
python run_web.py
# 访问 http://localhost:8765/battle

# 终端版本
python start.py
```

---

## 目录结构

```
NRC_AI/
├── data/                       # 数据目录（路径依赖）
│   ├── nrc.db                  # SQLite 主数据库（精灵/技能/血脉技能/可学技能）
│   ├── pokemon_stats.xlsx      # 精灵种族值原始数据
│   ├── skills_all.csv         # 技能原始数据（来源 A）
│   ├── skills.xlsx             # 技能数据（来源 B）
│   └── raw/
│       └── skills_wiki.csv    # Wiki 爬取原始数据
│
├── src/                        # 核心源码
│   ├── main.py                 # 终端主菜单入口
│   ├── battle.py               # 战斗逻辑 + 效果引擎集成
│   ├── models.py               # Pokemon / Skill / Type / BattleState 模型
│   ├── pokemon_db.py           # 精灵数据库加载
│   ├── skill_db.py             # 技能数据库加载
│   ├── mcts.py                 # 对抗式 MCTS AI + 经验学习系统
│   ├── effect_models.py        # EffectTag / Timing 枚举定义
│   ├── effect_data.py          # 手动技能/特性效果配置（35 个）
│   ├── effect_engine.py        # 效果执行引擎（Handler 注册表）
│   ├── skill_effects_generated.py  # 自动生成技能效果（460 个）
│   └── server.py               # FastAPI + WebSocket 服务端
│
├── web/                        # Web 前端
│   ├── battle.html             # 图形战斗界面
│   └── team.html               # 队伍编辑器
│
├── scripts/                    # 工具脚本
│   ├── crawl_pokemon_skills.py  # BiliGame Wiki 技能数据爬虫
│   ├── audit_effect_coverage.py    # 技能效果覆盖率 / 特性缺口审计
│   └── generate_skill_effects.py  # 数据库 description → 效果代码生成器
│
├── run_web.py                  # Web 界面启动脚本
├── start.py                    # 终端菜单启动脚本
└── run.bat                     # Windows 双击启动脚本
```

---

## 数据说明

所有数据文件位于 `data/` 目录，代码中通过相对路径加载：

| 文件 | 用途 | 加载位置 |
|---|---|---|
| `nrc.db` | 主数据库：精灵信息、技能、关联表 | `pokemon_db.py`、`skill_db.py` |
| `pokemon_stats.xlsx` | 精灵种族值原始数据 | `pokemon_db.py` |
| `skills_all.csv` / `skills.xlsx` | 技能原始数据 | `skill_db.py` |
| `raw/skills_wiki.csv` | Wiki 爬取的技能原始数据 | `scripts/crawl_pokemon_skills.py` |

---

## 主要功能

- **AI 自战**：双方均由对抗式 MCTS 驱动，每回合 150 次模拟
- **玩家 vs AI**：终端或 Web 界面手动控制队伍
- **批量模拟**：统计胜率、平均回合数
- **经验学习**：AI 随对局积累优化决策
- **Web 图形界面**：仿 Pokemon Showdown 风格，支持队伍编辑、实时战斗动画

---

## 战斗规则

- 能量系统：技能消耗能量，不足时自动聚能回复 5 点
- 速度判定先后手（除非技能有必定先手属性）
- 全部 495 个技能走统一效果标签引擎执行
- 支持异常状态（中毒/灼烧/冻结/麻痹/睡眠）、印记、传动、镜面反射等

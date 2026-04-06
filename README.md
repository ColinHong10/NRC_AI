# 洛克王国战斗 AI 模拟器

基于蒙特卡洛树搜索（MCTS）的洛克王国自动对战模拟系统，支持 AI 自战、玩家对战、Web 图形界面。

---

## 快速开始

```bash
pip install fastapi uvicorn[standard] openpyxl pandas beautifulsoup4 requests

# Web 界面（推荐）
python run_web.py
# 访问 http://localhost:8765/team （阵容编辑）
# 访问 http://localhost:8765/battle（战斗界面）

# 终端版本
python start.py
```

---

## 项目结构

```
NRC_AI/
├── src/                            # 核心源码
│   ├── models.py                   # Pokemon / Skill / BattleState 数据模型
│   ├── effect_models.py            # E 枚举（效果原语）/ Timing / SkillTiming
│   ├── effect_data.py              # 手工技能效果(59) + 特性效果配置(68)
│   ├── effect_engine.py            # 效果执行引擎（Handler 注册表）
│   ├── skill_effects_generated.py  # 自动生成技能效果(455)
│   ├── battle.py                   # 战斗逻辑 + 印记 / 回合流程
│   ├── skill_db.py                 # 技能数据库加载
│   ├── pokemon_db.py               # 精灵数据库加载
│   ├── mcts.py                     # 对抗式 MCTS AI
│   ├── server.py                   # FastAPI + WebSocket 服务端
│   └── main.py                     # 终端主菜单入口
│
├── web/                            # 前端
│   ├── battle.html                 # 战斗界面
│   ├── team.html                   # 阵容编辑器
│   └── index.html                  # 入口重定向
│
├── tests/                          # 测试（14 文件，107 用例）
├── data/nrc.db                     # SQLite 数据库（461 精灵 × 495 技能）
├── scripts/                        # 工具脚本（爬虫 / 生成器 / 审计）
├── docs/                           # 参考文档
│   ├── COVERAGE_MATRIX.md          # 特性覆盖矩阵
│   └── SKILLS_ABILITIES_CONFIG_GUIDE.md  # 配置开发手册
│
├── ROADMAP.md                      # 项目路线图与进度
└── requirements.txt
```

---

## 数据规模

| 数据 | 数量 | 来源 |
|------|------|------|
| 精灵 | 461 | BiliGame Wiki + nrc.db |
| 技能 | 495（472 有效果配置） | DB + 手工/自动配置 |
| 特性 | 170（68 已配置） | DB + effect_data.py |
| 印记 | 12 种 | 完整实现 |
| 学习关系 | 21,331 | 精灵 × 技能关联 |

---

## 主要功能

- **Web 图形界面**：阵容编辑 + 实时战斗动画 + WebSocket 通信
- **AI 自战**：双方 MCTS 驱动，每回合 150 次模拟
- **玩家 vs AI**：Web 或终端手动控制
- **效果引擎**：100+ 种效果原语，数据驱动，零硬编码
- **印记系统**：12 种场地印记，不随换人消失
- **批量模拟**：统计胜率、平均回合数

---

## 当前进度

详见 [ROADMAP.md](ROADMAP.md)。

核心优先级：
1. **技能 / 特性效果配置**（102 个特性待补、42 个空技能待修）
2. **前端战斗画面升级**（Tooltip / 印记显示 / 键盘快捷键 / 统计面板）
3. **伤害公式校准**（需游戏内真实数据对照）

"""
精灵数据库 - 从 SQLite 加载精灵属性和六维种族值
战斗五维根据用户配置的个体值和性格实时计算
"""
import os
import math
import sqlite3
from typing import Optional, List, Dict, Tuple

_conn: Optional[sqlite3.Connection] = None
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "nrc.db")

# 全库速度种族值中位线 (从 DB 中动态计算后缓存)
_speed_median: Optional[float] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        if not os.path.exists(_DB_PATH):
            raise FileNotFoundError(f"Database not found: {_DB_PATH}\nRun: python3 scripts/init_db.py")
        _conn = sqlite3.connect(_DB_PATH)
        _conn.row_factory = sqlite3.Row
    return _conn


def _get_speed_median() -> float:
    """获取全库速度种族值中位线"""
    global _speed_median
    if _speed_median is not None:
        return _speed_median
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT base_speed FROM pokemon ORDER BY base_speed")
    speeds = [r[0] for r in c.fetchall()]
    n = len(speeds)
    if n == 0:
        _speed_median = 80.0
    elif n % 2 == 1:
        _speed_median = float(speeds[n // 2])
    else:
        _speed_median = (speeds[n // 2 - 1] + speeds[n // 2]) / 2.0
    return _speed_median


# ────────────────────────────────────────────────────────────
#  PvP 战斗五维计算
# ────────────────────────────────────────────────────────────
#
# 公式:
#   HP    = [1.7 × base_hp    + 0.85 × IV + 70] × (1 + mod) + 100
#   其他  = [1.1 × base_stat  + 0.55 × IV + 10] × (1 + mod) + 50
#
# 个体值 (IV): 用户配置，6 项属性中选择 3 项为 60，其余 3 项为 0
# 性格修正：从 pokemon_nature_table.py 获取，25 种性格之一
# ────────────────────────────────────────────────────────────

def calc_combat_stats(
    base_hp: int, base_atk: int, base_spatk: int,
    base_def: int, base_spdef: int, base_speed: int,
    iv_config: Optional[Dict[str, int]] = None,
    nature_name: str = "坦率",
) -> Dict[str, float]:
    """
    计算 PvP 战斗五维。

    参数:
      base_*: 种族值
      iv_config: 个体值配置 {"hp":60,"atk":60,"spatk":0,"def":0,"spdef":0,"speed":60}
                 默认全 0（用户未配置时）
      nature_name: 性格名称（25 种性格之一），默认"坦率"（无修正）

    返回:
      {"hp":..., "atk":..., "spatk":..., "def":..., "spdef":..., "speed":...}
    """
    from src.pokemon_nature_table import get_nature_bonus

    bases = {
        "hp": base_hp, "atk": base_atk, "spatk": base_spatk,
        "def": base_def, "spdef": base_spdef, "speed": base_speed,
    }

    # 个体值配置：用户未传入时使用默认全 0
    if iv_config is None:
        iv_config = {"hp": 0, "atk": 0, "spatk": 0, "def": 0, "spdef": 0, "speed": 0}

    # 从性格表获取加成
    try:
        nature_bonus = get_nature_bonus(nature_name)
    except KeyError:
        # 未知性格时使用坦率（无修正）
        nature_bonus = {"atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0}

    # 性格加成字段名映射：pokemon_nature_table.py → calc_combat_stats
    # atk → atk, defense → def, sp_atk → spatk, sp_defense → spdef, speed → speed
    nature_config = {
        "hp": 0.0,
        "atk": nature_bonus.get("atk", 0.0),
        "spatk": nature_bonus.get("sp_atk", 0.0),
        "def": nature_bonus.get("defense", 0.0),
        "spdef": nature_bonus.get("sp_defense", 0.0),
        "speed": nature_bonus.get("speed", 0.0),
    }

    # ── 计算最终战斗五维 ──
    result = {}
    for stat in ["hp", "atk", "spatk", "def", "spdef", "speed"]:
        b = bases[stat]
        iv = iv_config.get(stat, 0)
        mod = nature_config.get(stat, 0.0)
        if stat == "hp":
            raw = 1.7 * b + 0.85 * iv + 70
            result[stat] = round(raw * (1.0 + mod) + 100)
        else:
            raw = 1.1 * b + 0.55 * iv + 10
            result[stat] = round(raw * (1.0 + mod) + 50)
    return result


def _auto_iv(bases: Dict[str, int]) -> Dict[str, int]:
    """
    默认 IV 分配策略 (完美资质 IV=60):
    - 输出手 (物攻>魔攻 → 物攻手，反之魔攻手):
        HP + 主攻 (atk 或 spatk) + speed 各给 60
    - 物攻=魔攻：HP + atk + speed

    已弃用：仅用于向后兼容
    """
    iv = {"hp": 0, "atk": 0, "spatk": 0, "def": 0, "spdef": 0, "speed": 0}
    iv["hp"] = 60
    iv["speed"] = 60
    if bases["atk"] >= bases["spatk"]:
        iv["atk"] = 60
    else:
        iv["spatk"] = 60
    return iv


def _auto_nature(bases: Dict[str, int]) -> Dict[str, float]:
    """
    默认性格修正策略:
    - +20%: 速度种族值 ≥ 中位线 → speed; 否则给主攻
    - -10%: 物攻/魔攻中较小者
    - 物攻=魔攻时不扣减任何一项 (两项都不减)

    已弃用：仅用于向后兼容
    """
    nature = {"hp": 0.0, "atk": 0.0, "spatk": 0.0, "def": 0.0, "spdef": 0.0, "speed": 0.0}
    median = _get_speed_median()

    # +20% 分配
    if bases["speed"] >= median:
        nature["speed"] = 0.20
    else:
        # 速度低于中位线 → 给主攻 +20%
        if bases["atk"] >= bases["spatk"]:
            nature["atk"] = 0.20
        else:
            nature["spatk"] = 0.20

    # -10% 分配：物攻/魔攻较小者
    if bases["atk"] < bases["spatk"]:
        nature["atk"] = -0.10
    elif bases["spatk"] < bases["atk"]:
        nature["spatk"] = -0.10
    # 物攻=魔攻：不减

    return nature


def load_pokemon_db(filepath=None):
    """兼容旧接口 — 现在只需确认 DB 可连接"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pokemon")
    count = c.fetchone()[0]
    print(f"[OK] 精灵数据库已加载：{count} 只精灵 (战斗五维由公式实时计算)")


def get_pokemon(name: str) -> Optional[Dict]:
    """
    根据名称获取精灵数据。
    支持模糊匹配：精确 > 前缀 > 包含。
    返回 dict 兼容旧接口，只包含种族值，战斗五维需调用 calc_combat_stats 计算。
    """
    conn = _get_conn()
    c = conn.cursor()

    # 精确匹配
    c.execute("SELECT * FROM pokemon WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        return _row_to_dict(row)

    # 前缀匹配（"千棘盔" -> "千棘盔（本来的样子）"）
    c.execute("SELECT * FROM pokemon WHERE name LIKE ? ORDER BY evo_stage DESC LIMIT 1",
              (f"{name}%",))
    row = c.fetchone()
    if row:
        return _row_to_dict(row)

    # 基础名匹配（去掉括号部分）
    base = name.split("（")[0].split("(")[0]
    if base != name:
        c.execute("SELECT * FROM pokemon WHERE name LIKE ? ORDER BY evo_stage DESC LIMIT 1",
                  (f"{base}%",))
        row = c.fetchone()
        if row:
            return _row_to_dict(row)

    # 包含匹配
    c.execute("SELECT * FROM pokemon WHERE name LIKE ? ORDER BY evo_stage DESC LIMIT 1",
              (f"%{name}%",))
    row = c.fetchone()
    if row:
        return _row_to_dict(row)

    return None


def search_pokemon(keyword: str) -> List[Dict]:
    """搜索精灵"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pokemon WHERE name LIKE ? OR ability LIKE ? LIMIT 20",
              (f"%{keyword}%", f"%{keyword}%"))
    return [_row_to_dict(r) for r in c.fetchall()]


def get_prev_evolution(name: str) -> Optional[str]:
    """
    萌化查询：返回精灵的进化链上一阶段的名称。
    若该精灵已是起始形态（无前置进化），返回 None。

    例：裘卡 → 裘力，裘力 → 裘洛，裘洛 → None
    """
    conn = _get_conn()
    c = conn.cursor()
    row = c.execute(
        "SELECT from_name FROM evolution WHERE to_name = ? LIMIT 1",
        (name,)
    ).fetchone()
    return row[0] if row else None


def get_evolution_chain(name: str) -> List[str]:
    """
    返回精灵所在完整进化链（从起始形态到最终形态的列表）。
    例：裘卡 → ['裘洛', '裘力', '裘卡']
    若没有进化链数据，返回 [name]。
    """
    conn = _get_conn()
    c = conn.cursor()

    # 向上找起始形态
    chain = [name]
    current = name
    visited = {name}
    while True:
        row = c.execute(
            "SELECT from_name FROM evolution WHERE to_name = ? LIMIT 1",
            (current,)
        ).fetchone()
        if not row or row[0] in visited:
            break
        current = row[0]
        visited.add(current)
        chain.insert(0, current)

    # 从起始形态向下
    current = chain[-1]
    while True:
        row = c.execute(
            "SELECT to_name FROM evolution WHERE from_name = ? LIMIT 1",
            (current,)
        ).fetchone()
        if not row or row[0] in visited:
            break
        current = row[0]
        visited.add(current)
        chain.append(current)

    return chain


def get_pokemon_skills(name: str) -> List[Dict]:
    """获取精灵可学习的所有技能"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT s.* FROM skill s
        JOIN pokemon_skill ps ON ps.skill_id = s.id
        JOIN pokemon p ON ps.pokemon_id = p.id
        WHERE p.name LIKE ?
    """, (f"{name}%",))
    return [dict(r) for r in c.fetchall()]


def _row_to_dict(row) -> Dict:
    """将 sqlite3.Row 转为兼容旧接口的 dict，只返回种族值"""
    # 只返回种族值，不计算战斗值
    return {
        "编号": row["id"],
        "名称": row["name"],
        "属性": row["element"],
        "进化阶段": row["evo_stage"],
        "特性": row["ability"],
        "生命种族值": row["base_hp"],
        "物攻种族值": row["base_atk"],
        "魔攻种族值": row["base_spatk"],
        "物防种族值": row["base_def"],
        "魔防种族值": row["base_spdef"],
        "速度种族值": row["base_speed"],
    }

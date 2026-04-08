"""
精灵数据库 - 从 SQLite 加载精灵属性和六维数据
包含 PvP 战斗五维计算（正确公式 + 个体值分配 + 性格修正）
"""
import os
import math
import sqlite3
from typing import Optional, List, Dict, Tuple

_conn: Optional[sqlite3.Connection] = None
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "nrc.db")

# 全库速度种族值中位线 (从DB中动态计算后缓存)
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
# 个体值 (IV): 6的倍数, 范围 48~60, 默认完美=60
#   - 共6项, 其中3项有IV, 3项IV=0
#   - 默认分配策略: 按精灵定位选最重要的3项
#
# 性格修正 (mod): 五维 (ATK/SPATK/DEF/SPDEF/SPD) 中
#   - 1项 +20%, 1项 -10%, 其余 0%
#   - HP 也可以获得性格修正 (玩家自选)
#   - 默认: 速度种族值 ≥ 中位线 → SPD +20%
#           物攻/魔攻 较小者 → -10%
# ────────────────────────────────────────────────────────────

def calc_combat_stats(
    base_hp: int, base_atk: int, base_spatk: int,
    base_def: int, base_spdef: int, base_speed: int,
    iv_config: Optional[Dict[str, int]] = None,
    nature_config: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    计算 PvP 战斗五维。

    参数:
      base_*: 种族值
      iv_config: 个体值配置 {"hp":60,"atk":0,...}, 默认自动分配
      nature_config: 性格修正 {"hp":0,"atk":-0.1,...}, 默认自动分配

    返回:
      {"hp":..., "atk":..., "spatk":..., "def":..., "spdef":..., "speed":...}
    """
    bases = {
        "hp": base_hp, "atk": base_atk, "spatk": base_spatk,
        "def": base_def, "spdef": base_spdef, "speed": base_speed,
    }

    # ── 自动分配个体值 (IV) ──
    if iv_config is None:
        iv_config = _auto_iv(bases)

    # ── 自动分配性格修正 ──
    if nature_config is None:
        nature_config = _auto_nature(bases)

    # ── 计算最终战斗五维 ──
    result = {}
    for stat in ["hp", "atk", "spatk", "def", "spdef", "speed"]:
        b = bases[stat]
        iv = iv_config.get(stat, 0)
        mod = nature_config.get(stat, 0.0)
        if stat == "hp":
            raw = 1.7 * b + 0.85 * iv + 70
            result[stat] = raw * (1.0 + mod) + 100
        else:
            raw = 1.1 * b + 0.55 * iv + 10
            result[stat] = raw * (1.0 + mod) + 50
    return result


def _auto_iv(bases: Dict[str, int]) -> Dict[str, int]:
    """
    默认 IV 分配策略 (完美资质 IV=60):
    - 输出手(物攻>魔攻 → 物攻手, 反之魔攻手):
        HP + 主攻(atk或spatk) + speed 各给60
    - 物攻=魔攻: HP + atk + speed
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
    - 物攻=魔攻时不扣减任何一项(两项都不减)
    """
    nature = {"hp": 0.0, "atk": 0.0, "spatk": 0.0, "def": 0.0, "spdef": 0.0, "speed": 0.0}
    median = _get_speed_median()

    # +20% 分配
    if bases["speed"] >= median:
        nature["speed"] = 0.20
    else:
        # 速度低于中位线 → 给主攻+20%
        if bases["atk"] >= bases["spatk"]:
            nature["atk"] = 0.20
        else:
            nature["spatk"] = 0.20

    # -10% 分配: 物攻/魔攻较小者
    if bases["atk"] < bases["spatk"]:
        nature["atk"] = -0.10
    elif bases["spatk"] < bases["atk"]:
        nature["spatk"] = -0.10
    # 物攻=魔攻: 不减

    return nature


def load_pokemon_db(filepath=None):
    """兼容旧接口 — 现在只需确认 DB 可连接"""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pokemon")
    count = c.fetchone()[0]
    print(f"[OK] 精灵数据库已加载: {count} 只精灵 (战斗五维由公式实时计算)")


def get_pokemon(name: str) -> Optional[Dict]:
    """
    根据名称获取精灵数据。
    支持模糊匹配：精确 > 前缀 > 包含。
    返回 dict 兼容旧接口, 战斗五维由公式计算。
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
    """将 sqlite3.Row 转为兼容旧接口的 dict, 战斗五维由公式实时计算"""
    # 用公式计算战斗五维
    stats = calc_combat_stats(
        base_hp=row["base_hp"], base_atk=row["base_atk"],
        base_spatk=row["base_spatk"], base_def=row["base_def"],
        base_spdef=row["base_spdef"], base_speed=row["base_speed"],
    )
    return {
        "编号": row["id"],
        "名称": row["name"],
        "属性": row["element"],
        "进化阶段": row["evo_stage"],
        "特性": row["ability"],
        "生命值": stats["hp"],
        "物攻": stats["atk"],
        "魔攻": stats["spatk"],
        "物防": stats["def"],
        "魔防": stats["spdef"],
        "速度": stats["speed"],
        "生命种族值": row["base_hp"],
        "物攻种族值": row["base_atk"],
        "魔攻种族值": row["base_spatk"],
        "物防种族值": row["base_def"],
        "魔防种族值": row["base_spdef"],
        "速度种族值": row["base_speed"],
    }

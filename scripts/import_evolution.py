"""
导入 spirit_evolution.csv 到 nrc.db 的 evolution 表。

表结构：
  evolution(
    id          INTEGER PRIMARY KEY,
    from_name   TEXT NOT NULL,   -- 前置形态精灵名
    to_name     TEXT NOT NULL,   -- 进化后精灵名
    evo_level   INTEGER,         -- 进化等级（NULL=无等级限制）
    condition   TEXT,            -- 特殊进化条件（NULL=无）
    chain_text  TEXT,            -- 原始进化链描述（调试用）
    UNIQUE(from_name, to_name)
  )

同时在 pokemon 表新增 spirit_no 列（如 NO.001），方便后续按编号查精灵。
"""

import csv
import sqlite3
import re
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'spirit_evolution.csv')
DB_PATH  = os.path.join(os.path.dirname(__file__), '..', 'data', 'nrc.db')


def clean_name(raw: str) -> str:
    """去掉括号内的形态说明，只保留精灵名。"""
    return re.sub(r'（[^）]*）', '', raw).strip()


def parse_chain(chain_text: str):
    """
    解析进化链文本，返回 [(from_name, to_name), ...] 列表。
    例：'喵喵 → 喵呜 → 魔力猫' → [('喵喵','喵呜'), ('喵呜','魔力猫')]
    """
    if not chain_text or not chain_text.strip():
        return []
    parts = [clean_name(p) for p in chain_text.split('→')]
    parts = [p for p in parts if p]  # 过滤空串
    pairs = []
    for i in range(len(parts) - 1):
        pairs.append((parts[i], parts[i + 1]))
    return pairs


def parse_evo_levels(level_str: str):
    """
    '16,32' → [16, 32]，取对应位置的等级。
    """
    if not level_str or not level_str.strip():
        return []
    try:
        return [int(x.strip()) for x in level_str.split(',') if x.strip()]
    except ValueError:
        return []


def main():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # 1. 建 evolution 表（幂等）
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS evolution (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_name   TEXT NOT NULL,
            to_name     TEXT NOT NULL,
            evo_level   INTEGER,
            condition   TEXT,
            chain_text  TEXT,
            UNIQUE(from_name, to_name)
        );
    """)

    # 2. 给 pokemon 表添加 spirit_no 列（如果没有）
    existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(pokemon)")}
    if 'spirit_no' not in existing_cols:
        cur.execute("ALTER TABLE pokemon ADD COLUMN spirit_no TEXT DEFAULT ''")
        print("已添加 pokemon.spirit_no 列")

    conn.commit()

    # 3. 读取 CSV，去重后解析
    # 用 (spirit_no, 名字, 形态分类) 作为去重 key，避免重复行干扰
    seen_rows = set()
    # 保存每条进化对的 level/condition，key=(from_name, to_name)
    edge_info = {}   # (from, to) -> (level, condition, chain_text)

    with open(CSV_PATH, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spirit_no    = row['编号'].strip()
            name         = row['名字'].strip()
            form_type    = row['形态分类'].strip()   # 原始形态 / 地区形态 / 首领形态
            chain_text   = row['进化链'].strip()
            level_str    = row['进化等级'].strip()
            condition    = row['进化条件'].strip() or None

            dedup_key = (spirit_no, name, form_type)
            if dedup_key in seen_rows:
                continue
            seen_rows.add(dedup_key)

            # 只处理原始形态的进化链（地区/首领形态不参与萌化还原）
            if form_type != '原始形态':
                continue

            pairs = parse_chain(chain_text)
            if not pairs:
                continue

            levels = parse_evo_levels(level_str)

            for idx, (from_n, to_n) in enumerate(pairs):
                lvl = levels[idx] if idx < len(levels) else None
                key = (from_n, to_n)
                if key not in edge_info:
                    edge_info[key] = (lvl, condition, chain_text)
                # 如果已存在但 level 为 None，尝试填入
                elif edge_info[key][0] is None and lvl is not None:
                    edge_info[key] = (lvl, condition, chain_text)

    # 4. 写入 evolution 表
    inserted = 0
    skipped  = 0
    for (from_n, to_n), (lvl, cond, chain) in edge_info.items():
        try:
            cur.execute(
                "INSERT OR IGNORE INTO evolution(from_name, to_name, evo_level, condition, chain_text) "
                "VALUES (?, ?, ?, ?, ?)",
                (from_n, to_n, lvl, cond, chain)
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  插入失败 {from_n}→{to_n}: {e}")

    conn.commit()
    print(f"evolution 表：新增 {inserted} 条进化关系，跳过重复 {skipped} 条")

    # 5. 更新 pokemon.spirit_no（按名字匹配）
    name_to_no = {}
    with open(CSV_PATH, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = row['名字'].strip()
            no = row['编号'].strip()
            if n not in name_to_no:
                name_to_no[n] = no

    updated = 0
    for name, no in name_to_no.items():
        cur.execute(
            "UPDATE pokemon SET spirit_no=? WHERE name=? AND (spirit_no IS NULL OR spirit_no='')",
            (no, name)
        )
        updated += cur.rowcount

    conn.commit()
    print(f"pokemon 表：更新 spirit_no {updated} 条")

    # 6. 验证：打印几条样本
    print("\n=== evolution 表样本（前10条）===")
    for row in cur.execute("SELECT from_name, to_name, evo_level, condition FROM evolution LIMIT 10"):
        print(f"  {row[0]} → {row[1]}  (lv{row[2]}, cond={row[3]})")

    print("\n=== 萌化查询示例：裘卡的前置形态 ===")
    result = cur.execute(
        "SELECT from_name, evo_level FROM evolution WHERE to_name=?", ('裘卡',)
    ).fetchone()
    if result:
        print(f"  裘卡 的上一阶段: {result[0]}  (lv{result[1]})")
    else:
        print("  未找到")

    print("\n=== 萌化查询示例：千棘盔的进化链 ===")
    for row in cur.execute(
        "SELECT from_name, to_name, evo_level FROM evolution WHERE chain_text LIKE '%千棘盔%'"
    ):
        print(f"  {row[0]} → {row[1]}  (lv{row[2]})")

    conn.close()
    print("\n完成！")


if __name__ == '__main__':
    main()

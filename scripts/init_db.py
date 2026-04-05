"""
NRC_AI 数据库初始化脚本
将 pokemon_stats.xlsx + skills_wiki.csv + skills_all.csv 导入 SQLite

用法: python3 scripts/init_db.py
输出: data/nrc.db
"""
import os
import sys
import csv
import sqlite3
import openpyxl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "nrc.db")

POKEMON_XLSX = os.path.join(BASE_DIR, "data", "pokemon_stats.xlsx")
SKILLS_WIKI_CSV = os.path.join(BASE_DIR, "data", "skills_wiki.csv")
SKILLS_ALL_CSV = os.path.join(BASE_DIR, "data", "skills_all.csv")


def create_tables(conn):
    c = conn.cursor()

    # ── 精灵表 ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS pokemon (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        element     TEXT NOT NULL DEFAULT '普通',
        evo_stage   TEXT DEFAULT '',
        ability     TEXT DEFAULT '',
        base_hp     INTEGER DEFAULT 0,
        base_atk    INTEGER DEFAULT 0,
        base_spatk  INTEGER DEFAULT 0,
        base_def    INTEGER DEFAULT 0,
        base_spdef  INTEGER DEFAULT 0,
        base_speed  INTEGER DEFAULT 0,
        base_total  INTEGER DEFAULT 0,
        stat_hp     INTEGER DEFAULT 0,
        stat_atk    INTEGER DEFAULT 0,
        stat_spatk  INTEGER DEFAULT 0,
        stat_def    INTEGER DEFAULT 0,
        stat_spdef  INTEGER DEFAULT 0,
        stat_speed  INTEGER DEFAULT 0
    )
    """)

    # ── 技能表 ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS skill (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        element     TEXT NOT NULL DEFAULT '普通',
        category    TEXT NOT NULL DEFAULT '状态',
        energy_cost INTEGER DEFAULT 0,
        power       INTEGER DEFAULT 0,
        description TEXT DEFAULT '',
        source      TEXT DEFAULT 'wiki'
    )
    """)

    # ── 精灵-技能关联表 ──
    c.execute("""
    CREATE TABLE IF NOT EXISTS pokemon_skill (
        pokemon_id  INTEGER NOT NULL,
        skill_id    INTEGER NOT NULL,
        PRIMARY KEY (pokemon_id, skill_id),
        FOREIGN KEY (pokemon_id) REFERENCES pokemon(id),
        FOREIGN KEY (skill_id)   REFERENCES skill(id)
    )
    """)

    # ── 索引 ──
    c.execute("CREATE INDEX IF NOT EXISTS idx_pokemon_name ON pokemon(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skill(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pokemon_element ON pokemon(element)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_skill_element ON skill(element)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ps_pokemon ON pokemon_skill(pokemon_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ps_skill ON pokemon_skill(skill_id)")

    conn.commit()
    print("[OK] Tables created")


def import_pokemon(conn):
    """从 pokemon_stats.xlsx 导入精灵数据"""
    if not os.path.exists(POKEMON_XLSX):
        print(f"[SKIP] {POKEMON_XLSX} not found")
        return 0

    wb = openpyxl.load_workbook(POKEMON_XLSX, read_only=True)
    ws = wb["精灵总表"]
    c = conn.cursor()
    count = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 18:
            continue
        name = row[1]
        if not name:
            continue

        # 检查是否已存在同名（保留最终形态）
        c.execute("SELECT id, evo_stage FROM pokemon WHERE name = ?", (name,))
        existing = c.fetchone()
        evo_stage = str(row[3] or "")

        if existing:
            # 如果已有最终形态，跳过非最终
            if existing[1] == "最终形态" and evo_stage != "最终形态":
                continue
            # 否则更新
            c.execute("""
                UPDATE pokemon SET element=?, evo_stage=?, ability=?,
                    base_hp=?, base_atk=?, base_spatk=?, base_def=?, base_spdef=?, base_speed=?, base_total=?,
                    stat_hp=?, stat_atk=?, stat_spatk=?, stat_def=?, stat_spdef=?, stat_speed=?
                WHERE name=?
            """, (
                row[2] or "普通", evo_stage, row[4] or "",
                row[5] or 0, row[6] or 0, row[7] or 0, row[8] or 0, row[9] or 0, row[10] or 0, row[11] or 0,
                row[12] or 0, row[13] or 0, row[14] or 0, row[15] or 0, row[16] or 0, row[17] or 0,
                name
            ))
        else:
            c.execute("""
                INSERT INTO pokemon (name, element, evo_stage, ability,
                    base_hp, base_atk, base_spatk, base_def, base_spdef, base_speed, base_total,
                    stat_hp, stat_atk, stat_spatk, stat_def, stat_spdef, stat_speed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                name, row[2] or "普通", evo_stage, row[4] or "",
                row[5] or 0, row[6] or 0, row[7] or 0, row[8] or 0, row[9] or 0, row[10] or 0, row[11] or 0,
                row[12] or 0, row[13] or 0, row[14] or 0, row[15] or 0, row[16] or 0, row[17] or 0,
            ))
            count += 1

    wb.close()
    conn.commit()
    print(f"[OK] Imported {count} pokemon from xlsx")
    return count


def import_skills(conn):
    """从 skills_wiki.csv 导入技能（优先 wiki 数据）"""
    if not os.path.exists(SKILLS_WIKI_CSV):
        print(f"[SKIP] {SKILLS_WIKI_CSV} not found")
        return 0

    c = conn.cursor()
    count = 0
    pet_links = []  # [(skill_name, pet_name), ...]

    with open(SKILLS_WIKI_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["技能名"].strip()
            if not name:
                continue

            element = row.get("属性", "普通").strip()
            category = row.get("分类", "状态").strip()
            energy = 0
            power = 0
            try:
                energy = int(row.get("耗能", "0").strip())
            except ValueError:
                pass
            try:
                power = int(row.get("威力", "0").strip())
            except ValueError:
                pass
            desc = row.get("技能描述", "").strip()

            c.execute("SELECT id FROM skill WHERE name = ?", (name,))
            existing = c.fetchone()
            if existing:
                c.execute("""
                    UPDATE skill SET element=?, category=?, energy_cost=?, power=?, description=?, source='wiki'
                    WHERE name=?
                """, (element, category, energy, power, desc, name))
            else:
                c.execute("""
                    INSERT INTO skill (name, element, category, energy_cost, power, description, source)
                    VALUES (?,?,?,?,?,?,'wiki')
                """, (name, element, category, energy, power, desc))
                count += 1

            # Parse pet list
            pets_str = row.get("可学习精灵", "").strip()
            if pets_str:
                for pet_name in pets_str.split("|"):
                    pet_name = pet_name.strip()
                    if pet_name and len(pet_name) < 30:
                        pet_links.append((name, pet_name))

    conn.commit()
    print(f"[OK] Imported {count} skills from wiki csv")

    # Supplement from skills_all.csv (only skills not in wiki)
    extra = 0
    if os.path.exists(SKILLS_ALL_CSV):
        with open(SKILLS_ALL_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("技能名", "").strip()
                if not name:
                    continue
                c.execute("SELECT id FROM skill WHERE name = ?", (name,))
                if c.fetchone():
                    continue  # Already from wiki

                element = row.get("属性", "普通").strip()
                category = row.get("类型", "状态").strip()
                energy = 0
                power = 0
                try:
                    energy = int(row.get("耗能", "0").strip())
                except ValueError:
                    pass
                try:
                    power = int(row.get("威力", "0").strip())
                except ValueError:
                    pass
                desc = row.get("效果描述", "").strip()

                c.execute("""
                    INSERT INTO skill (name, element, category, energy_cost, power, description, source)
                    VALUES (?,?,?,?,?,?,'manual')
                """, (name, element, category, energy, power, desc))
                extra += 1

        conn.commit()
        print(f"[OK] Imported {extra} extra skills from skills_all.csv")

    # Build pokemon_skill relations
    link_count = 0
    for skill_name, pet_name in pet_links:
        c.execute("SELECT id FROM skill WHERE name = ?", (skill_name,))
        skill_row = c.fetchone()
        if not skill_row:
            continue
        skill_id = skill_row[0]

        c.execute("SELECT id FROM pokemon WHERE name = ?", (pet_name,))
        pet_row = c.fetchone()
        if not pet_row:
            # Try fuzzy match: base name without parentheses
            base = pet_name.split("（")[0]
            c.execute("SELECT id FROM pokemon WHERE name LIKE ?", (f"{base}%",))
            pet_row = c.fetchone()
        if not pet_row:
            continue
        pet_id = pet_row[0]

        try:
            c.execute("INSERT OR IGNORE INTO pokemon_skill (pokemon_id, skill_id) VALUES (?,?)",
                       (pet_id, skill_id))
            link_count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    print(f"[OK] Created {link_count} pokemon-skill links")
    return count + extra


def recalc_combat_stats(conn):
    """用正确的PvP公式重算所有精灵的战斗五维并写回DB"""
    import sys
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from pokemon_db import calc_combat_stats

    c = conn.cursor()
    c.execute("SELECT id, base_hp, base_atk, base_spatk, base_def, base_spdef, base_speed FROM pokemon")
    rows = c.fetchall()
    count = 0
    for r in rows:
        pid = r[0]
        stats = calc_combat_stats(
            base_hp=r[1], base_atk=r[2], base_spatk=r[3],
            base_def=r[4], base_spdef=r[5], base_speed=r[6],
        )
        c.execute("""
            UPDATE pokemon SET
                stat_hp=?, stat_atk=?, stat_spatk=?,
                stat_def=?, stat_spdef=?, stat_speed=?
            WHERE id=?
        """, (
            round(stats["hp"], 1), round(stats["atk"], 1),
            round(stats["spatk"], 1), round(stats["def"], 1),
            round(stats["spdef"], 1), round(stats["speed"], 1),
            pid,
        ))
        count += 1
    conn.commit()
    print(f"[OK] Recalculated combat stats for {count} pokemon (new PvP formula)")


def print_stats(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pokemon")
    pokemon_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM skill")
    skill_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM pokemon_skill")
    link_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT pokemon_id) FROM pokemon_skill")
    linked_pokemon = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT skill_id) FROM pokemon_skill")
    linked_skills = c.fetchone()[0]

    print(f"\n{'='*40}")
    print(f"  Database: {DB_PATH}")
    print(f"  Pokemon:  {pokemon_count}")
    print(f"  Skills:   {skill_count}")
    print(f"  Links:    {link_count} ({linked_pokemon} pokemon × {linked_skills} skills)")
    print(f"{'='*40}")

    # Sample queries
    print("\n  Sample: 千棘盔 的技能:")
    c.execute("""
        SELECT s.name, s.element, s.category, s.power, s.energy_cost, substr(s.description, 1, 40)
        FROM skill s
        JOIN pokemon_skill ps ON ps.skill_id = s.id
        JOIN pokemon p ON ps.pokemon_id = p.id
        WHERE p.name = '千棘盔'
    """)
    for row in c.fetchall():
        print(f"    {row[0]} [{row[1]}/{row[2]}] P={row[3]} E={row[4]} | {row[5]}")

    print("\n  Sample: 能学 '毒雾' 的精灵:")
    c.execute("""
        SELECT p.name, p.element, p.stat_hp, p.stat_atk, p.stat_speed
        FROM pokemon p
        JOIN pokemon_skill ps ON ps.pokemon_id = p.id
        JOIN skill s ON ps.skill_id = s.id
        WHERE s.name = '毒雾'
        LIMIT 10
    """)
    for row in c.fetchall():
        print(f"    {row[0]} [{row[1]}] HP={row[2]} ATK={row[3]} SPD={row[4]}")


def main():
    # Delete old DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[OK] Removed old {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    create_tables(conn)
    import_pokemon(conn)
    import_skills(conn)
    recalc_combat_stats(conn)
    print_stats(conn)

    conn.close()
    print(f"\n[DONE] Database saved to {DB_PATH}")


if __name__ == "__main__":
    main()

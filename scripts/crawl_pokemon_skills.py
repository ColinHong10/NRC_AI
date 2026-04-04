"""
scripts/crawl_pokemon_skills.py

从 wiki.biligame.com/rocom 爬取每只精灵的完整技能列表，
更新 SQLite 数据库中的 pokemon_skill 关联表。

用法:
    python3 scripts/crawl_pokemon_skills.py [--test 圣羽翼王] [--limit N]
"""

import sys, os, time, json, sqlite3, re, argparse
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

# ── 配置 ──
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "nrc.db")
BASE_URL = "https://wiki.biligame.com/rocom/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://wiki.biligame.com/rocom/",
}
DELAY = 0.8   # 请求间隔秒数，避免被封

# ── 数据库连接 ──
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_pokemon(conn):
    """从DB获取所有精灵的 id 和 name"""
    c = conn.cursor()
    c.execute("SELECT id, name FROM pokemon ORDER BY id")
    return [(r["id"], r["name"]) for r in c.fetchall()]


def get_skill_id(conn, name: str):
    """根据技能名查找技能ID，不存在返回None"""
    c = conn.cursor()
    c.execute("SELECT id FROM skill WHERE name = ?", (name,))
    r = c.fetchone()
    return r["id"] if r else None


def insert_skill(conn, name: str, element: str = "普通", category: str = "状态",
                 energy_cost: int = 0, power: int = 0, description: str = "") -> int:
    """新增技能，返回新技能ID"""
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO skill (name, element, category, energy_cost, power, description, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'wiki_crawl')",
        (name, element, category, energy_cost, power, description)
    )
    conn.commit()
    c.execute("SELECT id FROM skill WHERE name = ?", (name,))
    r = c.fetchone()
    return r["id"] if r else None


def get_existing_skills_for_pokemon(conn, pokemon_id: int):
    """获取某精灵已有的技能ID集合"""
    c = conn.cursor()
    c.execute("SELECT skill_id FROM pokemon_skill WHERE pokemon_id = ?", (pokemon_id,))
    return {r["skill_id"] for r in c.fetchall()}


def upsert_pokemon_skill(conn, pokemon_id: int, skill_id: int):
    """插入精灵-技能关联（已存在则忽略）"""
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO pokemon_skill (pokemon_id, skill_id) VALUES (?, ?)",
        (pokemon_id, skill_id)
    )


# ── 爬取单只精灵的技能 ──
def crawl_pokemon_skills(name: str, session: requests.Session) -> dict:
    """
    返回 {
        "精灵技能": [...],
        "血脉技能": [...],
        "可学技能石": [...],
    }
    每个列表元素是技能名字符串。
    """
    encoded_name = quote(name, safe='')
    url = BASE_URL + encoded_name
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return {}
        r.encoding = 'utf-8'
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return {}

    soup = BeautifulSoup(r.text, 'lxml')
    result = {}

    # 找技能 tabBox
    tabbox = soup.find('div', class_='rocom_sprite_skill_tabBox')
    if not tabbox:
        # 有些精灵没有技能页面（非战斗精灵）
        return {}

    tabs = tabbox.find_all('div', class_='tabbertab')
    for tab in tabs:
        title = tab.get('title', '').strip()
        if not title:
            continue
        skill_divs = tab.find_all('div', class_='rocom_sprite_skillName')
        skills = list(dict.fromkeys(s.get_text(strip=True) for s in skill_divs))  # 去重保序
        if skills:
            result[title] = skills

    return result


# ── 主流程 ──
def main():
    parser = argparse.ArgumentParser(description="爬取 Wiki 精灵技能数据")
    parser.add_argument("--test", metavar="NAME", help="只测试一只精灵（如 '圣羽翼王'）")
    parser.add_argument("--limit", type=int, default=0, help="限制爬取数量（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入DB")
    parser.add_argument("--resume", metavar="FILE", help="从上次保存的进度文件继续")
    args = parser.parse_args()

    conn = get_conn()
    session = requests.Session()

    # ── 测试模式 ──
    if args.test:
        print(f"=== 测试爬取: {args.test} ===")
        result = crawl_pokemon_skills(args.test, session)
        total = sum(len(v) for v in result.values())
        print(f"共 {total} 个技能:")
        for tab_name, skills in result.items():
            print(f"  [{tab_name}]({len(skills)}个): {skills}")
        return

    # ── 全量爬取 ──
    all_pokemon = get_all_pokemon(conn)
    if args.limit > 0:
        all_pokemon = all_pokemon[:args.limit]

    total_pokemon = len(all_pokemon)
    print(f"共 {total_pokemon} 只精灵需要处理")

    # 进度存储
    progress_file = "data/crawl_progress.json"
    done_names = set()
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            done_names = set(json.load(f).get("done", []))
        print(f"恢复进度: 已完成 {len(done_names)} 只")

    stats = {
        "processed": 0, "skipped": 0, "errors": 0,
        "new_skills_added": 0, "new_relations_added": 0,
    }
    done_list = list(done_names)

    for i, (pid, pname) in enumerate(all_pokemon):
        if pname in done_names:
            continue

        print(f"[{i+1}/{total_pokemon}] {pname}...", end=" ", flush=True)

        skills_data = crawl_pokemon_skills(pname, session)
        if not skills_data:
            print("(无技能页面)")
            stats["skipped"] += 1
            done_list.append(pname)
            time.sleep(DELAY * 0.5)
            continue

        total_skills = sum(len(v) for v in skills_data.values())
        print(f"{total_skills}个技能", end=" ")

        if not args.dry_run:
            existing = get_existing_skills_for_pokemon(conn, pid)
            new_relations = 0
            for tab_name, skill_names in skills_data.items():
                for sk_name in skill_names:
                    sk_id = get_skill_id(conn, sk_name)
                    if sk_id is None:
                        # 技能不在DB里，跳过（不自动新增，避免引入脏数据）
                        continue
                    if sk_id not in existing:
                        upsert_pokemon_skill(conn, pid, sk_id)
                        new_relations += 1
                        existing.add(sk_id)
            conn.commit()
            if new_relations > 0:
                print(f"(+{new_relations}条关联)", end=" ")
                stats["new_relations_added"] += new_relations

        print()
        stats["processed"] += 1
        done_list.append(pname)

        # 定期保存进度
        if (i + 1) % 20 == 0:
            with open(progress_file, "w") as f:
                json.dump({"done": done_list}, f, ensure_ascii=False)
            print(f"  → 进度已保存 ({i+1}/{total_pokemon})")

        time.sleep(DELAY)

    # 最终保存进度
    with open(progress_file, "w") as f:
        json.dump({"done": done_list}, f, ensure_ascii=False)

    conn.close()
    print(f"\n=== 完成 ===")
    print(f"  处理: {stats['processed']} 只")
    print(f"  跳过: {stats['skipped']} 只")
    print(f"  新增关联: {stats['new_relations_added']} 条")


if __name__ == "__main__":
    main()

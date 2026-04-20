"""
scripts/scrape_skills_bilibili.py

从 wiki.biligame.com/rocom 批量抓取技能数据
参照 scrape_skills.py 的爬取方式，目标网站为 biligame 洛克王国手游 WIKI

输出 CSV: 技能名，属性，分类，耗能，威力，技能描述，可学习精灵列表

工作流程:
1. 从技能图鉴页面 (wiki.biligame.com/rocom/技能图鉴) 获取最新技能名称列表
2. 遍历每个技能名称，爬取对应的技能详情页
3. 解析属性、分类、耗能、威力、技能描述、可学习精灵
4. 保存到 CSV 文件和进度文件

页面结构解析:
- 属性：从 rocom_skill_template_skillAttribute 中的图片 alt 提取
- 分类：从 rocom_skill_template_skillSort 中的图片 alt 提取
- 耗能：从 rocom_skill_template_skillConsume_box 中的数字提取
- 威力：从 rocom_skill_template_skillPower 中的 <b> 标签提取
- 技能描述：从 rocom_skill_template_skillEffect 提取
- 可学习精灵：从 rocom_canlearn_img_box 中的 title 属性提取

用法:
    # 测试单个技能
    python3 scripts/scrape_skills_bilibili.py --test 冰锋横扫

    # 爬取全部技能
    python3 scripts/scrape_skills_bilibili.py

    # 限制爬取数量
    python3 scripts/scrape_skills_bilibili.py --limit 50

    # 从上次进度继续
    python3 scripts/scrape_skills_bilibili.py --resume

    # 干运行（不写入文件）
    python3 scripts/scrape_skills_bilibili.py --dry-run

输出文件:
    - data/skills_bilibili.csv: 爬取的技能数据
    - data/scrape_bilibili_progress.json: 爬取进度（用于断点续爬）

对比 scrape_skills.py:
    - scrape_skills.py: 爬取 rocoworldwiki.com，使用 browser 自动化
    - scrape_skills_bilibili.py: 爬取 wiki.biligame.com，使用 urllib 直接请求
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = ROOT / "data" / "skills_bilibili.csv"
PROGRESS_FILE = ROOT / "data" / "scrape_bilibili_progress.json"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://wiki.biligame.com/",
}

DELAY = 0.5  # 请求间隔秒数

# 技能图鉴页面 URL
SKILL_LIST_URL = "https://wiki.biligame.com/rocom/%E6%8A%80%E8%83%BD%E5%9B%BE%E9%89%B4"


def fetch_skill_list_from_wiki() -> List[str]:
    """从 wiki.biligame.com/rocom/技能图鉴 获取所有技能名称列表"""
    print("正在从技能图鉴页面获取技能列表...")

    html = fetch(SKILL_LIST_URL)
    if not html:
        print("[ERROR] 无法获取技能图鉴页面")
        return []

    # 提取所有技能链接的 title 属性
    # 格式：href="/rocom/技能名" title="技能名"
    skill_matches = re.findall(r'href="/rocom/[^"]+"\s+title="([^"]+)"', html)

    # 去重并保持顺序
    unique_skills = list(dict.fromkeys(skill_matches))

    # 过滤掉非技能项（如"首页"等）
    # 根据实际数据，正常技能名长度为 2-11 个字符
    filtered_skills = []
    for name in unique_skills:
        # 排除明显的非技能项
        if name in ["首页", "图鉴", "技能图鉴"]:
            continue
        # 长度限制：2-15（留有余量，实际最长技能名为 11）
        if len(name) < 2 or len(name) > 15:
            continue
        # 排除包含特殊字符的项（如"本页面过去的版本 [h]"）
        if '[' in name or ']' in name:
            continue
        # 排除包含"版本"或"页面"的项（WIKI 系统页面）
        if "版本" in name or "页面" in name:
            continue
        filtered_skills.append(name)

    print(f"  共找到 {len(filtered_skills)} 个技能")
    return filtered_skills


def fetch(url: str, retries: int = 3) -> str:
    """带重试的 HTTP GET"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
            else:
                print(f"请求失败：{e}")
                return ""


def extract_text(html: str, pattern: str) -> str:
    """提取文本并清理"""
    match = re.search(pattern, html)
    if match:
        text = match.group(1)
        # 去掉 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        # 清理空白
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    return ""


def parse_skill_page(html: str, skill_name: str) -> Optional[Dict]:
    """
    从技能详情页解析数据

    页面结构:
    - rocom_skill_template_skillAttribute: 属性 (如"冰系")
    - rocom_skill_template_skillConsume_box: 耗能 (如"<span>4</span>")
    - rocom_skill_template_skillSort: 分类 (如"魔攻" 带图片)
    - rocom_skill_template_skillPower: 威力 (如"<b>0</b>")
    - rocom_skill_template_skillEffect: 技能效果描述
    - rocom_skill_template_skillDescribe: 技能简介 (可选)

    返回 {
        "技能名": str,
        "属性": str,
        "分类": str,
        "耗能": str,
        "威力": str,
        "技能描述": str,
        "可学习精灵": str (用 | 分隔),
    }
    """
    result = {
        "技能名": skill_name,
        "属性": "",
        "分类": "",
        "耗能": "",
        "威力": "",
        "技能描述": "",
        "可学习精灵": "",
    }

    # 属性：从图片 alt 提取，如"图标 宠物 属性 冰.png" → "冰"
    attr_match = re.search(
        r'class="rocom_skill_template_skillAttribute"[^>]*>.*?alt="图标 宠物 属性 (\w+)\.png"',
        html
    )
    if attr_match:
        result["属性"] = attr_match.group(1)

    # 耗能：rocom_skill_template_skillConsume_box 中的数字
    energy_match = re.search(
        r'class="rocom_skill_template_skillConsume_box"[^>]*>\s*<span>(\d+)</span>',
        html
    )
    if energy_match:
        result["耗能"] = energy_match.group(1)

    # 分类：从图片 alt 提取，如"图标 技能 技能分类 魔攻.png" → "魔攻"
    sort_match = re.search(
        r'class="rocom_skill_template_skillSort"[^>]*>.*?alt="图标 技能 技能分类 (\w+)\.png"',
        html, re.DOTALL
    )
    if sort_match:
        result["分类"] = sort_match.group(1)

    # 威力：rocom_skill_template_skillPower 中的 <b> 数字
    power_match = re.search(
        r'class="rocom_skill_template_skillPower"[^>]*>.*?<b[^>]*>(\d+)</b>',
        html, re.DOTALL
    )
    if power_match:
        result["威力"] = power_match.group(1)

    # 技能效果：rocom_skill_template_skillEffect
    effect_match = re.search(
        r'class="rocom_skill_template_skillEffect"[^>]*>([\s\S]*?)</div>',
        html
    )
    if effect_match:
        effect_html = effect_match.group(1)
        # 去掉 HTML 标签和特殊符号
        effect_text = re.sub(r'<[^>]+>', '', effect_html)
        effect_text = re.sub(r'[✦◆★]\s*', '', effect_text)
        effect_text = re.sub(r'\s+', ' ', effect_text).strip()
        result["技能描述"] = effect_text

    # 技能简介：rocom_skill_template_skillDescribe (可选)
    if not result["技能描述"]:
        desc_match = re.search(
            r'class="rocom_skill_template_skillDescribe"[^>]*>([\s\S]*?)</div>',
            html
        )
        if desc_match:
            desc_html = desc_match.group(1)
            desc_text = re.sub(r'<[^>]+>', '', desc_html)
            desc_text = re.sub(r'\s+', ' ', desc_text).strip()
            if desc_text:
                result["技能描述"] = desc_text

    # 可学习精灵：找"可以学会的精灵"部分 (rocom_canlearn_box)
    # 结构：<div class="rocom_canlearn_img_box"><a href="..." title="电企鹅"><img alt="..." .../></a></div>
    pet_matches = re.findall(
        r'class="rocom_canlearn_img_box"[^>]*>.*?<a[^>]*title="([^"]+)"',
        html
    )
    if pet_matches:
        # 去重并保持顺序
        unique_pets = list(dict.fromkeys(pet_matches))
        result["可学习精灵"] = "|".join(unique_pets)

    return result


def scrape_skill(name: str) -> Optional[Dict]:
    """爬取单个技能"""
    encoded = urllib.parse.quote(name, safe='')
    url = f"https://wiki.biligame.com/rocom/{encoded}"

    try:
        html = fetch(url)
        if not html:
            return None

        data = parse_skill_page(html, name)
        return data
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def write_csv(results: List[Dict], path: Path) -> None:
    """写入 CSV 文件"""
    fieldnames = ['技能名', '属性', '分类', '耗能', '威力', '技能描述', '可学习精灵']
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def load_progress() -> tuple:
    """加载进度"""
    done_names = set()
    results = []
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            done_names = set(data.get("done", []))
            results = data.get("results", [])
    return done_names, results


def save_progress(done_names: set, results: List[Dict]) -> None:
    """保存进度"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"done": list(done_names), "results": results}, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="从 BiliGame Wiki 爬取技能数据")
    parser.add_argument("--test", metavar="NAME", help="只测试单个技能（如 '冰锋横扫'）")
    parser.add_argument("--limit", type=int, default=0, help="限制爬取数量（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入文件")
    parser.add_argument("--resume", action="store_true", help="从上次进度继续")
    parser.add_argument("--no-retry", action="store_true", help="不重试失败的条目（默认模式会自动重试直到全部成功）")
    args = parser.parse_args()

    # 从 Wiki 获取最新技能列表
    all_skills = fetch_skill_list_from_wiki()
    if not all_skills:
        print("[ERROR] 无法从 Wiki 获取技能列表，请检查网络连接或网站状态")
        sys.exit(1)

    # 测试模式
    if args.test:
        print(f"=== 测试爬取：{args.test} ===")
        data = scrape_skill(args.test)
        if data:
            print(f"技能名：{data['技能名']}")
            print(f"属性：{data['属性']}")
            print(f"分类：{data['分类']}")
            print(f"耗能：{data['耗能']}")
            print(f"威力：{data['威力']}")
            print(f"描述：{data['技能描述']}")
            pets = data.get('可学习精灵', '')
            if pets:
                print(f"可学习精灵：{pets[:50]}..." if len(pets) > 50 else f"可学习精灵：{pets}")
        else:
            print("爬取失败")
        return

    # 限制数量
    if args.limit > 0:
        all_skills = all_skills[:args.limit]

    # 加载进度
    done_names = set()
    results = []
    if args.resume:
        done_names, results = load_progress()
        print(f"恢复进度：已完成 {len(done_names)} 个")

    total = len(all_skills)

    # 主循环：爬取所有技能
    print(f"开始爬取 {len(all_skills)} 个技能...")

    try:
        while True:
            failed_names = []
            round_stats = {"success": 0, "failed": 0, "skipped": 0}

            for i, name in enumerate(all_skills):
                if name in done_names:
                    round_stats["skipped"] += 1
                    continue

                progress = f"[{i+1}/{total}]"
                print(f"{progress} {name}...", end=" ", flush=True)

                data = scrape_skill(name)
                if data and data.get("技能描述"):
                    # 检查是否已存在，存在则更新
                    existing_idx = next((idx for idx, r in enumerate(results) if r["技能名"] == name), None)
                    if existing_idx is not None:
                        results[existing_idx] = data
                    else:
                        results.append(data)
                    done_names.add(name)
                    round_stats["success"] += 1
                    print(f"OK (描述长度={len(data['技能描述'])})")
                else:
                    round_stats["failed"] += 1
                    print(f"FAILED")
                    failed_names.append(name)

                # 定期保存进度
                if (i + 1) % 50 == 0:
                    if not args.dry_run:
                        save_progress(done_names, results)
                        write_csv(results, OUTPUT_CSV)
                        print(f"  >> 已保存 {len(results)} 条记录")

                time.sleep(DELAY)

            # 最终保存
            if not args.dry_run:
                save_progress(done_names, results)
                write_csv(results, OUTPUT_CSV)

            # 打印统计
            print(f"\n本轮完成：共 {len(results)} 条记录")
            print(f"  本轮成功：{round_stats['success']}")
            print(f"  本轮失败：{round_stats['failed']}")
            print(f"  本轮跳过：{round_stats['skipped']}")

            # 如果没有失败项，或者启用了 --no-retry，则退出循环
            if not failed_names or args.no_retry:
                break

            # 否则，准备重试失败的条目
            print(f"\n{len(failed_names)} 个技能爬取失败，准备重试：{', '.join(failed_names)}")
            print("按 Ctrl+C 可中断...")
            time.sleep(2)

            # 重置失败项的完成状态，以便重试
            for name in failed_names:
                done_names.discard(name)
                # 从结果中移除失败的条目（如果存在）
                results = [r for r in results if r["技能名"] != name]

            print(f"开始重试 {len(failed_names)} 个技能...")
            time.sleep(DELAY * 2)  # 重试前等待一下

    except KeyboardInterrupt:
        print("\n\n用户中断爬取")
        if not args.dry_run:
            save_progress(done_names, results)
            write_csv(results, OUTPUT_CSV)
            print(f"进度已保存，共 {len(results)} 条记录")
        print(f"CSV 保存在：{OUTPUT_CSV}")
        print("使用 --resume 参数可从上次进度继续")
        return

    # 全部成功，删除进度文件
    if not args.dry_run and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print(f"\n进度文件已删除：{PROGRESS_FILE}")

    print(f"CSV 保存在：{OUTPUT_CSV}")


if __name__ == "__main__":
    main()

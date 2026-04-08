#!/usr/bin/env python3
"""
洛克王国精灵图鉴爬虫
从 wiki.biligame.com 爬取所有精灵的：
1. 立绘图片（icon）
2. 进化链信息
3. 身高体重区间
输出：
- data/spirit_icons/ 目录下所有精灵图片
- data/spirit_evolution.csv 记录进化链+身高体重
"""

import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_URL = "https://wiki.biligame.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://wiki.biligame.com/",
}

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "data" / "spirit_icons"
CSV_PATH = ROOT / "data" / "spirit_evolution.csv"


def fetch(url: str, retries: int = 3) -> str:
    """带重试的 HTTP GET"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
            else:
                print(f"  [ERROR] Failed to fetch {url}: {e}")
                return ""


def fetch_bytes(url: str, retries: int = 3) -> bytes:
    """带重试的二进制下载"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 + attempt)
            else:
                print(f"  [ERROR] Failed to download {url}: {e}")
                return b""


def parse_spirit_list(html: str) -> list[dict]:
    """
    从主页解析精灵列表
    每个 divsort 块包含一个精灵卡片
    两种属性模式：
      data-param1, data-param2, data-param3, data-param4, data-reverse, data-param5, data-param6
      data-param1, data-param2, data-param4, data-reverse, data-param5, data-param6
    """
    spirits = []

    # 通用属性提取（逐个提取而不是固定顺序）
    def extract_data_param(text, param_name):
        m = re.search(rf'{param_name}="([^"]*)"', text)
        return m.group(1) if m else ""

    # 精灵编号和名称
    name_pattern = re.compile(
        r'<span style="color:#343437;font-weight:0;font-size:10px;">(NO\.\d+)</span>.*?'
        r'<span class="font-mainfeiziti"[^>]*>([^<]+)</span>',
        re.DOTALL
    )

    # 图片链接 (src 在 class 前面)
    img_pattern = re.compile(
        r'<img[^>]*src="([^"]+)"[^>]*class="rocom_prop_icon"[^>]*/?>',
        re.DOTALL
    )

    # 详情页链接
    link_pattern = re.compile(
        r'<a\s+href="(/rocom/[^"]+)"\s+title="([^"]+)"',
        re.DOTALL
    )

    # 分割每个卡片
    card_splits = re.split(r'(?=<div\s+class="divsort")', html)

    for card_html in card_splits:
        if 'class="divsort"' not in card_html:
            continue

        # 提取 divsort 标签的属性
        div_match = re.search(r'<div\s+class="divsort"([^>]*)>', card_html)
        if not div_match:
            continue
        div_attrs = div_match.group(1)

        stage = extract_data_param(div_attrs, "data-param1")       # 阶段
        element = extract_data_param(div_attrs, "data-param2")     # 属性
        form_type = extract_data_param(div_attrs, "data-param4")   # 形态分类
        form = extract_data_param(div_attrs, "data-param5")        # 形态
        has_variant = extract_data_param(div_attrs, "data-param6") # 异色

        m_name = name_pattern.search(card_html)
        if not m_name:
            continue
        number = m_name.group(1)
        name = m_name.group(2).strip()

        m_img = img_pattern.search(card_html)
        img_url = m_img.group(1) if m_img else ""

        m_link = link_pattern.search(card_html)
        detail_path = m_link.group(1) if m_link else ""
        detail_url = BASE_URL + detail_path if detail_path else ""

        spirits.append({
            "number": number,
            "name": name,
            "stage": stage,
            "element": element,
            "form_type": form_type,
            "form": form,
            "has_variant": has_variant,
            "img_url": img_url,
            "detail_url": detail_url,
        })

    return spirits


def get_full_img_url(thumb_url: str) -> str:
    """
    从缩略图 URL 获取原始大图 URL
    缩略图: .../thumb/2/25/xxx.png/180px-yyy.png
    原图:   .../2/25/xxx.png
    """
    if "/thumb/" in thumb_url:
        # 去掉 /thumb/ 前缀和末尾的 /NNNpx-xxx.png
        parts = thumb_url.split("/thumb/")
        if len(parts) == 2:
            after_thumb = parts[1]
            # 找到最后一个 / 之前的部分
            segments = after_thumb.rsplit("/", 1)
            if len(segments) == 2:
                return parts[0] + "/" + segments[0]
    return thumb_url


def parse_detail_page(html: str, name: str) -> dict:
    """
    从精灵详情页解析进化链和身高体重
    """
    result = {
        "height_range": "",
        "weight_range": "",
        "evolution_chain": "",
        "evolution_levels": "",
        "evolution_condition": "",
    }

    # === 身高体重 ===
    # 身高在"图标 宠物 体质 身高.png"后面的<p>标签中
    height_match = re.search(
        r'alt="图标 宠物 体质 身高\.png".*?</div>\s*<p>([^<]+)</p>\s*<p[^>]*>([^<]*)</p>',
        html, re.DOTALL
    )
    if height_match:
        result["height_range"] = height_match.group(1).strip() + height_match.group(2).strip()

    weight_match = re.search(
        r'alt="图标 宠物 体质 体重\.png".*?</div>\s*<p>([^<]+)</p>\s*<p[^>]*>([^<]*)</p>',
        html, re.DOTALL
    )
    if weight_match:
        result["weight_range"] = weight_match.group(1).strip() + weight_match.group(2).strip()

    # === 进化链 ===
    evo_box = re.search(
        r'<div class="rocom_spirit_evolution_box">(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL
    )
    if not evo_box:
        # 尝试更宽松的匹配
        evo_box = re.search(
            r'进化链(.*?)进化条件',
            html, re.DOTALL
        )

    if evo_box:
        evo_html = evo_box.group(1) if evo_box else ""

        # 提取进化链中的精灵名称
        evo_names = re.findall(r'title="([^"]+)"', evo_html)
        # 去重保持顺序
        seen = set()
        unique_names = []
        for n in evo_names:
            if n not in seen:
                seen.add(n)
                unique_names.append(n)
        result["evolution_chain"] = " → ".join(unique_names) if unique_names else name

        # 提取进化等级
        evo_levels = re.findall(
            r'rocom_spirit_evolution_level_num">(\d+)</p>',
            evo_html
        )
        result["evolution_levels"] = ",".join(evo_levels)

    # 进化条件
    cond_match = re.search(
        r'进化条件:\s*<p[^>]*>([^<]+)</p>',
        html
    )
    if cond_match:
        result["evolution_condition"] = cond_match.group(1).strip()

    return result


def download_image(spirit: dict, icon_dir: Path) -> str:
    """下载精灵图片，返回保存文件名"""
    img_url = spirit.get("img_url", "")
    if not img_url:
        return ""

    # 获取原始大图
    full_url = get_full_img_url(img_url)

    # 文件名：编号_名字.png
    safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', spirit["name"])
    filename = f"{spirit['number'].replace('.', '')}_{safe_name}.png"
    filepath = icon_dir / filename

    if filepath.exists():
        return filename

    data = fetch_bytes(full_url)
    if data:
        filepath.write_bytes(data)
        return filename
    return ""


def main():
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: 获取主页精灵列表
    print("=" * 60)
    print("Step 1: 爬取精灵图鉴主页...")
    print("=" * 60)
    list_url = BASE_URL + "/rocom/%E7%B2%BE%E7%81%B5%E5%9B%BE%E9%89%B4"
    list_html = fetch(list_url)
    if not list_html:
        print("ERROR: 无法获取精灵图鉴主页")
        sys.exit(1)

    spirits = parse_spirit_list(list_html)
    print(f"  共找到 {len(spirits)} 个精灵")

    # 去掉 logo 等非精灵项（编号应为 NO.xxx）
    spirits = [s for s in spirits if s["number"].startswith("NO.")]
    print(f"  过滤后: {len(spirits)} 个有效精灵")

    # 只处理「最终形态」以避免重复爬详情页
    # 但我们也要记录所有阶段的精灵
    # 先按 detail_url 分组，同一个详情页只爬一次
    detail_urls = {}
    for s in spirits:
        if s["detail_url"] and s["detail_url"] not in detail_urls:
            detail_urls[s["detail_url"]] = s["name"]

    print(f"  独立详情页: {len(detail_urls)} 个")

    # Step 2: 爬取每个精灵的详情页
    print("\n" + "=" * 60)
    print("Step 2: 爬取精灵详情页（进化链 + 身高体重）...")
    print("=" * 60)

    detail_data = {}  # name -> {height, weight, evolution, ...}
    total = len(detail_urls)

    for i, (url, name) in enumerate(detail_urls.items()):
        progress = f"[{i+1}/{total}]"
        print(f"  {progress} 爬取: {name} ...", end="", flush=True)

        html = fetch(url)
        if html:
            info = parse_detail_page(html, name)
            detail_data[name] = info
            evo = info.get("evolution_chain", "")
            h = info.get("height_range", "")
            w = info.get("weight_range", "")
            print(f" ✓ 身高={h} 体重={w} 进化链={evo}")
        else:
            detail_data[name] = {
                "height_range": "",
                "weight_range": "",
                "evolution_chain": name,
                "evolution_levels": "",
                "evolution_condition": "",
            }
            print(" ✗ 失败")

        # 请求间隔，避免被限流
        if (i + 1) % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.3)

    # Step 3: 下载所有精灵图片
    print("\n" + "=" * 60)
    print("Step 3: 下载精灵图片...")
    print("=" * 60)

    def download_one(spirit):
        filename = download_image(spirit, ICON_DIR)
        return spirit["name"], filename

    downloaded = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(download_one, s): s for s in spirits}
        for i, future in enumerate(as_completed(futures)):
            name, filename = future.result()
            if filename:
                downloaded += 1
            else:
                failed += 1
            if (i + 1) % 50 == 0:
                print(f"  已下载 {downloaded}/{i+1}，失败 {failed}")

    print(f"  完成: 下载 {downloaded} 张，失败 {failed} 张")
    print(f"  图片保存在: {ICON_DIR}")

    # Step 4: 写入 CSV
    print("\n" + "=" * 60)
    print("Step 4: 生成 CSV 文件...")
    print("=" * 60)

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "编号", "名字", "阶段", "属性",
            "形态分类", "形态", "是否有异色",
            "身高范围", "体重范围",
            "进化链", "进化等级", "进化条件",
            "图片文件名"
        ])

        for s in spirits:
            info = detail_data.get(s["name"], {})
            safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', s["name"])
            filename = f"{s['number'].replace('.', '')}_{safe_name}.png"
            img_exists = (ICON_DIR / filename).exists()

            writer.writerow([
                s["number"],
                s["name"],
                s["stage"],
                s["element"],
                s["form_type"],
                s["form"],
                s["has_variant"],
                info.get("height_range", ""),
                info.get("weight_range", ""),
                info.get("evolution_chain", ""),
                info.get("evolution_levels", ""),
                info.get("evolution_condition", ""),
                filename if img_exists else "",
            ])

    print(f"  CSV 保存在: {CSV_PATH}")
    print("\n" + "=" * 60)
    print("全部完成!")
    print(f"  精灵总数: {len(spirits)}")
    print(f"  图片目录: {ICON_DIR}")
    print(f"  CSV文件: {CSV_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()

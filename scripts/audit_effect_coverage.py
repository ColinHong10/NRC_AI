"""
scripts/audit_effect_coverage.py

Audit coverage for skill effects and ability effects.

What it reports:
  - total skills in the SQLite DB
  - skills with / without parsed effects
  - manual vs generated skill effect coverage
  - unique abilities in the pokemon table
  - abilities with / without configured AbilityEffect entries

Usage:
    py scripts/audit_effect_coverage.py
    py scripts/audit_effect_coverage.py --all
    py scripts/audit_effect_coverage.py --json data/audit_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.effect_data import ABILITY_EFFECTS, SKILL_EFFECTS


DB_PATH = os.path.join(ROOT, "data", "nrc.db")


@dataclass
class CoverageSummary:
    total: int
    covered: int
    missing: int
    coverage_pct: float


def _get_conn(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_skill_rows(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        "SELECT name, element, category, power, energy_cost, description "
        "FROM skill ORDER BY name"
    )
    return cur.fetchall()


def _fetch_unique_abilities(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ability FROM pokemon WHERE ability IS NOT NULL AND ability != ''")
    names = []
    for (ability,) in cur.fetchall():
        name = ability.split(":")[0].split("（")[0].strip()
        if name:
            names.append(name)
    return sorted(set(names))


def _calc_summary(total: int, covered: int) -> CoverageSummary:
    missing = max(0, total - covered)
    pct = round((covered / total) * 100, 2) if total else 100.0
    return CoverageSummary(total=total, covered=covered, missing=missing, coverage_pct=pct)


def _print_summary(title: str, summary: CoverageSummary) -> None:
    print(f"{title}: {summary.covered}/{summary.total} ({summary.coverage_pct:.2f}%) covered, {summary.missing} missing")


def _print_list(label: str, items: List[str], show_all: bool, limit: int) -> None:
    print()
    print(label)
    if not items:
        print("  - none")
        return

    display = items if show_all else items[:limit]
    for name in display:
        print(f"  - {name}")
    if not show_all and len(items) > limit:
        print(f"  ... and {len(items) - limit} more (use --all to show every item)")


def audit(db_path: str = DB_PATH) -> Dict:
    conn = _get_conn(db_path)
    try:
        skill_rows = _fetch_skill_rows(conn)
        ability_names = _fetch_unique_abilities(conn)
    finally:
        conn.close()

    manual_skill_names = set(SKILL_EFFECTS.keys())
    generated_skill_names = set()
    generated_effect_skill_names = set()
    try:
        from src.skill_effects_generated import SKILL_EFFECTS_GENERATED

        generated_skill_names = set(SKILL_EFFECTS_GENERATED.keys())
        generated_effect_skill_names = {
            name for name, tags in SKILL_EFFECTS_GENERATED.items() if tags
        }
    except Exception:
        generated_skill_names = set()
        generated_effect_skill_names = set()

    all_skill_names = [row["name"] for row in skill_rows]
    manual_effect_skill_names = {
        name for name, tags in SKILL_EFFECTS.items() if tags
    }

    covered_skill_names = [
        name for name in all_skill_names
        if name in manual_effect_skill_names or name in generated_effect_skill_names
    ]
    missing_skill_names = [
        name for name in all_skill_names
        if name not in manual_effect_skill_names and name not in generated_effect_skill_names
    ]

    covered_manual = [name for name in all_skill_names if name in manual_effect_skill_names]
    covered_generated = [
        name for name in all_skill_names
        if name in generated_effect_skill_names and name not in manual_effect_skill_names
    ]

    skill_summary = _calc_summary(len(all_skill_names), len(covered_skill_names))

    covered_abilities = [name for name in ability_names if name in ABILITY_EFFECTS]
    missing_abilities = [name for name in ability_names if name not in ABILITY_EFFECTS]
    ability_summary = _calc_summary(len(ability_names), len(covered_abilities))

    return {
        "db_path": db_path,
        "skill_effects": {
            "summary": asdict(skill_summary),
            "manual_count": len(manual_skill_names),
            "generated_count": len(generated_skill_names),
            "manual_effect_count": len(manual_effect_skill_names),
            "generated_effect_count": len(generated_effect_skill_names),
            "manual_skill_names": sorted(manual_skill_names),
            "generated_skill_names": sorted(generated_skill_names),
            "manual_effect_skill_names": sorted(manual_effect_skill_names),
            "generated_effect_skill_names": sorted(generated_effect_skill_names),
            "covered_skill_names": covered_skill_names,
            "missing_skill_names": missing_skill_names,
            "covered_manual_skill_names": covered_manual,
            "covered_generated_skill_names": covered_generated,
        },
        "ability_effects": {
            "summary": asdict(ability_summary),
            "configured_count": len(ABILITY_EFFECTS),
            "ability_names": ability_names,
            "covered_ability_names": covered_abilities,
            "missing_ability_names": missing_abilities,
        },
        "skills_without_effects": missing_skill_names,
        "abilities_without_effects": missing_abilities,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit skill and ability effect coverage.")
    parser.add_argument("--db", default=DB_PATH, help="Path to the SQLite database (default: data/nrc.db)")
    parser.add_argument("--all", action="store_true", help="Print all missing skill / ability names")
    parser.add_argument("--limit", type=int, default=30, help="How many missing items to print when --all is not set")
    parser.add_argument("--json", dest="json_path", help="Write the full report to a JSON file")
    args = parser.parse_args()

    report = audit(args.db)

    skill_summary = report["skill_effects"]["summary"]
    ability_summary = report["ability_effects"]["summary"]

    print("Skill effect coverage")
    _print_summary("  skills", CoverageSummary(**skill_summary))
    print(f"  manual mappings: {report['skill_effects']['manual_count']}")
    print(f"  generated mappings: {report['skill_effects']['generated_count']}")
    print(f"  manual effect skills: {report['skill_effects']['manual_effect_count']}")
    print(f"  generated effect skills: {report['skill_effects']['generated_effect_count']}")
    print(f"  covered by manual config: {len(report['skill_effects']['covered_manual_skill_names'])}")
    print(f"  covered by generated config: {len(report['skill_effects']['covered_generated_skill_names'])}")
    _print_list("Missing skills without effect mapping", report["skills_without_effects"], args.all, args.limit)

    print()
    print("Ability effect coverage")
    _print_summary("  abilities", CoverageSummary(**ability_summary))
    print(f"  configured abilities: {report['ability_effects']['configured_count']}")
    _print_list("Missing abilities without AbilityEffect config", report["abilities_without_effects"], args.all, args.limit)

    if args.json_path:
        out_dir = os.path.dirname(os.path.abspath(args.json_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print()
        print(f"JSON report written to: {args.json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

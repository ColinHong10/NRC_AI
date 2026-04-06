"""
scripts/stats_verification_framework.py

P0 Task #31: Pokemon Stats Verification Framework

This script provides utilities for verifying Pokemon stats against live game data.
It creates:
  1. Export templates for game data capture
  2. Comparison tools for identifying discrepancies
  3. Reporting on stat variance
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class PokemonStatsVerifier:
    """Framework for verifying Pokemon stats."""
    
    DB_PATH = project_root / "data" / "nrc.db"
    
    def __init__(self):
        """Initialize verifier with database connection."""
        self.conn = sqlite3.connect(str(self.DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def get_all_pokemon(self) -> List[Dict]:
        """Fetch all Pokemon from database."""
        self.cursor.execute("""
            SELECT id, name, 
                   stat_hp as hp, stat_atk as attack, stat_def as defense, 
                   stat_spatk as sp_attack, stat_spdef as sp_defense, stat_speed as speed
            FROM pokemon
            ORDER BY id
        """)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_pokemon_by_name(self, name: str) -> Optional[Dict]:
        """Get Pokemon stats by name."""
        self.cursor.execute("""
            SELECT id, name, 
                   stat_hp as hp, stat_atk as attack, stat_def as defense, 
                   stat_spatk as sp_attack, stat_spdef as sp_defense, stat_speed as speed
            FROM pokemon
            WHERE name = ?
        """, (name,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def export_verification_csv(self, output_path: str, limit: Optional[int] = None):
        """
        Export Pokemon stats as CSV for easy game data entry.
        Format: name, hp_db, attack_db, defense_db, sp_attack_db, sp_defense_db, speed_db, hp_game, ...
        """
        pokemon_list = self.get_all_pokemon()
        if limit:
            pokemon_list = pokemon_list[:limit]
        
        with open(output_path, 'w') as f:
            # Header
            header = "name," + ",".join([
                "hp_db", "atk_db", "def_db", "spatk_db", "spdef_db", "spd_db",
                "hp_game", "atk_game", "def_game", "spatk_game", "spdef_game", "spd_game",
                "verified"
            ])
            f.write(header + "\n")
            
            # Rows
            for mon in pokemon_list:
                row = f"{mon['name']}," + ",".join([
                    str(mon['hp']), str(mon['attack']), str(mon['defense']),
                    str(mon['sp_attack']), str(mon['sp_defense']), str(mon['speed']),
                    ",,,,,,",  # Empty game columns
                    "NO",  # Verified flag
                ])
                f.write(row + "\n")
        
        print(f"✅ Exported {len(pokemon_list)} Pokemon to {output_path}")
    
    def verify_stats_from_csv(self, csv_path: str) -> Dict:
        """
        Verify Pokemon stats from populated CSV file.
        Returns: {"matches": [...], "mismatches": [...], "missing": [...]}
        """
        import csv
        
        results = {
            "matches": [],
            "mismatches": [],
            "missing": [],
            "total_checked": 0,
            "accuracy": 0.0,
        }
        
        stat_fields = ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                name = row.get('name')
                if not name or name.strip() == "":
                    continue
                
                results["total_checked"] += 1
                db_stats = self.get_pokemon_by_name(name)
                
                if not db_stats:
                    results["missing"].append(name)
                    continue
                
                # Compare each stat
                mismatches = {}
                for stat in stat_fields:
                    game_key = f"{stat}_game"
                    db_key = f"{stat}_db"
                    
                    game_val_str = row.get(game_key, "").strip()
                    if not game_val_str:
                        continue
                    
                    try:
                        game_val = int(game_val_str)
                        db_val = db_stats[stat]
                        
                        if game_val != db_val:
                            mismatches[stat] = {
                                "db": db_val,
                                "game": game_val,
                                "diff": game_val - db_val,
                            }
                    except ValueError:
                        pass
                
                if mismatches:
                    results["mismatches"].append({
                        "name": name,
                        "stats": mismatches,
                    })
                else:
                    results["matches"].append(name)
        
        if results["total_checked"] > 0:
            results["accuracy"] = len(results["matches"]) / results["total_checked"]
        
        return results
    
    def generate_report(self, verified_data: Dict) -> str:
        """Generate human-readable report of verification results."""
        report = []
        report.append("=" * 70)
        report.append("POKEMON STATS VERIFICATION REPORT")
        report.append("=" * 70)
        report.append("")
        
        total = verified_data["total_checked"]
        matches = len(verified_data["matches"])
        mismatches = len(verified_data["mismatches"])
        missing = len(verified_data["missing"])
        
        report.append(f"Total Checked: {total}")
        report.append(f"Matches: {matches} ({matches/total*100:.1f}% if total>0)")
        report.append(f"Mismatches: {mismatches}")
        report.append(f"Missing: {missing}")
        report.append(f"Database Accuracy: {verified_data['accuracy']*100:.1f}%")
        report.append("")
        
        if verified_data["mismatches"]:
            report.append("STAT MISMATCHES (Database vs Game):")
            report.append("-" * 70)
            for mismatch in verified_data["mismatches"]:
                report.append(f"\n{mismatch['name']}:")
                for stat, values in mismatch["stats"].items():
                    report.append(f"  {stat:10s}: DB={values['db']:3d} Game={values['game']:3d} "
                                f"(diff={values['diff']:+3d})")
            report.append("")
        
        if verified_data["missing"]:
            report.append("NOT FOUND IN DATABASE:")
            report.append("-" * 70)
            for name in verified_data["missing"][:10]:  # Show first 10
                report.append(f"  {name}")
            if len(verified_data["missing"]) > 10:
                report.append(f"  ... and {len(verified_data['missing']) - 10} more")
            report.append("")
        
        report.append("=" * 70)
        return "\n".join(report)


def main():
    """CLI interface for stats verification."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pokemon stats verification framework")
    parser.add_argument("--export", type=int, default=0, help="Export CSV template (specify limit, 0=all)")
    parser.add_argument("--verify", type=str, help="Verify stats from CSV file")
    parser.add_argument("--output", type=str, default="pokemon_stats_verification_template.csv", 
                       help="Output file for export")
    
    args = parser.parse_args()
    
    verifier = PokemonStatsVerifier()
    all_pokemon = verifier.get_all_pokemon()
    print(f"📊 Loaded {len(all_pokemon)} Pokemon from database\n")
    
    if args.export > 0:
        output_file = str(project_root / "data" / args.output)
        verifier.export_verification_csv(output_file, limit=args.export)
        print(f"\n📝 Template exported. Next steps:")
        print(f"   1. Open {args.output} in Excel")
        print(f"   2. Capture game data for 'game_*' columns")
        print(f"   3. Run verification: python scripts/stats_verification_framework.py --verify {args.output}")
    
    elif args.export == 0:
        output_file = str(project_root / "data" / args.output)
        verifier.export_verification_csv(output_file)
        print(f"\n📝 Full template exported: {args.output}")
    
    if args.verify:
        csv_file = str(project_root / "data" / args.verify)
        print(f"🔍 Verifying stats from {csv_file}...\n")
        results = verifier.verify_stats_from_csv(csv_file)
        report = verifier.generate_report(results)
        print(report)
        
        if results["mismatches"]:
            print("⚠️  Found stat discrepancies! Check if database needs updating.")


if __name__ == "__main__":
    # Default: export first 50 Pokemon
    main()

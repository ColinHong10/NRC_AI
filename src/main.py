"""
洛克王国战斗模拟系统 - 主程序 (v2)
集成: 技能数据库 + 应对系统 + 经验学习MCTS
"""

import sys, os, time, random, traceback
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.skill_db import load_skills, get_skill
from src.models import BattleState
from src.battle import (
    TeamBuilder, execute_full_turn, check_winner,
    auto_switch, get_actions
)
from src.mcts import MCTS, EXPERIENCE_A, EXPERIENCE_B


_db_loaded = False

def _ensure_loaded():
    """确保技能和精灵数据库已加载"""
    global _db_loaded
    if not _db_loaded:
        load_skills()
        from src.pokemon_db import load_pokemon_db
        load_pokemon_db()
        _db_loaded = True


def create_initial_state():
    _ensure_loaded()
    return BattleState(
        team_a=TeamBuilder.create_toxic_team(),
        team_b=TeamBuilder.create_wing_team(),
        current_a=0, current_b=0, turn=1
    )


def action_name(state, team, action):
    if action[0] == -1:
        return "汇合聚能"
    if action[0] == -2:
        team_list = state.team_a if team == "a" else state.team_b
        return f"换人->{team_list[action[1]].name}"
    current = state.team_a[state.current_a] if team == "a" else state.team_b[state.current_b]
    return current.skills[action[0]].name


def run_single_battle(simulations=200, verbose=True, use_experience=True):
    """运行单场对战"""
    state = create_initial_state()

    if verbose:
        print("=" * 50, flush=True)
        print("Rokugou Battle Simulator v2", flush=True)
        print("Team A (Toxic) vs Team B (Wing King)", flush=True)
        print(f"MCTS sims/turn: {simulations}", flush=True)
        print(f"Experience: {'ON' if use_experience else 'OFF'}", flush=True)
        print(f"Exp A: {EXPERIENCE_A.size} records | Exp B: {EXPERIENCE_B.size} records", flush=True)
        print("=" * 50, flush=True)

    mcts_a = MCTS(simulations=simulations, team="a",
                  experience=EXPERIENCE_A if use_experience else None)
    mcts_b = MCTS(simulations=simulations, team="b",
                  experience=EXPERIENCE_B if use_experience else None)

    start_time = time.time()

    for _ in range(150):
        winner = check_winner(state)
        if winner:
            if verbose:
                w = "A (Toxic)" if winner == "a" else "B (Wing King)"
                print(f"\n>>> Team {w} WINS!", flush=True)
            # 记录经验
            if use_experience:
                EXPERIENCE_A.record_battle(mcts_a.get_action_log(), won=(winner == "a"))
                EXPERIENCE_B.record_battle(mcts_b.get_action_log(), won=(winner == "b"))
                mcts_a.clear_log()
                mcts_b.clear_log()
            return winner, state.turn, time.time() - start_time

        auto_switch(state)
        if check_winner(state):
            break

        p_a = state.team_a[state.current_a]
        p_b = state.team_b[state.current_b]

        if verbose and state.turn <= 20:
            print(f"\n--- Round {state.turn} ---", flush=True)
            print(f"[A] {p_a.name}: HP={max(0,p_a.current_hp)}/{p_a.hp} EP={p_a.energy}", flush=True)
            print(f"[B] {p_b.name}: HP={max(0,p_b.current_hp)}/{p_b.hp} EP={p_b.energy}", flush=True)

        t1 = time.time()
        action_a = mcts_a.get_best_action(state)
        t_a = time.time() - t1

        action_b = mcts_b.get_best_action(state)
        t_b = time.time() - t1 - t_a

        if verbose and state.turn <= 20:
            print(f"  A: {action_name(state,'a',action_a)} ({t_a:.2f}s) | B: {action_name(state,'b',action_b)} ({t_b:.2f}s)", flush=True)

        execute_full_turn(state, action_a, action_b)

        if verbose and state.turn <= 20:
            p_a2 = state.team_a[state.current_a]
            p_b2 = state.team_b[state.current_b]
            print(f"  => {p_a2.name} HP={max(0,p_a2.current_hp)} | {p_b2.name} HP={max(0,p_b2.current_hp)}", flush=True)

    elapsed = time.time() - start_time
    winner = check_winner(state)

    if verbose:
        if not winner:
            print("\n>>> DRAW (max rounds)!", flush=True)
        print(f"\nFinished: {elapsed:.1f}s, {state.turn} rounds", flush=True)
        for team_name, team in [("A", state.team_a), ("B", state.team_b)]:
            print(f"Team {team_name}:", flush=True)
            for p in team:
                s = "FAINTED" if p.is_fainted else f"HP={p.current_hp}"
                print(f"  {p.name}: {s}", flush=True)

    if use_experience:
        EXPERIENCE_A.record_battle(mcts_a.get_action_log(), won=(winner == "a"))
        EXPERIENCE_B.record_battle(mcts_b.get_action_log(), won=(winner == "b"))
        mcts_a.clear_log()
        mcts_b.clear_log()

    return winner, state.turn, elapsed


def run_batch_simulation(games=50, simulations=100, use_experience=True):
    """批量模拟"""
    print("=" * 60, flush=True)
    exp_tag = "WITH Experience" if use_experience else "NO Experience"
    print(f" BATCH: {games} games x MCTS {simulations} sims [{exp_tag}]", flush=True)
    print("=" * 60, flush=True)

    results = {"a": 0, "b": 0}
    total_rounds = 0
    total_time = 0

    for i in range(games):
        if (i + 1) % max(1, games // 10) == 0 or i == 0:
            print(f"  Game {i+1}/{games}...", end="", flush=True)

        winner, rounds, elapsed = run_single_battle(
            simulations=simulations, verbose=False, use_experience=use_experience
        )
        if winner:
            results[winner] += 1
        total_rounds += rounds
        total_time += elapsed

        if (i + 1) % max(1, games // 10) == 0 or i == 0:
            tag = "A" if winner == "a" else "B" if winner == "b" else "?"
            print(f" {tag} win ({rounds}r)", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f" RESULTS ({games} games, {exp_tag}):", flush=True)
    print(f"   Team A (Toxic): {results['a']} wins ({results['a']/games*100:.1f}%)", flush=True)
    print(f"   Team B (Wing) : {results['b']} wins ({results['b']/games*100:.1f}%)", flush=True)
    print(f"   Avg rounds: {total_rounds/games:.1f}", flush=True)
    print(f"   Avg time:   {total_time/games:.2f}s/game", flush=True)
    print(f"   Exp A: {EXPERIENCE_A.size} | Exp B: {EXPERIENCE_B.size}", flush=True)
    print(f"{'='*60}", flush=True)
    return results


def run_learning_experiment(games=100, simulations=50):
    """
    经验学习实验：
    分4阶段，每阶段25场，观察学习效果
    """
    global EXPERIENCE_A, EXPERIENCE_B

    print("\n" + "=" * 65, flush=True)
    print(" LEARNING EXPERIMENT: Does experience improve performance?", flush=True)
    print("=" * 65, flush=True)

    phases = [
        (25, "Phase 1: Cold Start (no experience)"),
        (25, "Phase 2: Learning... (25 games experience)"),
        (25, "Phase 3: More data (50 games experience)"),
        (25, "Phase 4: Mature (75 games experience)"),
    ]

    print(f"{'Phase':<48} | {'A':>3} | {'B':>3} | {'A%':>5} | {'AvgRnd':>7}", flush=True)
    print("-" * 72, flush=True)

    for n_games, phase_name in phases:
        # 用经验模式打
        a_w, b_w = 0, 0
        rounds_list = []
        t0 = time.time()

        print(f"  >> {phase_name}", flush=True)
        for g_i in range(n_games):
            winner, rnd, _ = run_single_battle(
                simulations=simulations, verbose=False, use_experience=True
            )
            if winner == "a":
                a_w += 1
            elif winner == "b":
                b_w += 1
            rounds_list.append(rnd)
            tag = "A" if winner == "a" else "B" if winner == "b" else "?"
            print(f"[{g_i+1}/{n_games}]{tag}({rnd}r)", end=" ", flush=True)
        print(flush=True)

        dt = time.time() - t0
        total = a_w + b_w
        rate = a_w / total * 100 if total else 0
        avg_r = sum(rounds_list) / len(rounds_list)
        print(f"{phase_name:<48} | {a_w:>3} | {b_w:>3} | {rate:>5.1f}% | {avg_r:>7.1f}  ({dt:.1f}s)", flush=True)

    print(f"\n{'='*65}", flush=True)
    print(f" Final experience: A={EXPERIENCE_A.size} | B={EXPERIENCE_B.size}", flush=True)
    print(f"{'='*65}", flush=True)


def run_player_vs_ai(simulations=200):
    """玩家控制A队 vs AI(带经验)控制B队"""
    state = create_initial_state()

    print("\n" + "=" * 55, flush=True)
    print("  PLAYER (A-毒队) vs AI (B-翼王队)", flush=True)
    print(f"  AI Experience: B={EXPERIENCE_B.size} records", flush=True)
    print(f"  AI MCTS sims/turn: {simulations}", flush=True)
    print("=" * 55, flush=True)

    # 显示队伍信息
    print("\n  [你的队伍 - Team A]:", flush=True)
    for i, p in enumerate(state.team_a):
        skills_str = ", ".join(f"{s.name}({s.energy_cost}能)" for s in p.skills)
        print(f"    {i}. {p.name} [{p.pokemon_type.value}] HP={p.hp} | {skills_str}", flush=True)
    print("\n  [AI队伍 - Team B]:", flush=True)
    for i, p in enumerate(state.team_b):
        skills_str = ", ".join(f"{s.name}({s.energy_cost}能)" for s in p.skills)
        print(f"    {i}. {p.name} [{p.pokemon_type.value}] HP={p.hp} | {skills_str}", flush=True)

    mcts_b = MCTS(simulations=simulations, team="b",
                  experience=EXPERIENCE_B)

    def show_status():
        pa = state.team_a[state.current_a]
        pb = state.team_b[state.current_b]
        bar_a = _hp_bar(pa.current_hp, pa.hp)
        bar_b = _hp_bar(pb.current_hp, pb.hp)
        print(f"\n  [A] {pa.name} HP {bar_a} {max(0,pa.current_hp)}/{pa.hp} | 能量:{pa.energy}", flush=True)
        print(f"      增益:{_fmt_mods(pa)} | 减益:{_fmt_debuffs(pa)} | 中毒:{pa.poison_stacks} 灼烧:{pa.burn_stacks} 冻结:{pa.freeze_stacks}", flush=True)
        print(f"  [B] {pb.name} HP {bar_b} {max(0,pb.current_hp)}/{pb.hp} | 能量:{pb.energy}", flush=True)
        print(f"      增益:{_fmt_mods(pb)} | 减益:{_fmt_debuffs(pb)} | 中毒:{pb.poison_stacks} 灼烧:{pb.burn_stacks} 冻结:{pb.freeze_stacks}", flush=True)

    def get_player_action():
        pa = state.team_a[state.current_a]
        print(f"\n  --- 选择行动 (回合 {state.turn}) ---", flush=True)
        print(f"  当前精灵: {pa.name}", flush=True)
        print(f"  技能:", flush=True)
        for i, s in enumerate(pa.skills):
            usable = "✓" if pa.energy >= s.energy_cost else "✗能量不足"
            effects = _skill_effects(s)
            print(f"    {i+1}. {s.name} | 威力:{s.power} 能耗:{s.energy_cost} 类型:{s.skill_type.value}/{s.category.value} {usable}  {effects}", flush=True)
        print(f"    0. 汇合聚能 (回复5能量)", flush=True)
        # 可换人
        switchable = []
        for i, p in enumerate(state.team_a):
            if i != state.current_a and not p.is_fainted:
                switchable.append(i)
        if switchable:
            opts = " ".join(f"{i+1}={state.team_a[i].name}" for i in switchable)
            print(f"    S. 换人 ({opts})", flush=True)

        while True:
            try:
                raw = input("\n  你的选择: ").strip().upper()
                if raw == "0":
                    return (-1, -1)
                if raw.startswith("S") or raw.startswith("换"):
                    if not switchable:
                        print("  没有可换的精灵!", flush=True)
                        continue
                    print(f"  选择要换上的精灵: ", end="", flush=True)
                    for i in switchable:
                        print(f"{i+1}={state.team_a[i].name} ", end="", flush=True)
                    print(flush=True)
                    sel = input("  > ").strip()
                    idx = int(sel) - 1
                    if idx in switchable:
                        return (-2, idx)
                    print("  无效选择!", flush=True)
                    continue
                idx = int(raw) - 1
                if 0 <= idx < len(pa.skills):
                    if pa.energy < pa.skills[idx].energy_cost:
                        print("  能量不足!", flush=True)
                        continue
                    return (idx, -1)
                print("  无效选择!", flush=True)
            except (ValueError, EOFError, KeyboardInterrupt):
                print("  无效输入!", flush=True)

    start_time = time.time()

    for _ in range(150):
        winner = check_winner(state)
        if winner:
            w = "你赢了! PLAYER WINS!" if winner == "a" else "AI赢了! AI WINS!"
            print(f"\n{'='*55}", flush=True)
            print(f"  >>> {w}", flush=True)
            print(f"  对战 {state.turn} 回合, 耗时 {time.time()-start_time:.1f}s", flush=True)
            print(f"{'='*55}", flush=True)
            # AI记录经验
            EXPERIENCE_B.record_battle(mcts_b.get_action_log(), won=(winner == "b"))
            mcts_b.clear_log()
            return winner

        auto_switch(state)
        if check_winner(state):
            break

        show_status()
        action_a = get_player_action()

        print("  AI思考中...", end="", flush=True)
        t0 = time.time()
        action_b = mcts_b.get_best_action(state)
        dt = time.time() - t0

        pb = state.team_b[state.current_b]
        if action_b[0] == -1:
            ai_desc = "汇合聚能"
        elif action_b[0] == -2:
            ai_desc = f"换人->{state.team_b[action_b[1]].name}"
        else:
            ai_desc = pb.skills[action_b[0]].name
        print(f"\r  AI选择: {ai_desc} ({dt:.2f}s)      ", flush=True)

        # 执行
        print(f"\n  --- 执行 ---", flush=True)
        execute_full_turn(state, action_a, action_b)

        show_status()
        pa2 = state.team_a[state.current_a]
        pb2 = state.team_b[state.current_b]
        print(f"  结果: A={pa2.name} HP={max(0,pa2.current_hp)} | B={pb2.name} HP={max(0,pb2.current_hp)}", flush=True)

    # 超时
    winner = check_winner(state)
    if not winner:
        print("\n>>> 平局 (达到最大回合数)!", flush=True)
    EXPERIENCE_B.record_battle(mcts_b.get_action_log(), won=(winner == "b"))
    mcts_b.clear_log()
    return winner


def _hp_bar(current, maximum):
    if maximum <= 0:
        return "[---]"
    pct = max(0, min(100, current / maximum * 100))
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {pct:.0f}%"


def _fmt_mods(p):
    parts = []
    if p.atk_mod > 0: parts.append(f"攻+{p.atk_mod}")
    if p.spatk_mod > 0: parts.append(f"魔攻+{p.spatk_mod}")
    if p.def_mod > 0: parts.append(f"防+{p.def_mod}")
    if p.spdef_mod > 0: parts.append(f"魔防+{p.spdef_mod}")
    if p.speed_mod > 0: parts.append(f"速+{p.speed_mod}")
    return ", ".join(parts) if parts else "无"


def _fmt_debuffs(p):
    parts = []
    if p.atk_mod < 0: parts.append(f"攻{p.atk_mod}")
    if p.spatk_mod < 0: parts.append(f"魔攻{p.spatk_mod}")
    if p.def_mod < 0: parts.append(f"防{p.def_mod}")
    if p.spdef_mod < 0: parts.append(f"魔防{p.spdef_mod}")
    if p.speed_mod < 0: parts.append(f"速{p.speed_mod}")
    return ", ".join(parts) if parts else "无"


def _skill_effects(s):
    """简要显示技能效果"""
    parts = []
    if s.life_drain > 0: parts.append(f"吸血{s.life_drain*100:.0f}%")
    if s.damage_reduction > 0: parts.append(f"减伤{s.damage_reduction*100:.0f}%")
    if s.self_heal_hp > 0: parts.append(f"回复{s.self_heal_hp*100:.0f}%HP")
    if s.self_heal_energy > 0: parts.append(f"回{s.self_heal_energy}能")
    if s.poison_stacks > 0: parts.append(f"中毒{s.poison_stacks}层")
    if s.burn_stacks > 0: parts.append(f"灼烧{s.burn_stacks}层")
    if s.freeze_stacks > 0: parts.append(f"冻结{s.freeze_stacks}层")
    if s.hit_count > 1: parts.append(f"{s.hit_count}连击")
    if s.force_switch: parts.append("脱离")
    if s.agility: parts.append("迅捷")
    if s.charge: parts.append("蓄力")
    if s.damage_reduction > 0:  # 防御型技能默认有应对
        has_counter = (s.counter_physical_power_mult > 0 or s.counter_physical_drain > 0
                       or s.counter_physical_self_atk != 0 or s.counter_physical_enemy_def != 0
                       or s.counter_physical_energy_drain > 0 or s.counter_damage_reflect > 0
                       or s.counter_defense_power_mult > 0 or s.counter_defense_self_atk != 0
                       or s.counter_defense_enemy_def != 0 or s.counter_defense_enemy_atk != 0)
        if has_counter:
            parts.append("应对")
    if s.counter_status_power_mult > 0: parts.append("应对状态")
    if s.priority_mod != 0: parts.append(f"先手{'+' if s.priority_mod>0 else ''}{s.priority_mod}")
    if s.self_atk: parts.append(f"攻{'+'if s.self_atk>0 else ''}{int(s.self_atk*100)}%")
    if s.self_def: parts.append(f"防{'+'if s.self_def>0 else ''}{int(s.self_def*100)}%")
    if s.self_spatk: parts.append(f"魔攻{'+'if s.self_spatk>0 else ''}{int(s.self_spatk*100)}%")
    if s.self_speed: parts.append(f"速{'+'if s.self_speed>0 else ''}{int(s.self_speed*100)}%")
    if s.enemy_atk and s.enemy_atk < 0: parts.append(f"敌方攻{int(s.enemy_atk*100)}%")
    if s.enemy_def and s.enemy_def < 0: parts.append(f"敌方防{int(s.enemy_def*100)}%")
    return " | ".join(parts) if parts else ""


def main_menu():
    _ensure_loaded()

    # 加载历史经验
    exp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "experience")
    exp_a_path = os.path.join(exp_dir, "experience_team_a.md")
    exp_b_path = os.path.join(exp_dir, "experience_team_b.md")

    EXPERIENCE_A.load_from_file(exp_a_path)
    EXPERIENCE_B.load_from_file(exp_b_path)
    print(f"  Loaded experience: A={EXPERIENCE_A.size}, B={EXPERIENCE_B.size}", flush=True)

    while True:
        print(flush=True)
        print("=" * 50, flush=True)
        print("  Rokugou Battle AI Simulator v2", flush=True)
        print("  (Skill DB + Counter System + Experience Learning)", flush=True)
        print("=" * 50, flush=True)
        print(f"  Experience: A={EXPERIENCE_A.size} | B={EXPERIENCE_B.size}", flush=True)
        print("  1. Watch single battle (with experience)", flush=True)
        print("  2. Batch simulation (50 games)", flush=True)
        print("  3. Learning experiment (100 games)", flush=True)
        print("  4. Quick test (10 games, no exp)", flush=True)
        print("  5. A vs B: 20 games WITHOUT experience", flush=True)
        print("  6. A vs B: 20 games WITH experience", flush=True)
        print("  7. PLAYER vs AI (with experience) ★", flush=True)
        print("  0. Exit", flush=True)
        print("=" * 50, flush=True)

        try:
            choice = input("Select [0-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            # 退出前保存经验
            EXPERIENCE_A.save_to_file(exp_a_path)
            EXPERIENCE_B.save_to_file(exp_b_path)
            print(f"  Experience saved: A={EXPERIENCE_A.size} ({exp_a_path})", flush=True)
            print(f"  Experience saved: B={EXPERIENCE_B.size} ({exp_b_path})", flush=True)
            print("Bye!", flush=True)
            break
        elif choice == "1":
            run_single_battle(simulations=200, verbose=True)
        elif choice == "2":
            run_batch_simulation(games=50, simulations=100)
        elif choice == "3":
            run_learning_experiment(games=100, simulations=50)
        elif choice == "4":
            run_batch_simulation(games=10, simulations=50, use_experience=False)
        elif choice == "5":
            run_batch_simulation(games=20, simulations=100, use_experience=False)
        elif choice == "6":
            run_batch_simulation(games=20, simulations=100, use_experience=True)
        elif choice == "7":
            run_player_vs_ai(simulations=200)
        else:
            print("Invalid.", flush=True)


if __name__ == "__main__":
    try:
        main_menu()
    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()

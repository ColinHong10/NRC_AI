"""
MCTS AI + 经验学习系统 (v2 - Adversarial MCTS)

修复日志 (2026-03-30):
- [安全] eval() → ast.literal_eval() 防止任意代码执行
- [性能] copy.deepcopy() → BattleState.deep_copy() 提速3-5x
- [重构] 改为对抗MCTS：搜索树交替展开双方节点，敌方不再随机

核心改进：
1. 对抗MCTS：双方交替决策，UCB选择，反向传播交替更新
2. 经验学习：保留跨对战记录机制，改进状态签名
3. 先验引导：用经验数据作为UCB1的先验概率
"""

import sys
import os
import ast
import math
import random
from typing import List, Tuple, Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.models import BattleState, StatusType, StatType
from src.battle import (
    get_actions, execute_full_turn, check_winner, auto_switch, Action
)


# ============================================================
# 经验记忆 - 跨对战学习
# ============================================================
class ExperienceMemory:
    """
    经验记忆系统
    记录 (状态签名, 动作) -> (胜利次数, 总使用次数)
    下次遇到类似状态时，作为MCTS的先验概率
    """

    def __init__(self, decay: float = 0.95):
        # key: (state_key, action_tuple) -> [wins, total]
        self._memory: Dict[Tuple, List[float]] = {}
        self._decay = decay
        self._battle_count = 0

    def state_key(self, state: BattleState, team: str) -> str:
        """
        生成粗化状态签名（v3）
        
        改进：
        - HP 分4档（满/高/低/残）替代精确百分比，泛化能力大幅提升
        - 能量分3档（满/中/低）替代精确数值
        - 存活数差（-5到+5）替代具体 XvY
        - buff 保留正/零/负三档
        - 回合分桶保留（每5回合一档）
        """
        p = state.get_current(team)
        enemy_team_str = "b" if team == "a" else "a"
        e = state.get_current(enemy_team_str)
        
        # HP 分4档：满(=100%) / 高(>60%) / 低(>25%) / 残(<=25%)
        def hp_bucket(pokemon):
            if pokemon.hp <= 0:
                return "死"
            pct = pokemon.current_hp / pokemon.hp
            if pct >= 1.0:
                return "满"
            elif pct > 0.6:
                return "高"
            elif pct > 0.25:
                return "低"
            else:
                return "残"
        
        # 能量分3档：满(>=8) / 中(>=4) / 低(<4)
        def energy_bucket(energy):
            if energy >= 8:
                return "满"
            elif energy >= 4:
                return "中"
            else:
                return "低"
        
        my_team = state.team_a if team == "a" else state.team_b
        enemy_team_list = state.team_b if team == "a" else state.team_a
        my_alive = sum(1 for pk in my_team if not pk.is_fainted)
        enemy_alive = sum(1 for pk in enemy_team_list if not pk.is_fainted)
        alive_diff = my_alive - enemy_alive  # -5 到 +5
        
        # buff 简化为正/零/负三档
        atk_sign = "+" if p.atk_mod > 0 else ("-" if p.atk_mod < 0 else "0")
        def_sign = "+" if p.def_mod > 0 else ("-" if p.def_mod < 0 else "0")
        
        round_bin = min(state.turn // 5, 10)
        
        return (f"{p.name}|{hp_bucket(p)}|{energy_bucket(p.energy)}|{atk_sign}{def_sign}"
                f"|{e.name}|{hp_bucket(e)}|{alive_diff:+d}|{round_bin}")

    def record_action(self, state_key: str, action: Action, score: float):
        """记录一次动作的结果（score: 0.0~1.0 的奖励值）"""
        key = (state_key, action)
        if key not in self._memory:
            self._memory[key] = [0.0, 0.0]
        self._memory[key][1] += 1.0
        self._memory[key][0] += score

    def get_prior(self, state_key: str, action: Action) -> Tuple[float, int]:
        """获取先验概率和样本量（不会创建空条目）"""
        key = (state_key, action)
        if key not in self._memory:
            return 0.5, 0
        w, t = self._memory[key]
        if t < 1:
            return 0.5, 0
        return w / t, int(t)

    def decay(self):
        """衰减旧经验（模拟遗忘），同时清理衰减到极小值的条目"""
        to_delete = []
        for key in self._memory:
            self._memory[key][0] *= self._decay
            self._memory[key][1] *= self._decay
            if self._memory[key][1] < 0.01:
                to_delete.append(key)
        for key in to_delete:
            del self._memory[key]

    def record_battle(self, state_log: List[Tuple[str, Action]], won: bool):
        """
        记录一整场对战的动作序列（位置加权版）
        
        改进：越靠后的决策权重越高。
        赢了最后几步的因果关系更强，输了开头几步的"锅"也更小。
        """
        self._battle_count += 1
        n = len(state_log)
        if n == 0:
            return
        for i, (state_key, action) in enumerate(state_log):
            # 位置权重：从 0.3（开头）到 1.0（结尾）线性增长
            position_weight = 0.3 + 0.7 * (i / max(1, n - 1))
            if won:
                score = position_weight  # 赢：后期决策得分更高
            else:
                score = (1.0 - position_weight) * 0.3  # 输：前期决策不全算坏
            self.record_action(state_key, action, score)
        # 每10场衰减一次
        if self._battle_count % 10 == 0:
            self.decay()

    @property
    def size(self) -> int:
        return len(self._memory)

    def save(self):
        return {
            "battle_count": self._battle_count,
            "memory_size": self.size,
        }

    def save_to_file(self, filepath: str):
        """保存经验到MD文件"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        lines = [
            f"# Experience Memory",
            f"",
            f"- **Battle Count**: {self._battle_count}",
            f"- **Memory Size**: {self.size}",
            f"- **Decay**: {self._decay}",
            f"",
            f"```",
        ]
        for (state_key, action), (wins, total) in self._memory.items():
            if total >= 0.1:
                lines.append(f"{state_key}\t{action}\t{wins:.4f}\t{total:.4f}")
        lines.append("```")
        lines.append("")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def load_from_file(self, filepath: str):
        """从MD文件加载经验"""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            in_code_block = False
            for line in f:
                stripped = line.rstrip("\n").rstrip("\r")
                if stripped.strip() == "```":
                    in_code_block = not in_code_block
                    continue
                if not in_code_block:
                    continue
                parts = stripped.split("\t")
                if len(parts) < 4:
                    continue
                state_key = parts[0]
                action_str = parts[1]
                try:
                    wins = float(parts[2])
                    total = float(parts[3])
                    # 安全修复：ast.literal_eval 替代 eval
                    action = ast.literal_eval(action_str)
                    self._memory[(state_key, action)] = [wins, total]
                except Exception:
                    continue

    def summary(self) -> str:
        """生成经验摘要文本"""
        return f"battles={self._battle_count}, records={self.size}"


# 全局经验库（A队和B队各一个）
EXPERIENCE_A = ExperienceMemory()
EXPERIENCE_B = ExperienceMemory()


# ============================================================
# MCTS 节点（对抗版）
# ============================================================
class MCTSNode:
    """
    对抗MCTS节点。
    每个节点记录"哪一方在这个节点做决策"(active_team)。
    树的层交替为 A 和 B 的决策层。
    """
    __slots__ = ('state', 'parent', 'action', 'children', 'wins', 'visits',
                 'untried', 'active_team')

    def __init__(self, state: BattleState, parent=None, action=None,
                 active_team="a"):
        self.state = state
        self.parent = parent
        self.action = action          # 到达此节点所用的动作
        self.children: List['MCTSNode'] = []
        self.wins = 0.0               # 从 self.team（搜索器所属队伍）视角的胜利数
        self.visits = 0
        self.untried: List[Action] = []
        self.active_team = active_team  # 谁在这个节点做决策

    @property
    def fully_expanded(self):
        return len(self.untried) == 0


# ============================================================
# 对抗 MCTS 搜索器（带经验学习）
# ============================================================
class MCTS:
    """
    对抗MCTS：搜索树中双方交替展开。

    树结构（以 self.team="a" 为例）：
    - root (active_team="a"): 我方决策节点，untried = 我方可选动作
    - root.children[i] (active_team="b"): 对方决策节点（我方已选动作i）
    - root.children[i].children[j] (active_team="a"): 下一回合我方决策节点
      （双方都选完，回合已执行）

    每个"回合"对应树的两层，双方都用 UCB 选择，而非敌方随机。
    """

    def __init__(self, simulations: int = 200, team: str = "a",
                 experience: ExperienceMemory = None,
                 explore_weight: float = 1.4):
        self.simulations = simulations
        self.team = team
        self.enemy_team = "b" if team == "a" else "a"
        self.experience = experience
        self.explore_weight = explore_weight
        self._action_log: List[Tuple[str, Action]] = []

    def get_best_action(self, state: BattleState) -> Action:
        # 性能优化：用 BattleState.deep_copy() 替代 copy.deepcopy()
        root = MCTSNode(state.deep_copy(), active_team=self.team)
        root.untried = get_actions(state, self.team)

        if not root.untried:
            return (-1,)
        if len(root.untried) == 1:
            return root.untried[0]

        state_key = None
        if self.experience:
            state_key = self.experience.state_key(state, self.team)

        for _ in range(self.simulations):
            node = root

            # ---- Selection ----
            while node.fully_expanded and node.children:
                node = self._select_child(node, state_key)

            # ---- Expansion ----
            if node.untried:
                act = node.untried.pop(random.randrange(len(node.untried)))
                new_state = node.state.deep_copy()

                w = check_winner(new_state)
                if w:
                    child = MCTSNode(new_state, node, act,
                                     active_team=node.active_team)
                    child.untried = []
                    node.children.append(child)
                    self._backpropagate(child, w)
                    continue

                if node.active_team == self.team:
                    # 我方刚选了 act，创建对方决策节点
                    child = MCTSNode(new_state, node, act,
                                     active_team=self.enemy_team)
                    child.untried = get_actions(new_state, self.enemy_team)
                    if not child.untried:
                        child.untried = [(-1,)]
                else:
                    # 对方刚选了 act，执行完整回合
                    # node.action = 上一层（我方）选的动作
                    # act = 对方在此节点选的动作
                    my_action = node.action
                    enemy_action = act
                    if self.team == "a":
                        execute_full_turn(new_state, my_action, enemy_action)
                    else:
                        execute_full_turn(new_state, enemy_action, my_action)
                    auto_switch(new_state)

                    child = MCTSNode(new_state, node, act,
                                     active_team=self.team)
                    w2 = check_winner(new_state)
                    if w2:
                        child.untried = []
                        node.children.append(child)
                        self._backpropagate(child, w2)
                        continue
                    child.untried = get_actions(new_state, self.team)
                    if not child.untried:
                        child.untried = [(-1,)]

                node.children.append(child)
                node = child

            # ---- Simulation (随机对局) ----
            winner = self._simulate(node.state)

            # ---- Backpropagation ----
            self._backpropagate(node, winner)

        if not root.children:
            return get_actions(state, self.team)[0]

        # 选访问次数最多的子节点
        best = max(root.children, key=lambda x: x.visits)
        if state_key:
            self._action_log.append((state_key, best.action))

        return best.action

    def _select_child(self, node: MCTSNode, state_key: str = None) -> MCTSNode:
        """UCB1 选择（带经验先验）"""
        best_score = -1
        best_child = None
        is_my_turn = (node.active_team == self.team)

        for child in node.children:
            if child.visits == 0:
                score = float('inf')
            else:
                # 对抗关键：如果是对方的决策层，exploit 要反转
                if is_my_turn:
                    exploit = child.wins / child.visits
                else:
                    exploit = 1.0 - child.wins / child.visits
                explore = math.sqrt(
                    self.explore_weight * math.log(node.visits) / child.visits
                )
                score = exploit + explore

            # 经验先验加成（仅在我方决策层使用）
            if is_my_turn and state_key and self.experience and child.action:
                prior_w, prior_n = self.experience.get_prior(
                    state_key, child.action
                )
                if prior_n > 0 and child.visits > 0:
                    prior_weight = min(prior_n / 20.0, 0.3)
                    current_rate = child.wins / child.visits
                    adjusted = (current_rate * (1 - prior_weight)
                                + prior_w * prior_weight)
                    explore = math.sqrt(
                        self.explore_weight * math.log(node.visits)
                        / child.visits
                    )
                    score = adjusted + explore

            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _simulate(self, state: BattleState, max_rounds: int = 80) -> Optional[str]:
        """快速随机模拟（rollout）"""
        sim_state = state.deep_copy()
        for _ in range(max_rounds):
            w = check_winner(sim_state)
            if w:
                return w
            actions_a = get_actions(sim_state, "a")
            actions_b = get_actions(sim_state, "b")
            if not actions_a:
                return "b"
            if not actions_b:
                return "a"

            if self.experience:
                act_a = self._biased_choice(sim_state, "a", actions_a)
                act_b = self._biased_choice(sim_state, "b", actions_b)
            else:
                act_a = random.choice(actions_a)
                act_b = random.choice(actions_b)

            execute_full_turn(sim_state, act_a, act_b)
        return check_winner(sim_state)

    def _biased_choice(self, state: BattleState, team: str,
                       actions: List[Action]) -> Action:
        """带经验偏好的随机选择（用于模拟阶段）"""
        state_key = self.experience.state_key(state, team)
        scores = []
        for act in actions:
            prior_w, prior_n = self.experience.get_prior(state_key, act)
            if prior_n > 0:
                scores.append((act, prior_w, prior_n))
            else:
                scores.append((act, 0.5, 0))

        total = sum(max(0.1, s[1]) * (1 + s[2] * 0.01) for s in scores)
        r = random.random() * total
        cumul = 0
        for act, w, n in scores:
            cumul += max(0.1, w) * (1 + n * 0.01)
            if cumul >= r:
                return act
        return random.choice(actions)

    def _backpropagate(self, node: MCTSNode, winner: Optional[str]) -> None:
        """反向传播：统一以 self.team 视角记录胜负"""
        while node:
            node.visits += 1
            if winner == self.team:
                node.wins += 1.0
            elif winner:
                node.wins += 0.0
            else:
                node.wins += 0.5  # 平局
            node = node.parent

    def get_action_log(self) -> List[Tuple[str, Action]]:
        """获取本场动作记录"""
        return self._action_log

    def clear_log(self):
        self._action_log = []

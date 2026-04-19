"""
Regression tests for skill bugs:
1. 啮合传递 (Gear Transfer) — POSITION_BUFF only triggers at positions 0/2
2. 折射 (Refraction) — dynamic effects based on carried skill types
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.effect_engine import EffectExecutor
from src.effect_models import E, SkillEffect, SkillTiming
from src.models import BattleState, Pokemon, Skill, Type, SkillCategory
from src.skill_db import get_skill, load_skills

load_skills()


def make_pokemon(
    name="test",
    hp=300,
    attack=120,
    defense=80,
    spatk=120,
    spdef=80,
    speed=100,
    ptype=Type.NORMAL,
    ability="",
    skills=None,
):
    return Pokemon(
        name=name,
        pokemon_type=ptype,
        hp=hp,
        attack=attack,
        defense=defense,
        sp_attack=spatk,
        sp_defense=spdef,
        speed=speed,
        ability=ability,
        skills=skills or [],
    )


def make_state(user, target):
    return BattleState(
        team_a=[user] + [make_pokemon() for _ in range(5)],
        team_b=[target] + [make_pokemon() for _ in range(5)],
        current_a=0,
        current_b=0,
        turn=1,
    )


# ═══════════════════════════════════════════════════════════
#  啮合传递 — POSITION_BUFF 位置判定
# ═══════════════════════════════════════════════════════════


class TestGearTransferPositionBuff:
    """啮合传递 at position 0 or 2 should grant +100% atk; other positions should not."""

    def _make_user_with_gear_at(self, position: int):
        """Create a user with 啮合传递 at the given position index."""
        skill_names = ["双星", "双星", "双星", "双星"]
        skill_names[position] = "啮合传递"
        skills = [get_skill(n) for n in skill_names]
        return make_pokemon(
            name="迷迷箱怪",
            ptype=Type.STEEL,
            skills=skills,
        )

    def test_gear_at_position_0_grants_atk(self):
        """啮合传递 at index 0 (1号位) → atk_up should increase by 1.0"""
        user = self._make_user_with_gear_at(0)
        target = make_pokemon()
        state = make_state(user, target)
        gear_skill = user.skills[0]
        assert gear_skill.name == "啮合传递"

        old_atk_up = user.atk_up
        EffectExecutor.execute_skill(
            state, user, target, gear_skill, gear_skill.effects,
            is_first=True, team="a",
        )
        assert user.atk_up == old_atk_up + 1.0, (
            f"Expected atk_up += 1.0 at position 0, got {user.atk_up}"
        )

    def test_gear_at_position_2_grants_atk(self):
        """啮合传递 at index 2 (3号位) → atk_up should increase by 1.0"""
        user = self._make_user_with_gear_at(2)
        target = make_pokemon()
        state = make_state(user, target)
        gear_skill = user.skills[2]
        assert gear_skill.name == "啮合传递"

        old_atk_up = user.atk_up
        EffectExecutor.execute_skill(
            state, user, target, gear_skill, gear_skill.effects,
            is_first=True, team="a",
        )
        assert user.atk_up == old_atk_up + 1.0, (
            f"Expected atk_up += 1.0 at position 2, got {user.atk_up}"
        )

    def test_gear_at_position_1_no_atk(self):
        """啮合传递 at index 1 (2号位) → atk_up should NOT change"""
        user = self._make_user_with_gear_at(1)
        target = make_pokemon()
        state = make_state(user, target)
        gear_skill = user.skills[1]
        assert gear_skill.name == "啮合传递"

        old_atk_up = user.atk_up
        EffectExecutor.execute_skill(
            state, user, target, gear_skill, gear_skill.effects,
            is_first=True, team="a",
        )
        assert user.atk_up == old_atk_up, (
            f"Expected no atk change at position 1, got {user.atk_up}"
        )

    def test_gear_at_position_3_no_atk(self):
        """啮合传递 at index 3 (4号位) → atk_up should NOT change"""
        user = self._make_user_with_gear_at(3)
        target = make_pokemon()
        state = make_state(user, target)
        gear_skill = user.skills[3]
        assert gear_skill.name == "啮合传递"

        old_atk_up = user.atk_up
        EffectExecutor.execute_skill(
            state, user, target, gear_skill, gear_skill.effects,
            is_first=True, team="a",
        )
        assert user.atk_up == old_atk_up, (
            f"Expected no atk change at position 3, got {user.atk_up}"
        )

    def test_gear_always_grants_speed(self):
        """啮合传递 at any position should grant speed +80%"""
        for pos in range(4):
            user = self._make_user_with_gear_at(pos)
            target = make_pokemon()
            state = make_state(user, target)
            gear_skill = user.skills[pos]

            old_speed_up = user.speed_up
            EffectExecutor.execute_skill(
                state, user, target, gear_skill, gear_skill.effects,
                is_first=True, team="a",
            )
            assert user.speed_up == old_speed_up + 0.8, (
                f"Expected speed_up += 0.8 at position {pos}, got {user.speed_up}"
            )


# ═══════════════════════════════════════════════════════════
#  折射 — 根据携带技能属性动态判断效果
# ═══════════════════════════════════════════════════════════


class TestRefractionDynamic:
    """折射 should apply effects based on the types of OTHER skills the user carries."""

    def _make_user_with_skills(self, other_skill_names: list):
        """Create a user carrying 折射 + specified other skills.
        Padded with extra 折射 copies (excluded by name filter in handler)."""
        refract = get_skill("折射")
        other_skills = [get_skill(n) for n in other_skill_names]
        skills = [refract] + other_skills
        # Pad to 4 skills with extra 折射 (same name → excluded from carry check)
        while len(skills) < 4:
            skills.append(get_skill("折射"))
        return make_pokemon(
            name="白金独角兽",
            ptype=Type.LIGHT,
            skills=skills[:4],
        )

    def test_refract_with_poison_skill(self):
        """Carrying a 毒系 skill → target gains 2 poison stacks"""
        user = self._make_user_with_skills(["毒雾"])  # 毒系技能
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        old_poison = target.poison_stacks
        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.poison_stacks >= old_poison + 2, (
            f"Expected +2 poison stacks, got {target.poison_stacks}"
        )

    def test_refract_with_fire_skill(self):
        """Carrying a 火系 skill → target gains 4 burn stacks"""
        user = self._make_user_with_skills(["引燃"])  # 火系技能
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        old_burn = target.burn_stacks
        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.burn_stacks >= old_burn + 4, (
            f"Expected +4 burn stacks, got {target.burn_stacks}"
        )

    def test_refract_with_ice_skill(self):
        """Carrying a 冰系 skill → target gains 2 freeze stacks"""
        user = self._make_user_with_skills(["冰雹"])  # 冰系技能
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        old_freeze = target.freeze_stacks
        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.freeze_stacks >= old_freeze + 2, (
            f"Expected +2 freeze stacks, got {target.freeze_stacks}"
        )

    def test_refract_with_multiple_types(self):
        """Carrying 毒+火+冰 → target gets poison+burn+freeze"""
        user = self._make_user_with_skills(["毒雾", "引燃", "冰雹"])
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.poison_stacks >= 2, f"Poison: {target.poison_stacks}"
        assert target.burn_stacks >= 4, f"Burn: {target.burn_stacks}"
        assert target.freeze_stacks >= 2, f"Freeze: {target.freeze_stacks}"

    def test_refract_with_no_matching_types(self):
        """Carrying only 光系 skills (same as 折射 itself) → only spatk buff, no status"""
        # 折射 is 光系; if other skills are also 光系, the 光 effect (+40% spatk) triggers
        user = self._make_user_with_skills(["光球", "光球", "光球"])
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        # No poison/burn/freeze from just 光系 skills
        assert target.poison_stacks == 0
        assert target.burn_stacks == 0
        assert target.freeze_stacks == 0
        # But spatk should be buffed
        assert user.spatk_up >= 0.4, f"Expected spatk +0.4, got {user.spatk_up}"

    def test_refract_ghost_drains_energy(self):
        """Carrying a 幽系 skill → target loses 2 energy"""
        user = self._make_user_with_skills(["背袭"])  # 幽系技能
        target = make_pokemon()
        target.energy = 10
        state = make_state(user, target)
        refract = user.skills[0]

        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.energy <= 8, f"Expected energy <= 8, got {target.energy}"

    def test_refract_phantom_meteor(self):
        """Carrying a 幻系 skill → target gains 1 meteor stack"""
        user = self._make_user_with_skills(["错乱"])  # 幻系技能
        target = make_pokemon()
        state = make_state(user, target)
        refract = user.skills[0]

        old_meteor = target.meteor_stacks
        EffectExecutor.execute_skill(
            state, user, target, refract, refract.effects,
            is_first=True, team="a",
        )
        assert target.meteor_stacks >= old_meteor + 1, (
            f"Expected +1 meteor, got {target.meteor_stacks}"
        )

    def test_refract_config_has_correct_tag(self):
        """折射 loaded config should have REFRACT_BY_CARRY tag, not hardcoded status tags"""
        refract = get_skill("折射")
        # Should have DAMAGE + REFRACT_BY_CARRY, not POISON/BURN/FREEZE/METEOR
        has_refract_tag = False
        has_hardcoded_poison = False
        for item in refract.effects:
            tags = item.effects if isinstance(item, SkillEffect) else [item]
            for tag in tags:
                if tag.type == E.REFRACT_BY_CARRY:
                    has_refract_tag = True
                if tag.type == E.POISON:
                    has_hardcoded_poison = True

        assert has_refract_tag, "折射 should use REFRACT_BY_CARRY, not hardcoded status"
        assert not has_hardcoded_poison, "折射 should NOT have hardcoded POISON tag"

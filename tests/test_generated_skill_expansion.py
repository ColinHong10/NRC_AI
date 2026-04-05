"""
Generated skill expansion regressions.

Covers high-frequency description patterns that are now mapped automatically.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.effect_models import E
from src.skill_db import get_skill, load_skills


def _has_tag(skill, tag_type, **params):
    from src.effect_models import SkillEffect
    for item in skill.effects:
        tags = item.effects if isinstance(item, SkillEffect) else [item]
        for tag in tags:
            if tag.type != tag_type:
                continue
            if all(tag.params.get(k) == v for k, v in params.items()):
                return True
    return False


def test_generated_high_frequency_patterns_are_loaded():
    load_skills()

    assert _has_tag(get_skill("伺机而动"), E.NEXT_ATTACK_MOD, power_bonus=70)
    assert _has_tag(get_skill("热身"), E.NEXT_ATTACK_MOD, power_pct=1.0)
    assert _has_tag(get_skill("贪婪"), E.GRANT_LIFE_DRAIN, pct=1.0)
    assert _has_tag(get_skill("求雨"), E.WEATHER, type="rain", turns=8)
    assert _has_tag(get_skill("麻痹"), E.SKILL_MOD, stat="priority", value=-1)
    assert _has_tag(get_skill("过载回路"), E.FORCE_SWITCH)
    assert _has_tag(get_skill("远程访问"), E.FORCE_ENEMY_SWITCH)


if __name__ == "__main__":
    test_generated_high_frequency_patterns_are_loaded()
    print("PASS: generated skill expansion")

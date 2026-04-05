import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.effect_models import E, EffectTag, SkillEffect, SkillTiming
from src.models import Skill, Type, SkillCategory
from src.server import serialize_skill, _skill_tags


def test_serialize_skill_includes_effect_summary():
    skill = Skill(
        name="听桥",
        skill_type=Type.WATER,
        category=SkillCategory.DEFENSE,
        power=0,
        energy_cost=3,
        effects=[
            SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.6})]),
            SkillEffect(SkillTiming.ON_COUNTER, [EffectTag(E.MIRROR_DAMAGE)], {"category": "attack"}),
        ],
    )

    payload = serialize_skill(skill, current_energy=10, cooldown=0)

    assert payload["has_effects"] is True
    assert "减伤60%" in payload["tags"]
    assert any("减伤" in item for item in payload["effect_tags"])
    assert "反弹原始伤害" in payload["effect_summary"]


def test_skill_tags_reads_effects():
    skill = Skill(
        name="毒液渗透",
        skill_type=Type.POISON,
        category=SkillCategory.MAGICAL,
        power=90,
        energy_cost=6,
        effects=[
            EffectTag(E.ENERGY_COST_DYNAMIC, {"per": "enemy_poison", "reduce": 1}),
            EffectTag(E.DAMAGE),
            EffectTag(E.POISON, {"stacks": 1}),
        ],
    )

    tags = _skill_tags(skill)

    assert "动态减耗" in "".join(tags)
    assert "中毒×1" in tags
    assert "造成伤害" in tags


if __name__ == "__main__":
    test_serialize_skill_includes_effect_summary()
    test_skill_tags_reads_effects()
    print("PASS")

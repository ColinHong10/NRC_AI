import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_skill_effects import generate_mapping, load_rows, tags_for_row
from src.effect_models import E
from src.skill_effects_generated import SKILL_EFFECTS_GENERATED


def _has_tag(tags, tag_type, **params):
    for tag in tags:
        if tag.type != tag_type:
            continue
        if all(tag.params.get(key) == value for key, value in params.items()):
            return True
    return False


def test_coverage_regeneration_threshold():
    _, stats = generate_mapping(load_rows())
    assert stats.generated_nonempty >= 410
    assert stats.covered_total >= 450


def test_lifedrain_and_granted_lifedrain_patterns():
    rows = {row["name"]: row for row in load_rows()}
    steal = tags_for_row(rows["汲取"])
    greed = SKILL_EFFECTS_GENERATED["贪婪"]

    assert "T(E.DAMAGE)" in steal
    assert "T(E.LIFE_DRAIN, pct=1.0)" in steal
    assert _has_tag(greed, E.GRANT_LIFE_DRAIN, pct=1.0)


def test_next_attack_global_mod_and_hit_count_patterns():
    ambush = SKILL_EFFECTS_GENERATED["伺机而动"]
    focus = SKILL_EFFECTS_GENERATED["化劲"]
    warmup = SKILL_EFFECTS_GENERATED["热身运动"]

    assert _has_tag(ambush, E.NEXT_ATTACK_MOD, power_bonus=70)
    assert _has_tag(focus, E.SKILL_MOD, target="self", stat="power_pct", value=0.4)
    assert _has_tag(warmup, E.SKILL_MOD, target="self", stat="hit_count", value=3)


def test_cleanse_buff_and_switch_patterns():
    ritual = SKILL_EFFECTS_GENERATED["洗礼"]
    sun = SKILL_EFFECTS_GENERATED["晒太阳"]
    remote = SKILL_EFFECTS_GENERATED["远程访问"]

    assert _has_tag(ritual, E.CLEANSE, target="self", mode="debuffs")
    assert _has_tag(ritual, E.SKILL_MOD, target="self", stat="cost", value=-1)
    assert _has_tag(sun, E.CLEANSE, target="enemy", mode="buffs")
    assert _has_tag(remote, E.FORCE_ENEMY_SWITCH)


def test_combined_stat_patterns():
    rows = {row["name"]: row for row in load_rows()}
    harvest = tags_for_row(rows["丰饶"])
    sharp_eye = tags_for_row(rows["锐利眼神"])
    courage = SKILL_EFFECTS_GENERATED["三鼓作气"]

    assert "T(E.SELF_BUFF, atk=1.3, spatk=1.3)" in harvest
    assert 'T(E.ENEMY_DEBUFF, {"def": 1.2}, spdef=1.2)' in sharp_eye
    assert _has_tag(courage, E.SELF_BUFF, atk=0.3)


def test_delayed_or_one_shot_priority_gaps_are_not_faked():
    forced_restart = SKILL_EFFECTS_GENERATED["强制重启"]
    guarded = SKILL_EFFECTS_GENERATED["有效预防"]

    assert _has_tag(forced_restart, E.DAMAGE)
    assert not _has_tag(forced_restart, E.FORCE_ENEMY_SWITCH)
    assert not _has_tag(guarded, E.SKILL_MOD, target="self", stat="priority", value=1)


def test_counter_interrupt_pattern_is_generated():
    skill = SKILL_EFFECTS_GENERATED["硬门"]

    assert any(
        tag.type == E.COUNTER_ATTACK
        and any(sub.type == E.INTERRUPT for sub in tag.sub_effects)
        for tag in skill
    )


if __name__ == "__main__":
    test_coverage_regeneration_threshold()
    test_lifedrain_and_granted_lifedrain_patterns()
    test_next_attack_global_mod_and_hit_count_patterns()
    test_cleanse_buff_and_switch_patterns()
    test_combined_stat_patterns()
    test_delayed_or_one_shot_priority_gaps_are_not_faked()
    test_counter_interrupt_pattern_is_generated()
    print("PASS: generated skill effect patterns")

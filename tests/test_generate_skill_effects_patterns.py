import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_skill_effects import generate_mapping, load_rows, tags_for_row
from src.effect_models import E, SkillEffect, SkillTiming
from src.skill_effects_generated import SKILL_EFFECTS_GENERATED


def _u(raw):
    """Decode \\uXXXX escape sequences."""
    return raw.encode("raw_unicode_escape").decode("unicode_escape")


def _has_tag(effects, tag_type, **params):
    """Check if any EffectTag in effects (SkillEffect list or EffectTag list) matches."""
    for item in effects:
        tags = item.effects if isinstance(item, SkillEffect) else [item]
        for tag in tags:
            if tag.type != tag_type:
                continue
            if all(tag.params.get(key) == value for key, value in params.items()):
                return True
    return False


def _has_counter(effects, category, tag_type=None, **params):
    """Check if effects contain an ON_COUNTER SE with given category and optional sub-tag."""
    for item in effects:
        if not isinstance(item, SkillEffect):
            continue
        if item.timing != SkillTiming.ON_COUNTER:
            continue
        if item.filter.get("category") != category:
            continue
        if tag_type is None:
            return True
        for tag in item.effects:
            if tag.type != tag_type:
                continue
            if all(tag.params.get(k) == v for k, v in params.items()):
                return True
    return False


def _has_se_tag(se_entries, tag_str):
    """Check if a tag string appears in any SE entry's rendered tags (for tags_for_row output)."""
    for entry in se_entries:
        for t in entry.tags:
            if tag_str in t:
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

    assert _has_se_tag(steal, "E.DAMAGE")
    assert _has_se_tag(steal, "E.LIFE_DRAIN")
    assert _has_tag(greed, E.GRANT_LIFE_DRAIN, pct=1.0)


def test_next_attack_global_mod_and_hit_count_patterns():
    ambush = SKILL_EFFECTS_GENERATED["伺机而动"]
    focus = SKILL_EFFECTS_GENERATED["化劲"]
    warmup = SKILL_EFFECTS_GENERATED["热身运动"]
    triple_break = SKILL_EFFECTS_GENERATED["三连破"]
    courage = SKILL_EFFECTS_GENERATED["三鼓作气"]

    assert _has_tag(ambush, E.NEXT_ATTACK_MOD, power_bonus=70)
    assert _has_tag(focus, E.SKILL_MOD, target="self", stat="power_pct", value=0.4)
    assert _has_tag(warmup, E.SKILL_MOD, target="self", stat="hit_count", value=3)
    assert _has_tag(triple_break, E.SELF_BUFF, atk=0.3)
    assert _has_tag(triple_break, E.SKILL_MOD, target="self", stat="hit_count", value=3)
    assert _has_tag(courage, E.SELF_BUFF, atk=0.3)
    assert _has_tag(courage, E.SKILL_MOD, target="self", stat="hit_count", value=3)


def test_cleanse_buff_and_switch_patterns():
    ritual = SKILL_EFFECTS_GENERATED["洗礼"]
    sun = SKILL_EFFECTS_GENERATED["晒太阳"]
    remote = SKILL_EFFECTS_GENERATED["远程访问"]
    quick_move = SKILL_EFFECTS_GENERATED["快速移动"]
    disrupt = SKILL_EFFECTS_GENERATED["精神扰乱"]

    assert _has_tag(ritual, E.CLEANSE, target="self", mode="debuffs")
    assert _has_tag(ritual, E.SKILL_MOD, target="self", stat="cost", value=-1)
    assert _has_tag(sun, E.CLEANSE, target="enemy", mode="buffs")
    assert _has_tag(remote, E.FORCE_ENEMY_SWITCH)
    assert _has_counter(quick_move, "defense", E.SELF_BUFF, speed=0.7)
    assert _has_counter(disrupt, "defense", E.ENEMY_ENERGY_COST_UP, amount=2)


def test_combined_stat_patterns():
    rows = {row["name"]: row for row in load_rows()}
    harvest = tags_for_row(rows["丰饶"])
    sharp_eye = tags_for_row(rows["锐利眼神"])

    assert _has_se_tag(harvest, "E.SELF_BUFF")
    assert _has_se_tag(sharp_eye, "E.ENEMY_DEBUFF")


def test_delayed_or_one_shot_priority_gaps_are_not_faked():
    forced_restart = SKILL_EFFECTS_GENERATED["强制重启"]
    guarded = SKILL_EFFECTS_GENERATED["有效预防"]

    assert _has_tag(forced_restart, E.DAMAGE)
    assert not _has_tag(forced_restart, E.FORCE_ENEMY_SWITCH)
    assert not _has_tag(guarded, E.SKILL_MOD, target="self", stat="priority", value=1)


def test_counter_interrupt_pattern_is_generated():
    skill = SKILL_EFFECTS_GENERATED["硬门"]
    assert _has_counter(skill, "attack", E.INTERRUPT)


def test_conditional_and_per_use_patterns_are_generated():
    switch_punish = SKILL_EFFECTS_GENERATED["当头棒喝"]
    anti_status = SKILL_EFFECTS_GENERATED["见招拆招"]
    revenge = SKILL_EFFECTS_GENERATED["气势一击"]
    drain = SKILL_EFFECTS_GENERATED["触底强击"]
    pierce = SKILL_EFFECTS_GENERATED["穿膛"]
    pressure = SKILL_EFFECTS_GENERATED["迫近攻击"]
    combo = SKILL_EFFECTS_GENERATED["乘胜追击"]

    assert _has_tag(switch_punish, E.POWER_DYNAMIC, condition="enemy_switch", bonus=150)
    assert _has_tag(anti_status, E.POWER_DYNAMIC, condition="prev_status", bonus=50)
    assert _has_tag(revenge, E.POWER_DYNAMIC, condition="prev_counter_success", bonus=240)
    assert _has_tag(drain, E.POWER_DYNAMIC, condition="energy_zero_after_use", bonus=100)
    assert _has_tag(pierce, E.POWER_DYNAMIC, condition="enemy_energy_leq", threshold=2, multiplier=5.0)
    assert _has_tag(pressure, E.PERMANENT_MOD, target="power", delta=40, trigger="per_use")
    assert _has_tag(combo, E.PERMANENT_MOD, target="hit_count", delta=1, trigger="per_use")


def test_timed_enemy_cost_patterns_are_generated():
    control = SKILL_EFFECTS_GENERATED["操控"]
    noise = SKILL_EFFECTS_GENERATED["聒噪"]
    anger = SKILL_EFFECTS_GENERATED["激怒"]

    assert _has_tag(control, E.ENEMY_ENERGY_COST_UP, amount=7, duration=3, filter="used_skill")
    assert _has_tag(noise, E.ENEMY_ENERGY_COST_UP, amount=3, duration=3, filter="attack")
    assert _has_tag(anger, E.ENEMY_ENERGY_COST_UP, amount=3, duration=3, filter="other_skills")


def test_self_ko_and_per_use_cost_patterns_are_generated():
    comet = SKILL_EFFECTS_GENERATED[_u("\u5f57\u661f")]
    smash = SKILL_EFFECTS_GENERATED[_u("\u91cd\u51fb")]
    cannon = SKILL_EFFECTS_GENERATED[_u("\u6c34\u70ae")]

    assert _has_tag(comet, E.POWER_DYNAMIC, condition="self_missing_hp_step", step_pct=0.05, bonus_per_step=-10)
    assert _has_tag(comet, E.SELF_KO)
    assert _has_tag(smash, E.PERMANENT_MOD, target="cost", delta=1, trigger="per_use")
    assert _has_tag(cannon, E.PERMANENT_MOD, target="cost", delta=-1, trigger="per_use")


def test_hp_threshold_and_cost_reset_patterns_are_generated():
    bite = SKILL_EFFECTS_GENERATED[_u("\u6495\u54ac")]
    focus = SKILL_EFFECTS_GENERATED[_u("\u6c14\u6c89\u4e39\u7530")]

    assert _has_tag(bite, E.SKILL_MOD, target="self", stat="current_hit_count", value=2, condition="self_hp_below", threshold=0.5)
    assert _has_tag(focus, E.SELF_BUFF, atk=1.3)
    assert _has_tag(focus, E.HEAL_HP, pct=0.6)
    assert _has_tag(focus, E.PERMANENT_MOD, target="cost", delta=-3, trigger="per_counter")
    assert _has_tag(focus, E.RESET_SKILL_COST, when="post_use")


if __name__ == "__main__":
    test_coverage_regeneration_threshold()
    test_lifedrain_and_granted_lifedrain_patterns()
    test_next_attack_global_mod_and_hit_count_patterns()
    test_cleanse_buff_and_switch_patterns()
    test_combined_stat_patterns()
    test_delayed_or_one_shot_priority_gaps_are_not_faked()
    test_counter_interrupt_pattern_is_generated()
    test_conditional_and_per_use_patterns_are_generated()
    test_timed_enemy_cost_patterns_are_generated()
    test_self_ko_and_per_use_cost_patterns_are_generated()
    test_hp_threshold_and_cost_reset_patterns_are_generated()
    print("PASS: generated skill effect patterns")

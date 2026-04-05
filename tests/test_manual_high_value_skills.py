"""
Manual high-value skill regressions.

Covers:
1. Direct lifesteal skills that were previously missing from the manual layer.
2. High-value stat/control skills that should be hand-authored instead of
   relying on generated coverage.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.effect_engine import EffectExecutor
from src.effect_models import E
from src.models import BattleState, Type
from src.skill_db import get_skill, load_skills


def make_pokemon(
    name="test",
    hp=300,
    attack=120,
    defense=80,
    spatk=120,
    spdef=80,
    speed=100,
    ptype=Type.DARK,
    skills=None,
):
    from src.models import Pokemon

    return Pokemon(
        name=name,
        pokemon_type=ptype,
        hp=hp,
        attack=attack,
        defense=defense,
        sp_attack=spatk,
        sp_defense=spdef,
        speed=speed,
        skills=skills or [],
    )


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


def test_manual_lifesteal_skills_are_loaded():
    load_skills()
    for name in ["蝙蝠", "汲取"]:
        skill = get_skill(name)
        assert _has_tag(skill, E.DAMAGE)
        assert _has_tag(skill, E.LIFE_DRAIN, pct=1.0)


def test_manual_stat_and_cost_skills_are_loaded():
    load_skills()

    fengrao = get_skill("丰饶")
    assert _has_tag(fengrao, E.SELF_BUFF, atk=1.3, spatk=1.3)

    ruili = get_skill("锐利眼神")
    assert _has_tag(ruili, E.ENEMY_DEBUFF, **{"def": 1.2, "spdef": 1.2})

    yenshui = get_skill("盐水浴")
    assert _has_tag(yenshui, E.PASSIVE_ENERGY_REDUCE, reduce=2, range="all")
    # 盐水浴 now uses SE format: ON_COUNTER with category="defense"
    from src.effect_models import SkillEffect as _SE, SkillTiming as _ST
    counter_ses = [
        se for se in yenshui.effects
        if isinstance(se, _SE) and se.timing == _ST.ON_COUNTER
    ]
    assert len(counter_ses) >= 1
    counter_se = counter_ses[0]
    assert counter_se.filter.get("category") == "defense"
    assert any(
        tag.type == E.PASSIVE_ENERGY_REDUCE
        and tag.params.get("reduce") == 1
        and tag.params.get("range") == "all"
        for tag in counter_se.effects
    )


def test_bat_lifesteal_executes_in_battle():
    load_skills()
    bat = get_skill("蝙蝠")
    attacker = make_pokemon(
        name="bat_user",
        hp=300,
        attack=150,
        defense=80,
        ptype=Type.DARK,
        skills=[bat],
    )
    attacker.current_hp = 180
    defender = make_pokemon(
        name="dummy",
        hp=260,
        defense=90,
        ptype=Type.NORMAL,
        skills=[],
    )
    state = BattleState(team_a=[attacker], team_b=[defender])

    before = attacker.current_hp
    result = EffectExecutor.execute_skill(state, attacker, defender, bat, bat.effects)

    assert result["damage"] > 0
    assert attacker.current_hp > before


if __name__ == "__main__":
    test_manual_lifesteal_skills_are_loaded()
    test_manual_stat_and_cost_skills_are_loaded()
    test_bat_lifesteal_executes_in_battle()
    print("PASS: manual high-value skills")

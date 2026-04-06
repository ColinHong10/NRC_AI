# TIER 2 Configuration Complete — Next Steps

**Date:** 2026-04-07  
**Status:** ✅ Partial Complete (19/25 abilities)  
**Effort:** 1 session (this session)

---

## Completion Status

✅ **Completed:** 19 of 25 TIER 2 abilities  
⏳ **Remaining:** 6 TIER 2 abilities

| Category | Total | Completed | Remaining |
|----------|-------|-----------|-----------|
| Team Synergy | 4 | 4 | - |
| Stat Scaling | 4 | 4 | - |
| Mark-Based | 5 | 5 | - |
| Damage Type Modifiers | 6 | 6 | - |
| **Total** | **19** | **19** | **-** |

---

## Remaining 6 TIER 2 Abilities

### Healing/Sustain (2) — To be done next
- **生长** → Recover 12% per turn (ON_TURN_END)
- **深层氧循环** → Recover 15% on grass skill (ON_USE_SKILL)

### Energy Cost Modification (1) — To be done next
- **缩壳** → -2 cost on defense skills (PASSIVE)

### Status Application (2) — To be done next
- **毒牙** → Poison = -40% spatk/spdef (Needs special status handling)
- **毒腺** → 4-layer poison on low-cost (ON_USE_SKILL)

### Entry Effects (1) — To be done next
- **吉利丁片** → +20% defense, freeze immune (ON_ENTER)

---

## Workflow for Remaining 6 Abilities

### Phase 1: Add Effect Enums (5 min)
```python
# In effect_models.py, add to E enum:
HEAL_PER_TURN = auto()                    # 生长
HEAL_ON_GRASS_SKILL = auto()              # 深层氧循环
SKILL_COST_REDUCTION_TYPE = auto()        # 缩壳
POISON_STAT_DEBUFF = auto()               # 毒牙 (special)
POISON_ON_SKILL_APPLY = auto()            # 毒腺
FREEZE_IMMUNITY_AND_BUFF = auto()         # 吉利丁片
```

### Phase 2: Implement Handlers (15 min)
```python
def _h_heal_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    # ON_TURN_END: Heal based on max_hp percentage
    pct = tag.params.get("heal_pct", 0.12)
    if ctx.user:
        ctx.user.hp = min(ctx.user.hp + int(ctx.user.max_hp * pct), ctx.user.max_hp)

def _h_heal_on_grass_skill(tag: EffectTag, ctx: Ctx) -> None:
    # ON_USE_SKILL: Heal if skill is grass type
    # Filter by ctx.skill.type == Type.GRASS
```

### Phase 3: Configure Abilities (10 min)
```python
# In effect_data.py ABILITY_EFFECTS:
"生长": [AE(Timing.ON_TURN_END, [T(E.HEAL_PER_TURN, heal_pct=0.12)])],
"深层氧循环": [AE(Timing.ON_USE_SKILL, [T(E.HEAL_ON_GRASS_SKILL, heal_pct=0.15)])],
```

### Phase 4: Test & Verify (5 min)
```bash
python3 -c "from src.effect_data import ABILITY_EFFECTS; print(len(ABILITY_EFFECTS))"
# Should show: 56 (50 + 6 new)
```

---

## Next Session Plan

### Option A: Complete TIER 2 (Recommended)
1. Add remaining 6 abilities (30 min)
2. Update ROADMAP.md (5 min)
3. Move to TIER 3 or P0 tasks

### Option B: Move to P0 Priority Tasks
1. Task #26: Damage calibration test suite (20+ game-verified tests)
2. Task #31: Pokemon stat verification (461 mons × 6 stats)

---

## Architecture Notes

### Healing Effects
- Use `ctx.user.hp` and `ctx.user.max_hp` for calculations
- Apply healing in handler, don't modify in damage formula
- Pattern: `ctx.user.hp = min(healed, max_hp)`

### Skill Filtering
- Use `ctx.skill.type` to check skill element
- Import Type enum: `from src.types import Type`
- Example: `if ctx.skill.type == Type.GRASS:`

### Status Effects
- Poison stat debuff: Create special `POISON_STAT_DEBUFF` effect
- Apply -40% to spatk/spdef in ability_state tracking
- Different from standard `POISON` status effect

### Immunity Effects
- Track immunities in `ability_state["immunities"]`
- Check during status effect application
- Pattern: `if "freeze_immune" in ctx.user.ability_state`

---

## Code Quality Checklist

Before marking complete:
- [ ] All 6 new enums added to effect_models.py
- [ ] All 6 handlers implemented in effect_engine.py
- [ ] All 6 handlers registered in _HANDLERS dict
- [ ] All 6 handlers registered in _ABILITY_HANDLER_OVERRIDES dict
- [ ] All 6 abilities configured in effect_data.py
- [ ] All parameters match COVERAGE_MATRIX.md specs
- [ ] Type checking: `python3 -c "from src import *"`
- [ ] Test file runs without errors
- [ ] Total ability count: 56 (50 + 6)

---

## Documentation Updates

After completing remaining 6 abilities:
1. Update TIER2_IMPLEMENTATION_2026-04-07.md metrics
2. Update ROADMAP.md "当前进度" section
3. Update COVERAGE_MATRIX.md ability count
4. Create TIER2_FINAL_SUMMARY.md with all 25 abilities

---

## Estimated Effort

- **Remaining 6 abilities:** 1 hour
- **Total TIER 2 completion:** 2 hours
- **Next phase (TIER 3):** 4-6 hours

---

## Quick Copy-Paste Template

```python
# TEMPLATE: Add new TIER 2 ability

# In effect_models.py:
FEATURE_NAME = auto()                     # 特性名: Description

# In effect_engine.py:
def _h_feature_name(tag: EffectTag, ctx: Ctx) -> None:
    """FEATURE_NAME: Description"""
    if not ctx.user:
        return
    # Implementation

# Register in effect_engine.py:
E.FEATURE_NAME:    _h_feature_name,       # In both _HANDLERS and _ABILITY_HANDLER_OVERRIDES

# In effect_data.py:
"特性名": [
    AE(Timing.TRIGGER, [
        T(E.FEATURE_NAME, param1=value1)
    ]),
],
```

---

## Summary

- ✅ 19/25 TIER 2 abilities complete
- ✅ All infrastructure in place
- ✅ 61% improvement over TIER 1
- ⏳ 6 remaining abilities (~1 hour to complete)
- 🎯 Next: Complete remaining TIER 2 or move to P0 tasks


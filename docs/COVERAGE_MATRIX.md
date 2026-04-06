# Configuration Coverage Matrix — Detailed Breakdown

**Generated:** 2026-04-07

---

## Skills Coverage Summary

### By Configuration Type

| Type | Count | Coverage | Status |
|------|-------|----------|--------|
| **Manual (explicit)** | 59 | 11.9% | ✅ Complete |
| **Generated (auto)** | 413 | 83.4% | ⚠️ 42 empty |
| **Total configured** | 472 | 95.4% | ✅ Good |
| **Unconfigured** | 23 | 4.6% | ⚠️ Edge cases |

### Manual Skills Breakdown (59)

**By Functional Category:**
- Attack/Damage: 35 skills (59%)
- Buff/Debuff: 12 skills (20%)
- Status Effect (poison/burn/mark): 10 skills (17%)
- Healing: 2 skills (3%)

**By Priority Team:**
- Team A (Poison): 18 skills
- Team B (Wing King): 20 skills  
- High-Value: 11 skills
- Marks System: 10 skills

### Generated Skills Breakdown (455)

**Total:** 455 entries
- **With effects:** 413 (91%)
- **Empty []:** 42 (9%)

**Empty Skills Impact:**
- ~8.5% of skill database
- Mostly fantasy-themed skills
- Likely cosmetic/low-priority

---

## Abilities Coverage Summary

### Overall Status

| Metric | Value | Status |
|--------|-------|--------|
| Total abilities | 170 | ✅ |
| Configured | 31 | ⚠️ |
| Unconfigured | 139 | ❌ |
| Coverage | 18.2% | **CRITICAL** |

### Configured Abilities by Category (31)

#### Energy Management (5)
- 养分内循环: +6 energy per turn
- 养分重吸收: +3 energy per turn
- 快充: +10 energy on exit
- 小偷小摸: Steal 2 energy from enemy
- 做噩梦: Steal 3 energy on enemy switch

#### Damage Modifiers (6)
- 不移: +30% power on pure attacks
- 勇敢: +40% power on high-cost skills
- 挺起胸脯: +50% power on 1-cost skills
- 身经百练: +20% power based on counters
- 冰钻: +10% per enemy energy
- 冻土: +10% per ice skill

#### Status Effects (4)
- 溶解扩散: Apply poison based on skill count
- 扩散侵蚀: Apply poison based on mark stacks
- 蚀刻: Convert poison to marks
- 下黑手: 5-layer poison on enemy switch

#### Special Mechanics (7)
- 保卫: Transform after 2 defense counters
- 不朽: Revive after 3 turns
- 哨兵: Speed boost + forced switch
- 预警: Speed boost if threatened
- 向心力: Grant drive + power to positions
- 洁癖: Transfer mods on switch
- 贪婪: Copy opponent mods on switch

#### Passive Effects (4)
- 对流: Invert cost changes
- 乘风连击: +1 hit count per wing skill
- 专注力: +100% attack on switch
- 煤渣草: Burn stacks don't decay

#### System Mechanics (5)
- 绝对秩序: -50% damage from non-weakness skills
- 虚假宝箱: Enemy gets buffs on faint
- 飓风: Shared wing skill effects + MP cost
- More complex: See full descriptions

---

## Unconfigured Abilities (139) — Priority Tiers

### TIER 1: CRITICAL (12 abilities)
**Counter-Success Mechanics** — These modify battle resolution

```
圣火骑士      → Double damage after counter
指挥家        → +20% attack permanent after counter
斗技          → +20 power permanent after counter
思维之盾      → -5 energy cost after counter
野性感官      → +1 speed priority after counter
```

**First-Strike Mechanics** — These modify action speed

```
破空          → +75% power if first strike
顺风          → +50% power if first strike
咔咔冲刺      → +1 hit count if first strike
起飞加速      → First skill gets agility
```

**Turn-End Mechanics** — Critical for passive loops

```
警惕          → Auto-switch at 0 energy
防过载保护    → Auto-switch after any action
星地善良      → Swap ally at 0 energy
```

### TIER 2: HIGH IMPACT (25 abilities)

**Team Synergy**
```
虫群突袭      → +15% stats per other bug
虫群鼓舞      → +10% stats per other bug
壮胆          → +50% attack if bugs in team
振奋虫心      → +5 aff(献) on team kill
```

**Stat Scaling**
```
囤积          → +10% defense per energy
嫁祸          → +2 hits per 25% HP lost
全神贯注      → +100% attack, -20% per action
吸积盘        → +2 meteor marks per turn
```

**Mark-Based**
```
坠星          → +15% power per meteor mark
观星          → +15% power per meteor mark (地系)
月牙雪糕      → Freeze = meteor mark
吟游之弦      → Marks stack (don't replace)
灰色肖像      → Stacks enemy debuffs +3
```

**Damage Type Modifiers**
```
涂鸦          → +50% non-STAB power
目空          → +25% non-light power
绒粉星光      → +100% vs non-weakness
天通地明      → +100% vs pollutant blood
月光审判      → +100% vs leader blood
偏振          → -40% from same-type attacks
```

### TIER 3: MEDIUM IMPACT (40+ abilities)

**Healing/Sustain**
```
生长          → Recover 12% per turn
深层氧循环    → Recover 15% on grass skill
氧循环        → Recover 10% on grass skill
渴求          → +50% lifesteal on enter
仁心          → Recover equal to enemy burn damage
```

**Energy Cost Modification**
```
缩壳          → -2 cost on defense skills
消波块        → -1 cost per water skill
水翼飞升      → -1 cost per water skill
水翼推进      → -1 cost per water skill
洄游          → -1 permanent per charge
```

**Status Application**
```
毒牙          → Poison = -40% spatk/spdef
毒腺          → 4-layer poison on low-cost
毒蘑菇        → Steal 1 energy per turn
生物碱        → 2-layer poison on grass
灵魂灼伤      → Burn for ice, freeze for fire
```

**Entry Effects**
```
图书守卫者    → +50% attack if MP=1
构装契约者    → +50% defense if MP=1
吉利丁片      → +20% defense, freeze immune
美拉德反应    → +20% attack, burn immune
茶多酚        → +20% recovery, parasite immune
```

**Combat Modifiers**
```
倾轧          → 2x effect from cost changes
加个雪球      → Extra freeze on freeze
捉迷藏        → Freeze = +1 energy cost
抓到你了      → +2 freeze on enter, +1 energy cost
```

### TIER 4: SITUATIONAL (50+ abilities)

**Complex Conditions**
```
衡量          → Copy enemy buffs on enter
张弛有度      → +40% attack weekend, +40% defense weekday
得寸进尺      → +100% attack in rain
侵蚀          → +1 hit per poison layer
```

**Team Effects**
```
坚韧铠甲      → +1 aff(献) per attack
花精灵        → +1 aff(献) per turn
系统发育      → Distribute energy/HP to bench
多人宿舍      → Energy can exceed cap
无忧无虑      → Unlimited 萌化 stacks
```

**Skill Filtering**
```
共鸣          → +20 power on 虫鸣
定向精炼      → +10% power on machine/ground
拨浪鼓        → +10 power on poison/cute per status skill
搜刮          → +20% spatk per 聚能 or switch
```

**Mode Interactions**
```
嫉妒          → Use any skill in charge mode
游弋          → Use any skill in charge, +100% def
噼啪！        → +1 use on first skill
```

---

## Coverage by Ability Type

### Currently Configured (31)

```
📊 Distribution:
  Energy Mgmt:     ████░░░ (16%)
  Dmg Modifiers:   ███░░░░ (20%)
  Status Effects:  ███░░░░ (13%)
  Special Mech:    ███░░░░ (23%)
  Passive:         ██░░░░░ (13%)
  System:          ██░░░░░ (16%)
```

### Need Configuration (139)

```
📊 Gaps:
  Counter-Success:  12 (9%)
  First-Strike:      8 (6%)
  Turn-End Loop:     5 (4%)
  Team Synergy:     15 (11%)
  Mark-Based:       12 (9%)
  Stat Scaling:     18 (13%)
  Healing/Sustain:  15 (11%)
  Others:           38 (27%)
```

---

## Configuration Precedence & Conflicts

### Overlaps Between Manual & Generated

**59 manual skills are ALSO in generated:**
- Manual takes precedence if loaded after
- Current load order: generated → manual
- **Action:** Verify load order in skill_db.py

### Duplicate Ability Names

**0 duplicates found**
- All 31 configured abilities are unique
- No conflicting configurations

### Potential Issues

| Issue | Count | Severity | Fix |
|-------|-------|----------|-----|
| Empty skill slots | 42 | Medium | Populate or remove |
| Missing tier-1 abilities | 12 | Critical | Add immediately |
| Data format mismatch | 1 | Low | DB cleanup |

---

## Database Structure Issues

### Skills Table
✅ **Good:** 495 records, consistent structure
⚠️ **Issue:** Some descriptions incomplete

### Pokemon-Ability Mapping
❌ **Problem:** Abilities stored as `"name:description"`
- Makes parsing fragile
- Single `:` entry is garbage data
- Recommend: Split into separate columns

### Recommendation
```sql
-- Current: pokemon.ability = '"Name": "Description"'
-- Better:  
-- pokemon.ability_id → ability_lookup.id
-- ability_lookup.name
-- ability_lookup.description
```

---

## Summary: What's Configured vs What's Missing

```
SKILLS (495 total)
├── Manual (59)           ✅ Explicit configs
├── Generated (413)       ✅ Auto-generated
├── Empty (42)            ⚠️  Null behavior
└── Unconfigured (23)     ❌ Edge cases

ABILITIES (170 total)
├── Configured (31)       ✅ 18.2% coverage
│   ├── Energy Mgmt (5)
│   ├── Dmg Modifiers (6)
│   ├── Status Effects (4)
│   ├── Special Mech (7)
│   ├── Passive (4)
│   └── System (5)
└── Unconfigured (139)    ❌ 81.8% gap
    ├── Tier 1 Critical (12)   👈 DO FIRST
    ├── Tier 2 High (25)       👈 DO SECOND
    ├── Tier 3 Medium (40+)
    └── Tier 4 Situational (50+)
```

---

**Next Steps:**
1. **Immediate:** Configure TIER 1 critical abilities
2. **Week 2:** Fill TIER 2 gaps
3. **Week 3:** Systematically add TIER 3+4
4. **Week 4:** Audit effect_engine.py for actual implementation


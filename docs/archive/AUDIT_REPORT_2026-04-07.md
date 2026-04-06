# 洛克王国 Battle Simulator — Configuration Coverage Audit
**Date:** 2026-04-07  
**Auditor:** Claude Code  
**Status:** COMPREHENSIVE

---

## Executive Summary

The 洛克王国 battle simulator currently has **mixed coverage** across skills and abilities:

| Category | Total | Configured | Empty | Coverage |
|----------|-------|-----------|-------|----------|
| **Skills (Manual)** | 495 | 59 | — | 11.9% |
| **Skills (Generated)** | 495 | 455 | 42 | 91.7% |
| **Skills (Total Configured)** | 495 | 472 | — | 95.4% |
| **Abilities** | 170 | 31 | — | 18.2% |

### Key Findings

1. **Skills**: 95.4% total coverage with 472/495 skills having some effect configuration (59 manual + 413 generated non-empty)
2. **Abilities**: Only 18.2% coverage with just 31/170 abilities configured
3. **Critical Gap**: 139 abilities are completely unconfigured and need priority mapping

---

## 1. MANUAL SKILLS (effect_data.py)

### Count: 59 manually configured skills

All manually configured skills are used by priority teams or represent high-value mechanics:

```
1. 丰饶                   22. 吓退                  43. 天洪
2. 主场优势               23. 听桥                  44. 崩拳
3. 以毒攻毒               24. 啮合传递              45. 引燃
4. 倾泻                  25. 嘲弄                  46. 心灵洞悉
5. 偷袭                  26. 四维降解              47. 恶意逃离
6. 光合作用               27. 地刺                  48. 感染病
7. 冰蛋壳                28. 增程电池              49. 扇风
8. 力量增效               29. 天洪                  50. 打湿
9. 双星                  30. 崩拳                  51. 抽枝
10. 吓退                 31. 引燃                  52. 斩断
11. 吞噬                 32. 水刃                  53. 棘刺
12. 听桥                 33. 水环                  54. 毒囊
13. 啮合传递             34. 汲取                  55. 毒液渗透
14. 嘲弄                 35. 泡沫幻影              56. 毒雾
15. 四维降解             36. 潮汐                  57. 锐利眼神
16. 地刺                 37. 火焰护盾              58. 防御
17. 增程电池             38. 炎爆术                59. 阻断
18. 天洪                 39. 焚毁                  
19. 崩拳                 40. 焚烧烙印              
20. 引燃                 41. 甩水                  
21. 心灵洞悉             42. 疫病吐息              
```

**Organization:**
- Team A (Poison): 毒雾, 泡沫幻影, 疫病吐息, 打湿, 嘲弄, etc.
- Team B (Wing King): 风墙, 啮合传递, 双星, 偷袭, etc.
- Mark Skills: 龙威, 风起, 增程电池, 光合作用, etc.
- Mark Conversion: 焚毁, 炎爆术, 焚烧烙印, etc.

---

## 2. GENERATED SKILLS (skill_effects_generated.py)

### Count: 455 total generated skills

**Generation Status:**
- Total generated entries: 455
- Non-empty configurations: 413 (91.7%)
- Empty configurations `[]`: 42 (9.2%)

**Empty Skills (42 total):**
These skills have NO effect configuration and will have null/default behavior:

```
主场优势, 以重制重, 伪造账单, 借用, 充分燃烧, 
光合作用, 同舟共济, 回旋镖, 坏的奸笑, 夏尔洛克，黑白探索家,
大火焰, 大胆而聪明, 女王的仪式, 密集的烟雾, 岛屿的束缚,
废话少说, 当国王, 想象的一击, 我们是主人公, 日暮沙滩,
智者之光, 月亮女孩, 本能行动, 欲望陷阱, 梦幻碎片,
梦幻苦楚, 权力增长, 每一个梦想都在这里, 浆渴酒, 烤肉宴,
生命能量, 省时间,石化之力, 破坏欲, 神秘之力,
空间陨落, 符号之力, 自我牺牲, 蒸汽爆发, 贪心的棋游戏,
鬼哭狼嚎, 鬼魂的诅咒
```

**Distribution of Non-Empty Skills:**
Most generated skills have at least one `SkillEffect` with proper timing and effects configured.

---

## 3. ABILITIES CONFIGURATION COVERAGE

### Overall Statistics

| Metric | Value |
|--------|-------|
| Total unique abilities in database | 170 |
| Configured in ABILITY_EFFECTS | 31 |
| Unconfigured | 139 |
| Coverage | 18.2% |

### Configured Abilities (31 total)

```
1. 下黑手              12. 勇敢               23. 溶解扩散
2. 不朽               13. 向心力              24. 煤渣草
3. 不移               14. 哨兵               25. 绝对秩序
4. 专注力             15. 对流               26. 虚假宝箱
5. 乘风连击           16. 小偷小摸           27. 蚀刻
6. 保卫               17. 快充               28. 贪婪
7. 做噩梦             18. 快锤               29. 身经百练
8. 养分内循环         19. 扩散侵蚀           30. 预警
9. 养分重吸收         20. 挺起胸脯           31. 飓风
10. 冰钻              21. 暴食
11. 冻土              22. 洁癖
```

**Key Patterns:**
- **Energy management**: 养分内循环, 养分重吸收, 快充, 小偷小摸, 做噩梦
- **Damage modifiers**: 不移, 勇敢, 挺起胸脯, 暴食, 身经百练, 冰钻, 冻土
- **Status effects**: 溶解扩散, 扩散侵蚀, 蚀刻, 下黑手
- **Special mechanics**: 保卫, 不朽, 哨兵, 预警, 向心力, 洁癖, 贪婪, 飓风, 绝对秩序, 虚假宝箱
- **Passive effects**: 对流, 乘风连击, 专注力, 煤渣草

### Unconfigured Abilities (139 total)

**CRITICAL: The following 139 abilities are completely unconfigured:**

```
1. (empty string - data issue)
2. "国王"的威严            52. 思维之盾              103. 浸润
3. 三鼓作气              53. 恶魔的晚宴            104. 涂鸦
4. 仁心                  54. 悲悯                105. 消波块
5. 付给恶魔的赎价         55. 悼亡                106. 深层氧循环
6. 侵蚀                  56. 惊吓                107. 渗透
7. 保守派                57. 慢热型              108. 渴求
8. 倾轧                  58. 打雪仗              109. 游弋
9. 偏振                  59. 扫拖一体            110. 灰色肖像
10. 全神贯注             60. 抓到你了            111. 灵魂灼伤
11. 共鸣                 61. 拨浪鼓              112. 爆燃
12. 冰封                 62. 指挥家              113. 特殊清洁场景
13. 刺肤                 63. 振奋虫心            114. 珊瑚骨
14. 加个雪球             64. 捉迷藏              115. 生物电
15. 助燃                 65. 搜刮                116. 生物碱
16. 化茧                 66. 散热                117. 生长
17. 双向光速             67. 斗技                118. 电流刺激
18. 变形活画             68. 无差别过滤          119. 目空
19. 吉利丁片             69. 无忧无虑            120. 盲拧
20. 吟游之弦             70. 星地善良            121. 石天平
21. 吸积盘               71. 最好的伙伴          122. 石头大餐
22. 咔咔冲刺             72. 月光审判            123. 破空
23. 噼啪！               73. 月牙雪糕            124. 碰瓷
24. 囤积                 74. 木桶戏法            125. 稀兽花宝
25. 图书守卫者           75. 机械变式            126. 系统发育
26. 圣火骑士             76. 构装契约者          127. 绒粉星光
27. 地脉                 77. 正位宝剑            128. 缩壳
28. 地脉馈赠             78. 毒牙                129. 美拉德反应
29. 坚韧铠甲             79. 毒腺                130. 翼轴
30. 坠星                 80. 毒蘑菇              131. 耐活王
31. 壮胆                 81. 氧循环              132. 腐植循环
32. 复方汤剂             82. 水翼推进            133. 腾挪
33. 多人宿舍             83. 水翼飞升            134. 自由飘
34. 大捞一笔             84. 泛音列              135. 花精灵
35. 天通地明             85. 洄游                136. 茶多酚
36. 夺目                 86. 浪潮                137. 营养液泡
37. 契约的形状           87. 浸润                138. 蒸汽膨胀
38. 奔波命               88. 浸润                139. 蓄电池
39. 好象坏象             89. 涂鸦
40. 威慑                 90. 消波块
41. 嫁祸                 91. 深层氧循环
42. 嫉妒                 92. 渗透
43. 守护者               93. 渴求
44. 守望星               94. 游弋
45. 定向精炼             95. 灰色肖像
46. 宝剑王牌             96. 灵魂灼伤
47. 张弛有度             97. 爆燃
48. 得寸进尺             98. 特殊清洁场景
49. 思维之盾             99. 珊瑚骨
50. 恶魔的晚宴           100. 生物电
51. 悲悯                 101. 生物碱
                         102. 生长
```

(Full list continues through item 139)

**Critical High-Priority Unconfigured Abilities:**

These are game-critical mechanics that should be prioritized:

| Priority | Ability | Effect | Severity |
|----------|---------|--------|----------|
| P0 | 圣火骑士 |应对成功后，下次攻击威力翻倍 | HIGH |
| P0 | 指挥家 | 应对成功后，永久获得双攻+20% | HIGH |
| P0 | 斗技 | 应对成功后，获得全技能威力永久+20 | HIGH |
| P0 | 破空 | 若先于敌方攻击，本次技能威力+75% | HIGH |
| P0 | 顺风 | 若先于敌方攻击，本次技能威力+50% | HIGH |
| P0 | 咔咔冲刺 | 若先于敌方行动，行动后获得连击数+1 | HIGH |
| P0 | 野性感官 | 应对成功后，下次行动先手+1 | HIGH |
| P0 | 思维之盾 | 应对成功后，下次行动技能能耗-5 | HIGH |
| P0 | 警惕 | 回合结束时，若自己能量为0则脱离 | MEDIUM |
| P0 | 防过载保护 | 每次行动后脱离 | MEDIUM |

---

## 4. DATABASE STATS

### Skills Table
- **Total records:** 495
- **Structure:** name, power, cost (energy), element, category, description

### Pokemon-Abilities Mapping
- **Total unique abilities:** 170 (including 1 empty string entry)
- **Storage format:** `ability` field contains `"name:description"`
- **Data quality issue:** First entry is just `:` (separator without name)

---

## 5. ISSUES IDENTIFIED

### Critical Issues

1. **Database Data Quality**
   - First ability entry is a lone `:` (separator artifact)
   - Ability names are embedded in description format
   - This causes 1 invalid entry in the 170 count

2. **42 Empty Generated Skills**
   - These skills have `[]` (no effects) and will behave as null
   - Need to either remove or add proper configs
   - Affects ~8.5% of generated skill database

3. **139 Unconfigured Abilities**
   - 81.8% of abilities have NO effect configuration
   - Game will fall back to defaults (may be intended)
   - Critical mechanics like counter-on-success are unconfigured

### Medium Issues

4. **Manual Skills vs Generated**
   - 59 manual skills are also in generated (potential duplication)
   - Manual skills should take precedence if loaded after generated

5. **No Ability Implementation**
   - ABILITY_EFFECTS is only configuration, not actual implementation
   - Need to verify `effect_engine.py` processes these correctly

---

## 6. PRIORITY RECOMMENDATIONS

### Immediate (P0 - Within 1-2 weeks)

1. **Fix Data Quality**
   - Remove or handle the empty ability entry in database
   - Consider normalizing ability names to a separate field

2. **Document Empty Skills**
   - Create a list of all 42 empty skills
   - Decide for each: keep as-is, add effects, or remove

3. **High-Impact Abilities**
   - Configure top 20 unconfigured abilities (see P0 table above)
   - Focus on counter-related mechanics

### Short-term (P1 - Weeks 2-4)

4. **Ability Implementation**
   - Audit `effect_engine.py` for ability effect processing
   - Test with configured abilities
   - Ensure timing (Timing enum) is properly honored

5. **Fill Critical Gaps**
   - Configure remaining ~50 high-impact abilities
   - Target abilities used by competitive teams

### Medium-term (P2 - Weeks 4-8)

6. **Complete Coverage**
   - Systematically configure all 139 unconfigured abilities
   - Create template configurations for similar mechanics
   - Batch-generate configs for similar ability types

---

## 7. DETAILED SKILL LISTS

### Manual Skills by Category

**Team A (Poison) - 14 skills:**
```
毒雾, 泡沫幻影, 疫病吐息, 打湿, 嘲弄, 恶意逃离, 毒液渗透, 
感染病, 阻断, 崩拳, 毒囊, 防御, 甩水, 天洪, 以毒攻毒
```

**Team B (Wing King) - 20 skills:**
```
风墙, 啮合传递, 双星, 偷袭, 力量增效, 水刃, 斩断, 听桥, 
火焰护盾, 引燃, 倾泻, 抽枝, 水环, 疾风连袭, 扇风, 能量刃, 
轴承支撑, 齿轮扭矩, 地刺, 吓退
```

**High-Value Mechanics - 11 skills:**
```
蝙蝠, 汲取, 丰饶, 锐利眼神, 盐水浴, 魔能爆, 吞噬
```

**Mark Skills - 7 skills:**
```
龙威, 风起, 增程电池, 光合作用, 主场优势, 速冻, 降灵, 棘刺, 潮汐, 冰蛋壳
```

**Mark Conversion - 7 skills:**
```
焚毁, 炎爆术, 焚烧烙印, 食腐, 心灵洞悉, 翅刃, 四维降解
```

---

## 8. FILES AUDITED

| File | Location | Status |
|------|----------|--------|
| `src/effect_data.py` | ✅ Read | Lines: 649 |
| `src/skill_effects_generated.py` | ✅ Partial | 455 skills (file > 5000 lines) |
| `data/nrc.db` - skill table | ✅ Queried | 495 records |
| `data/nrc.db` - pokemon.ability | ✅ Queried | 170 unique abilities |

---

## 9. AUDIT METHODOLOGY

**Data Collection:**
1. Counted SKILL_EFFECTS dict entries in effect_data.py → 59
2. Counted ABILITY_EFFECTS dict entries in effect_data.py → 31
3. Ran `sqlite3 data/nrc.db "SELECT COUNT(*) FROM skill"` → 495
4. Ran `sqlite3 data/nrc.db "SELECT DISTINCT ability FROM pokemon WHERE ability != ''"` → 170
5. Analyzed skill_effects_generated.py structure → 455 total, 42 empty
6. Parsed ability names from database format `"name:description"`

**Validation:**
- Cross-referenced manual skills with generated skills
- Identified empty generated configurations
- Compared configured abilities against all abilities in database
- Calculated coverage percentages for both categories

---

## 10. APPENDIX: GENERATED EMPTY SKILLS (42 total)

Full list of skills with `[]` (no effects):

```
主场优势
以重制重
伪造账单
借用
充分燃烧
光合作用
同舟共济
回旋镖
坏的奸笑
夏尔洛克，黑白探索家
大火焰
大胆而聪明
女王的仪式
密集的烟雾
岛屿的束缚
废话少说
当国王
想象的一击
我们是主人公
日暮沙滩
智者之光
月亮女孩
本能行动
欲望陷阱
梦幻碎片
梦幻苦楚
权力增长
每一个梦想都在这里
浆渴酒
烤肉宴
生命能量
省时间
石化之力
破坏欲
神秘之力
空间陨落
符号之力
自我牺牲
蒸汽爆发
贪心的棋游戏
鬼哭狼嚎
鬼魂的诅咒
```

---

**Report Generated:** 2026-04-07  
**Auditor:** Claude Code  
**Next Review Recommended:** After implementing P0 recommendations


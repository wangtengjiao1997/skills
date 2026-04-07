# Worked Example

**Segment**: US portable coffee gadget enthusiasts, ages 25–45

---

## Input

```json
{
  "project_name": "便携式冷萃咖啡机用户需求与市场潜力研究",
  "group_name": "美国便携咖啡爱好者",
  "segment_name": "美国便携咖啡爱好者",
  "segment_bio": "美国居民，年龄25-45岁，拥有并在过去6个月内使用过便携式咖啡器具（AeroPress、Fellow Prismo、Outin Nano等）的资深咖啡爱好者。每周至少制作咖啡3次以上。",
  "demographic": [
    {"content": "Country", "options": [{"content": "United States"}]},
    {"content": "Age", "min": 25, "max": 45}
  ],
  "screener": {
    "sections": [{
      "questions": [
        {
          "content": "Do you own a portable coffee maker?",
          "options": [
            {"content": "Yes, used in the past 6 months", "qualify": true},
            {"content": "No", "qualify": false}
          ]
        },
        {
          "content": "How often do you make coffee per week?",
          "options": [
            {"content": "3+ times", "qualify": true},
            {"content": "1-2 times", "qualify": false},
            {"content": "Never", "qualify": false}
          ]
        }
      ]
    }]
  },
  "sample_size": 1,
  "screen_type": 2
}
```

## Context string (built by skill / script)

```
Project: 便携式冷萃咖啡机用户需求与市场潜力研究
Target group: 美国便携咖啡爱好者
Segment description: 美国居民，年龄25-45岁，拥有并在过去6个月内使用过便携式咖啡器具...
Demographics: Country: United States; Age: 25-45
Screener: Do you own a portable coffee maker? [qualify: Yes, used in the past 6 months] | How often do you make coffee per week? [qualify: 3+ times]
Sample size: 1
Has screener questionnaire
```

## LLM output (9 dimension scores with reasons)

```json
{
  "audience_rarity":    {"score": 7, "reason": "Multi-criteria overlap: US resident + age 25-45 + specific gear ownership + 3+/week usage"},
  "panel_fit":          {"score": 4, "reason": "Coffee enthusiasts are moderately tech-savvy and comfortable with surveys"},
  "topic_engagement":   {"score": 2, "reason": "Personal hobby; respondents are typically eager to discuss and share expertise"},
  "expertise_required": {"score": 6, "reason": "Requires specific product ownership and demonstrated usage habits"},
  "incidence_rate":     {"score": 0.008, "reason": "US 25-45 (~51%) × portable gadget owner (~5%) × 3+/week (~30%) ≈ 0.008"},
  "visibility":         {"score": 0.70, "reason": "Active on Reddit r/coffee, Instagram, and gear review forums"},
  "accessibility":      {"score": 2.2,  "reason": "Reachable via niche communities (Reddit, Facebook Groups for coffee gear)"},
  "verification":       {"score": 2.1,  "reason": "Requires purchase receipt or usage screenshot as behavioral proof"},
  "compliance":         {"score": 1.0,  "reason": "Standard consumer research with no sensitive data"}
}
```

## Computed result

```
MRDI = (1/0.008) × (1/0.70)^0.5 × 2.2^0.5 × 2.1 × 1.0
     = 125.0 × 1.195 × 1.483 × 2.1 × 1.0
     ≈ 460
```

| Field | Value |
|-------|-------|
| **MRDI** | 460 |
| **Segment** | 4 — 困难 Difficult |
| **Price** | $99 |
| **Rule** | MRDI 200–999 → Segment 4; MRDI < 1000 → $99 |

The `scores` and `reasons` are also available as separate flat dicts in the JSON output:

```json
{
  "segment_name": "美国便携咖啡爱好者",
  "scores":  {"audience_rarity": 7, "panel_fit": 4, ..., "incidence_rate": 0.008, ...},
  "reasons": {"audience_rarity": "Multi-criteria overlap: ...", "incidence_rate": "US 25-45 (~51%) × ...", ...},
  "mrdi": 460.0,
  "segment": 4,
  "segment_label": "困难 Difficult",
  "price": "$99"
}
```

---

## CLI usage (script mode)

```bash
# Save the input JSON to a file
python scripts/score.py --input segment.json

# Or pass inline
python scripts/score.py --json '{"segment_name": "US coffee lovers", ...}'

# Batch mode
python scripts/score.py --batch all_segments.json --output results.json
```

---
description: Score a target audience's recruitment difficulty using MRDI (Market Research Difficulty Index). Calls Claude API across 9 dimensions and returns a difficulty score, segment tier (1-5), and pricing ($99/$199).
argument-hint: <JSON or plain description of target audience — project_name, group_name, segment_bio, demographic, screener, sample_size>
---

You are running the MRDI (Market Research Difficulty Index) scorer.

## Instructions

1. Parse the audience information from $ARGUMENTS. Accept either:
   - A plain-text description (infer project/group names from context)
   - A JSON object with fields: `project_name`, `group_name`, `segment_name`, `segment_bio`, `demographic`, `screener`, `sample_size`, `screen_type`

2. Write the Python script below to a temp file `/tmp/mrdi_run.py` with the parsed values filled into `INPUT`, then execute it with `python3 /tmp/mrdi_run.py`.

3. Display the final MRDI score, segment, price, and all 9 dimension scores.

---

## Python script to write and run

```python
#!/usr/bin/env python3
"""MRDI scorer — fully self-contained, no external files needed."""

import json
import os
import sys
import urllib.request

MODEL = "claude-haiku-4-5-20251001"

# ── Embedded system prompt ──
SYSTEM_PROMPT = """You are an expert at estimating recruitment difficulty for online user research panels.

Given a target segment's details, estimate these 9 dimensions:

── LLM Features (1-10 integer) ──

1. **audience_rarity** (1-10)
   How rare is this audience in an online research panel?
   - 1-2: very common (general consumers, online shoppers)
   - 3-4: somewhat common (specific age+interest, e.g. gamers, coffee lovers)
   - 5-6: moderately rare (niche professionals, specific product owners)
   - 7-8: rare (specialized roles, multi-criteria overlap)
   - 9-10: extremely rare (ultra-niche, requires chain of specific conditions)

2. **panel_fit** (1-10)
   How well does this audience match a typical online research panel?
   - 1-2: perfect match (tech-savvy, articulate, motivated by incentives)
   - 3-4: good match (general consumers comfortable with online surveys)
   - 5-6: moderate (some reluctance or low digital engagement)
   - 7-8: poor match (offline-heavy populations, elderly, low-income)
   - 9-10: very poor (minors, institutionalized, no internet access)

3. **topic_engagement** (1-10)
   How willing are qualified participants to discuss this topic?
   - 1-2: highly engaging (personal passions, early adopter stories)
   - 3-4: interesting (product feedback, lifestyle habits)
   - 5-6: neutral (routine behaviors, general opinions)
   - 7-8: low interest (boring tasks, sensitive but not personal)
   - 9-10: aversive (embarrassing, legally risky, emotionally draining)

4. **expertise_required** (1-10)
   Depth of domain knowledge or experience needed.
   - 1-2: none (general opinions, basic usage)
   - 3-4: light (casual user of a product category)
   - 5-6: moderate (regular user with specific habits)
   - 7-8: substantial (professional expertise, years of experience)
   - 9-10: deep specialist (rare craft, proprietary tools, certified skills)

── MRDI Dimensions (float) ──

5. **incidence_rate** (0.001-1.0 float)
   Estimated proportion of QUALIFIED participants in an online research panel.
   Use the MULTIPLICATIVE method: estimate each independent filter's pass rate, then MULTIPLY them.

   Reference panel composition (approximate):
   - US adults 18+: ~100% of panel
   - Age 25-34: ~27% | Age 65+: ~7% | Female: ~50%
   - Bachelor's degree+: ~46% | Graduate degree: ~18%
   - Hispanic: ~12% | Black: ~12% | Asian: ~6%
   - Household income $100K+: ~15% | Self-employed: ~8%
   - Veterans: ~6% | Disabled: ~9%

   Estimation method: multiply independent filters.
   Example 1: "Women 25-34" = 0.50 × 0.27 = 0.135
   Example 2: "Hispanic women 25-44 with bachelor's+" = 0.12 × 0.50 × (0.27+0.24) × 0.46 = 0.014
   Example 3: "Black male veterans 45-65 with disability" = 0.12 × 0.50 × 0.06 × 0.30 × 0.09 = 0.0001

   Scale:
   - 0.20-0.50: single broad filter (one gender, or one age bracket)
   - 0.05-0.20: two filters intersected
   - 0.01-0.05: three filters intersected
   - 0.001-0.01: four+ filters, niche professional + demographic
   - <0.001: extreme intersection (5+ specific conditions)

6. **visibility** (0.05-1.0 float)
   Digital footprint density — can we identify and reach them online?
   - 0.8-1.0: active public profiles (social media, review sites, forums)
   - 0.5-0.7: moderate online presence, findable through ads/communities
   - 0.2-0.5: limited digital traces, privacy-conscious
   - 0.05-0.2: hidden, no public markers

7. **accessibility** (1.0-5.0 float)
   Difficulty of initial contact and recruitment channel.
   - 1.0-1.5: direct panel recruitment, Meta/Google ads
   - 1.5-2.5: need community access (Facebook Groups, Discord, Reddit)
   - 2.5-3.5: need referrals or trust-building
   - 3.5-5.0: need special permits, institutional access, long-term relationships

8. **verification** (1.0-3.5 float)
   Difficulty of verifying the participant actually qualifies.
   - 1.0-1.3: self-report + basic check (age, location)
   - 1.3-1.8: behavioral proof (purchase history, usage screenshots)
   - 1.8-2.5: professional verification (LinkedIn, certifications)
   - 2.5-3.5: multi-step verification (ID + task + reference)

9. **compliance** (1.0-2.5 float)
   Regulatory risk from data sensitivity or protected populations.
   - 1.0: standard consent, non-sensitive data
   - 1.3: consumer behavior data, explicit consent
   - 1.8: health/political/religious data (GDPR Article 9)
   - 2.5: minors or vulnerable groups (COPPA, ethics review)

IMPORTANT: Return ONLY a JSON object with all 9 scores, nothing else.
Example: {"audience_rarity": 5, "panel_fit": 3, "topic_engagement": 4, "expertise_required": 5, "incidence_rate": 0.025, "visibility": 0.6, "accessibility": 1.5, "verification": 1.8, "compliance": 1.0}

Segment details:"""

# ── Input — edit this section ──
INPUT = {
    "project_name": "",
    "group_name": "",
    "segment_name": "",
    "segment_bio": "",
    "demographic": [],
    "screener": {},
    "sample_size": 1,
    "screen_type": 0,
}


def build_context(row):
    parts = [f"Project: {row['project_name']}"]
    if row.get("group_name"):
        parts.append(f"Target group: {row['group_name']}")
    if row.get("segment_name") and row["segment_name"] != row.get("group_name"):
        parts.append(f"Segment: {row['segment_name']}")
    if row.get("segment_bio"):
        parts.append(f"Segment description: {row['segment_bio'][:400]}")

    demo = row.get("demographic", [])
    if demo:
        criteria = []
        for c in demo:
            content = c.get("content", c.get("criteria_id", ""))
            opts = c.get("options", [])
            if opts:
                labels = [o.get("content", "") for o in opts[:5]]
                criteria.append(f"{content}: {', '.join(labels)}")
            elif c.get("min") is not None:
                criteria.append(f"{content}: {c['min']}-{c.get('max', '')}")
        if criteria:
            parts.append(f"Demographics: {'; '.join(criteria)}")

    scr = row.get("screener")
    if scr and isinstance(scr, dict):
        questions = []
        for sec in scr.get("sections", []):
            for q in sec.get("questions", []):
                qtext = q.get("content", "")
                qualify = [o["content"] for o in q.get("options", []) if o.get("qualify")]
                if qualify:
                    questions.append(f"{qtext} [qualify: {', '.join(qualify[:3])}]")
                else:
                    questions.append(qtext)
        if questions:
            parts.append(f"Screener: {' | '.join(questions[:8])}")

    parts.append(f"Sample size: {row.get('sample_size', 0)}")
    if row.get("screen_type") == 2:
        parts.append("Has screener questionnaire")
    return "\n".join(parts)


def call_api(prompt, api_key):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body, method="POST",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    text = result["content"][0]["text"].strip()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def compute_mrdi(scores):
    ir  = max(0.001, scores["incidence_rate"])
    vis = max(0.05,  scores["visibility"])
    acc = max(1.0,   scores["accessibility"])
    ver = max(1.0,   scores["verification"])
    com = max(1.0,   scores["compliance"])
    mrdi = (1 / ir) * (1 / vis) ** 0.5 * acc ** 0.5 * ver * com
    if mrdi < 10:    seg = 1
    elif mrdi < 50:  seg = 2
    elif mrdi < 200: seg = 3
    elif mrdi < 1000: seg = 4
    else:            seg = 5
    return mrdi, seg


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("Error: set ANTHROPIC_API_KEY env var")
        sys.exit(1)

    context = build_context(INPUT)
    full_prompt = SYSTEM_PROMPT + "\n\n" + context

    print("=" * 55)
    print("  MRDI Scorer")
    print("=" * 55)
    print(f"\n[Context]\n{context}\n")
    print("[Calling API] ...")

    scores = call_api(full_prompt, api_key)
    mrdi, seg = compute_mrdi(scores)
    price = "$99" if mrdi < 1000 else "$199"

    print(f"\n[9 Dimensions]\n{json.dumps(scores, indent=2)}")
    print(f"\n[Result]")
    print(f"  MRDI:    {mrdi:.0f}")
    print(f"  Segment: {seg}  (1=极易 → 5=极难)")
    print(f"  Price:   {price}")

    result = {
        "scores": scores,
        "mrdi": round(mrdi, 1),
        "segment": seg,
        "price": price,
    }
    print(f"\n[JSON]\n{json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
```

---

## Usage notes

- Requires `ANTHROPIC_API_KEY` environment variable.
- To switch to a higher-accuracy model, change `MODEL` to `claude-sonnet-4-6` (higher cost, ~0.945 correlation with expert scores).
- Segment tiers: 1 (MRDI < 10, 极易), 2 (< 50), 3 (< 200), 4 (< 1000), 5 (≥ 1000, 极难).
- Price: $99 for segments 1–4, $199 for segment 5.
- MRDI formula: `(1/IR) × (1/visibility)^0.5 × accessibility^0.5 × verification × compliance`

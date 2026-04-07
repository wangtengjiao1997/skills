---
name: mrdi-scorer
description: Score target audience segments for market research recruitment difficulty using the MRDI (Market Research Difficulty Index) framework. Computes 9 LLM-evaluated dimensions, calculates a composite difficulty score, and classifies segments into tiers with pricing. Use when the user wants to estimate panel recruitment difficulty, evaluate research feasibility, price a research project, classify a target group, or score audience complexity. Trigger on mentions of: MRDI, audience scoring, panel difficulty, recruitment difficulty, segment pricing, target group assessment, research feasibility.
---

# MRDI Scorer

Score any target audience segment on 9 dimensions and compute its **Market Research Difficulty Index (MRDI)**, segment tier (1–5), and recommended price. All logic is self-contained — no external files required.

## Input fields

Collect these from the user. Only `segment_name` and at least one demographic filter are required; all other fields improve accuracy.

| Field | Required | Description |
|-------|----------|-------------|
| `project_name` | No | Research project name |
| `group_name` | No | Target group label |
| `segment_name` | Yes | Specific segment name |
| `segment_bio` | No | Free-text description (≤400 chars) |
| `demographic` | Yes | Age, gender, income, ethnicity, occupation, etc. |
| `screener` | No | Qualifying questions and their pass/fail options |
| `sample_size` | No | Number of participants needed |
| `has_screener` | No | Whether a screener questionnaire is used |

---

## Scoring workflow

### Step 1 — Build context string

Assemble the segment information into a plain-text block:

```
Project: {project_name}
Target group: {group_name}
Segment: {segment_name}
Segment description: {segment_bio, truncated to 400 chars}
Demographics: {Age: 25-45; Gender: Female; Income: $75K+; ...}
Screener: {Q1 text [qualify: option A] | Q2 text [qualify: option B]}
Sample size: {n}
Has screener questionnaire        ← include only if screener exists
```

### Step 2 — Score 9 dimensions

Read the full rubric in [prompt.md](prompt.md), then evaluate each dimension for this segment. Score as the expert judge described in the rubric. Use the **multiplicative method** for `incidence_rate` (multiply each independent filter's pass rate).

For each dimension provide **both** a numeric score **and** a one-sentence reason. For `incidence_rate` the reason must show the multiplicative chain (e.g. `0.50 × 0.27 × 0.05 ≈ 0.007`).

| # | Dimension | Type | Range | Key driver |
|---|-----------|------|-------|-----------|
| 1 | `audience_rarity` | int | 1–10 | How rare is this audience in an online panel? |
| 2 | `panel_fit` | int | 1–10 | How well do they match a typical panel profile? |
| 3 | `topic_engagement` | int | 1–10 | Willingness to participate in this study? |
| 4 | `expertise_required` | int | 1–10 | Domain knowledge / experience depth needed? |
| 5 | `incidence_rate` | float | 0.001–1.0 | Proportion of panel that qualifies |
| 6 | `visibility` | float | 0.05–1.0 | Digital footprint — can we find them online? |
| 7 | `accessibility` | float | 1.0–5.0 | Difficulty of initial contact / recruitment channel |
| 8 | `verification` | float | 1.0–3.5 | Difficulty of confirming they actually qualify |
| 9 | `compliance` | float | 1.0–2.5 | Regulatory / data sensitivity risk |

### Step 3 — Compute MRDI

Apply floors first, then compute:

```
ir  = max(0.001, incidence_rate)
vis = max(0.05,  visibility)
acc = max(1.0,   accessibility)
ver = max(1.0,   verification)
com = max(1.0,   compliance)

MRDI = (1/ir) × (1/vis)^0.5 × acc^0.5 × ver × com
```

### Step 4 — Classify segment and price

| MRDI range | Segment | Label | Price |
|------------|---------|-------|-------|
| < 10 | 1 | 极易 Very Easy | $99 |
| 10 – 49 | 2 | 容易 Easy | $99 |
| 50 – 199 | 3 | 适中 Moderate | $99 |
| 200 – 999 | 4 | 困难 Difficult | $99 |
| ≥ 1000 | 5 | 极难 Very Hard | $199 |

### Step 5 — Present results

```
## MRDI Score Report — {segment_name}

### Dimension Scores
| Dimension          | Score  | Reason                                      |
|--------------------|--------|---------------------------------------------|
| Audience Rarity    | {}/10  | {reason}                                    |
| Panel Fit          | {}/10  | {reason}                                    |
| Topic Engagement   | {}/10  | {reason}                                    |
| Expertise Required | {}/10  | {reason}                                    |
| Incidence Rate     | {}     | {multiplicative chain, e.g. 0.50×0.27≈0.14} |
| Visibility         | {}     | {reason}                                    |
| Accessibility      | {}     | {reason}                                    |
| Verification       | {}     | {reason}                                    |
| Compliance         | {}     | {reason}                                    |

### Result
- **MRDI**: {value}
- **Segment**: {1-5} — {label}
- **Price**: {$99 / $199}
```

---

## Batch / automation mode

To score segments from a JSON file using the Anthropic API directly, run the standalone script (requires `ANTHROPIC_API_KEY`):

```bash
# Score a single segment
python scripts/score.py --input segment.json

# Score multiple segments in a batch
python scripts/score.py --batch segments.json

# Score inline JSON
python scripts/score.py --json '{"segment_name": "US coffee lovers", ...}'
```

See [scripts/score.py](scripts/score.py) for full usage. The script is fully self-contained.

## Additional resources

- Scoring rubric (full): [prompt.md](prompt.md)
- Worked example: [example.md](example.md)

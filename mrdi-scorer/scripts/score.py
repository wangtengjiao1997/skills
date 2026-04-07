#!/usr/bin/env python3
"""
MRDI Scorer — standalone CLI tool

Scores one or more audience segments using Claude and computes the
Market Research Difficulty Index (MRDI), segment tier (1-5), and price.

No external files required. All logic and prompts are embedded.

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."

  # Score a single segment from a JSON file
  python score.py --input segment.json

  # Score multiple segments from a JSON array file
  python score.py --batch segments.json

  # Score inline JSON string
  python score.py --json '{"segment_name": "US coffee lovers", ...}'

Input JSON schema (single segment):
  {
    "project_name":  "Study name",             # optional
    "group_name":    "Target group label",     # optional
    "segment_name":  "Specific segment",       # required
    "segment_bio":   "Free-text description",  # optional, truncated to 400 chars
    "demographic": [                           # required (at least one filter)
      {"content": "Age", "min": 25, "max": 45},
      {"content": "Gender", "options": [{"content": "Female"}]},
      {"criteria_id": "income", "content": "Household Income",
       "options": [{"content": "$75K+"}]}
    ],
    "screener": {                              # optional
      "sections": [{
        "questions": [{
          "content": "Do you own a portable coffee maker?",
          "options": [
            {"content": "Yes", "qualify": true},
            {"content": "No",  "qualify": false}
          ]
        }]
      }]
    },
    "sample_size": 50,                         # optional
    "screen_type": 2                           # optional: 2 = has screener
  }

Batch mode: JSON file must contain an array of segment objects, e.g.:
  [{"segment_name": "...", ...}, {"segment_name": "...", ...}]
"""

import argparse
import json
import os
import sys
import urllib.request

# ── Model ──────────────────────────────────────────────────────────────────────
MODEL = "claude-haiku-4-5-20251001"

# ── Embedded scoring prompt ────────────────────────────────────────────────────
SCORING_PROMPT = """\
You are an expert at estimating recruitment difficulty for online user research panels.

Given a target segment's details, estimate these 9 dimensions:

── LLM Features (1-10 integer) ──

1. audience_rarity (1-10)
   How rare is this audience in an online research panel?
   1-2: very common (general consumers, online shoppers)
   3-4: somewhat common (specific age+interest, e.g. gamers, coffee lovers)
   5-6: moderately rare (niche professionals, specific product owners)
   7-8: rare (specialized roles, multi-criteria overlap)
   9-10: extremely rare (ultra-niche, requires chain of specific conditions)

2. panel_fit (1-10)
   How well does this audience match a typical online research panel?
   1-2: perfect match (tech-savvy, articulate, motivated by incentives)
   3-4: good match (general consumers comfortable with online surveys)
   5-6: moderate (some reluctance or low digital engagement)
   7-8: poor match (offline-heavy populations, elderly, low-income)
   9-10: very poor (minors, institutionalized, no internet access)

3. topic_engagement (1-10)
   How willing are qualified participants to discuss this topic?
   1-2: highly engaging (personal passions, early adopter stories)
   3-4: interesting (product feedback, lifestyle habits)
   5-6: neutral (routine behaviors, general opinions)
   7-8: low interest (boring tasks, sensitive but not personal)
   9-10: aversive (embarrassing, legally risky, emotionally draining)

4. expertise_required (1-10)
   Depth of domain knowledge or experience needed.
   1-2: none (general opinions, basic usage)
   3-4: light (casual user of a product category)
   5-6: moderate (regular user with specific habits)
   7-8: substantial (professional expertise, years of experience)
   9-10: deep specialist (rare craft, proprietary tools, certified skills)

── MRDI Dimensions (float) ──

5. incidence_rate (0.001-1.0 float)
   Estimated proportion of QUALIFIED participants in an online research panel.
   Use the MULTIPLICATIVE method: estimate each independent filter's pass rate, then MULTIPLY.

   Reference panel composition (US adults 18+):
   Age 25-34: ~27% | Age 35-44: ~24% | Age 45-54: ~20% | Age 65+: ~7%
   Female: ~50% | Bachelor's degree+: ~46% | Graduate degree: ~18%
   Hispanic: ~12% | Black: ~12% | Asian: ~6%
   HHI $100K+: ~15% | Self-employed: ~8% | Veterans: ~6% | Disabled: ~9%

   Scale:
   0.20-0.50: single broad filter (one gender, or one age bracket)
   0.05-0.20: two filters intersected
   0.01-0.05: three filters intersected
   0.001-0.01: four+ filters, niche professional + demographic
   <0.001: extreme intersection (5+ specific conditions)

6. visibility (0.05-1.0 float)
   Digital footprint density — can we identify and reach them online?
   0.8-1.0: active public profiles (social media, review sites, forums)
   0.5-0.7: moderate online presence, findable through ads/communities
   0.2-0.5: limited digital traces, privacy-conscious
   0.05-0.2: hidden, no public markers

7. accessibility (1.0-5.0 float)
   Difficulty of initial contact and recruitment channel.
   1.0-1.5: direct panel recruitment, Meta/Google ads
   1.5-2.5: need community access (Facebook Groups, Discord, Reddit)
   2.5-3.5: need referrals or trust-building
   3.5-5.0: need special permits, institutional access, long-term relationships

8. verification (1.0-3.5 float)
   Difficulty of verifying the participant actually qualifies.
   1.0-1.3: self-report + basic check (age, location)
   1.3-1.8: behavioral proof (purchase history, usage screenshots)
   1.8-2.5: professional verification (LinkedIn, certifications)
   2.5-3.5: multi-step verification (ID + task + reference)

9. compliance (1.0-2.5 float)
   Regulatory risk from data sensitivity or protected populations.
   1.0: standard consent, non-sensitive data
   1.3: consumer behavior data, explicit consent
   1.8: health/political/religious data (GDPR Article 9)
   2.5: minors or vulnerable groups (COPPA, ethics review)

IMPORTANT: Return ONLY a JSON object where each key maps to {"score": <value>, "reason": "<one sentence>"}.
For incidence_rate, the reason must show the multiplicative chain (e.g. "0.50 × 0.27 × 0.05 ≈ 0.007").
Nothing outside the JSON object.

Example:
{
  "audience_rarity":    {"score": 5, "reason": "Niche hobbyist with one product filter"},
  "panel_fit":          {"score": 3, "reason": "Tech-savvy consumers, comfortable with surveys"},
  "topic_engagement":   {"score": 4, "reason": "Lifestyle topic with moderate interest"},
  "expertise_required": {"score": 5, "reason": "Regular user with specific product habits"},
  "incidence_rate":     {"score": 0.025, "reason": "Female (~50%) × age 25-34 (~27%) × product owner (~18%) ≈ 0.024"},
  "visibility":         {"score": 0.6, "reason": "Moderate online presence via forums and review sites"},
  "accessibility":      {"score": 1.5, "reason": "Reachable via Meta ads and niche Facebook groups"},
  "verification":       {"score": 1.8, "reason": "Purchase history screenshot sufficient"},
  "compliance":         {"score": 1.0, "reason": "Standard consumer research, no sensitive data"}
}

Segment details:
"""

SEGMENT_LABELS = {1: "极易 Very Easy", 2: "容易 Easy", 3: "适中 Moderate",
                  4: "困难 Difficult", 5: "极难 Very Hard"}


# ── Context builder ────────────────────────────────────────────────────────────

def build_context(row: dict) -> str:
    """Serialize a segment dict into the plain-text context block."""
    parts = [f"Project: {row.get('project_name', '(unnamed project)')}"]

    group = row.get("group_name", "")
    segment = row.get("segment_name", "")
    if group:
        parts.append(f"Target group: {group}")
    if segment and segment != group:
        parts.append(f"Segment: {segment}")

    bio = row.get("segment_bio", "")
    if bio:
        parts.append(f"Segment description: {bio[:400]}")

    # Demographics
    demo = row.get("demographic", [])
    if demo:
        criteria = []
        for c in demo:
            label = c.get("content") or c.get("criteria_id", "")
            opts = c.get("options", [])
            if opts:
                values = [o.get("content", "") for o in opts[:5] if o.get("content")]
                criteria.append(f"{label}: {', '.join(values)}")
            elif c.get("min") is not None:
                hi = c.get("max", "")
                criteria.append(f"{label}: {c['min']}-{hi}")
        if criteria:
            parts.append(f"Demographics: {'; '.join(criteria)}")

    # Screener
    scr = row.get("screener")
    if scr and isinstance(scr, dict):
        questions = []
        for sec in scr.get("sections", []):
            for q in sec.get("questions", []):
                qtext = q.get("content", "")
                qualifying = [o["content"] for o in q.get("options", [])
                              if o.get("qualify") and o.get("content")]
                if qualifying:
                    questions.append(f"{qtext} [qualify: {', '.join(qualifying[:3])}]")
                else:
                    questions.append(qtext)
        if questions:
            parts.append(f"Screener: {' | '.join(questions[:8])}")

    parts.append(f"Sample size: {row.get('sample_size', 0)}")
    if row.get("screen_type") == 2 or row.get("has_screener"):
        parts.append("Has screener questionnaire")

    return "\n".join(parts)


# ── API call ───────────────────────────────────────────────────────────────────

def call_api(full_prompt: str, api_key: str) -> dict:
    """POST to Anthropic Messages API; return the parsed 9-dimension dict."""
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 900,
        "messages": [{"role": "user", "content": full_prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())

    text = result["content"][0]["text"].strip()
    start = text.index("{")
    end = text.rindex("}") + 1
    return json.loads(text[start:end])


# ── Parse LLM response ────────────────────────────────────────────────────────

def extract_scores(raw: dict) -> tuple[dict, dict]:
    """
    Split the LLM's {dim: {score, reason}} response into two flat dicts:
      scores  — {dim: numeric_value}   used for MRDI formula
      reasons — {dim: reason_string}   stored in result for display
    """
    scores = {}
    reasons = {}
    for dim, val in raw.items():
        if isinstance(val, dict):
            scores[dim] = val["score"]
            reasons[dim] = val.get("reason", "")
        else:
            scores[dim] = val
            reasons[dim] = ""
    return scores, reasons


# ── MRDI formula ───────────────────────────────────────────────────────────────

def compute_mrdi(scores: dict) -> tuple[float, int, str]:
    """
    Apply floors, run MRDI formula, return (mrdi, segment, price).

    Formula: (1/ir) × (1/vis)^0.5 × acc^0.5 × ver × com
    """
    ir  = max(0.001, scores["incidence_rate"])
    vis = max(0.05,  scores["visibility"])
    acc = max(1.0,   scores["accessibility"])
    ver = max(1.0,   scores["verification"])
    com = max(1.0,   scores["compliance"])

    mrdi = (1 / ir) * (1 / vis) ** 0.5 * acc ** 0.5 * ver * com

    if mrdi < 10:
        seg = 1
    elif mrdi < 50:
        seg = 2
    elif mrdi < 200:
        seg = 3
    elif mrdi < 1000:
        seg = 4
    else:
        seg = 5

    price = "$199" if mrdi >= 1000 else "$99"
    return mrdi, seg, price


# ── Score one segment ──────────────────────────────────────────────────────────

def score_segment(row: dict, api_key: str, verbose: bool = True) -> dict:
    """Score a single segment dict. Returns a result dict."""
    context = build_context(row)
    full_prompt = SCORING_PROMPT + "\n" + context

    if verbose:
        name = row.get("segment_name") or row.get("group_name", "(unnamed)")
        print(f"\n{'─'*60}")
        print(f"Scoring: {name}")
        print(f"{'─'*60}")
        print(f"[Context]\n{context}\n")
        print("[Calling API] ...")

    raw = call_api(full_prompt, api_key)
    scores, reasons = extract_scores(raw)
    mrdi, seg, price = compute_mrdi(scores)

    result = {
        "segment_name": row.get("segment_name") or row.get("group_name", ""),
        "scores": scores,
        "reasons": reasons,
        "mrdi": round(mrdi, 1),
        "segment": seg,
        "segment_label": SEGMENT_LABELS[seg],
        "price": price,
    }

    if verbose:
        print(f"[Scores & Reasons]")
        for dim, val in scores.items():
            reason = reasons.get(dim, "")
            print(f"  {dim}: {val}  — {reason}")
        print(f"\n[Result]")
        print(f"  MRDI:    {mrdi:.1f}")
        print(f"  Segment: {seg} — {SEGMENT_LABELS[seg]}")
        print(f"  Price:   {price}")

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MRDI Scorer — compute recruitment difficulty for audience segments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",  metavar="FILE",
                       help="JSON file containing a single segment object")
    group.add_argument("--batch",  metavar="FILE",
                       help="JSON file containing an array of segment objects")
    group.add_argument("--json",   metavar="JSON",
                       help="Inline JSON string of a single segment object")

    parser.add_argument("--output", metavar="FILE",
                        help="Write results to this JSON file (default: stdout)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress output")

    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("Error: set ANTHROPIC_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    # Load input
    if args.input:
        with open(args.input) as f:
            segments = [json.load(f)]
    elif args.batch:
        with open(args.batch) as f:
            segments = json.load(f)
        if not isinstance(segments, list):
            segments = [segments]
    else:
        segments = [json.loads(args.json)]

    # Score
    results = []
    for seg in segments:
        results.append(score_segment(seg, api_key, verbose=not args.quiet))

    # Output
    output = results[0] if len(results) == 1 else results
    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        if not args.quiet:
            print(f"\n[Saved] {args.output}")
    else:
        print(f"\n[JSON Output]\n{output_json}")


if __name__ == "__main__":
    main()

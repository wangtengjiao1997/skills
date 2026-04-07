#!/usr/bin/env python3
"""
MRDI 难度评分 — 单条示例脚本

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  python3 score_one.py
"""

import json
import os
import sys
import urllib.request

# ── 配置 ──
MODEL = "claude-haiku-4-5-20251001"
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompt.txt")

# ── 示例输入 ──
EXAMPLE_INPUT = {
    "project_name": "【trooly】便携式冷萃咖啡机用户需求与市场潜力研究",
    "group_name": "美国便携咖啡爱好者",
    "segment_name": "美国便携咖啡爱好者",
    "segment_bio": (
        "美国居民，年龄25-45岁，拥有并在过去6个月内使用过便携式咖啡器具"
        "（如AeroPress、Fellow Prismo、Outin Nano等）的资深咖啡爱好者。"
        "每周至少制作咖啡3次以上，能够详细描述咖啡制作习惯、便携设备使用场景"
        "（居家、办公室、户外、旅行）以及对不同萃取方式的偏好。"
    ),
    "demographic": [
        {"criteria_id": "country", "content": "Country",
         "options": [{"option_id": "US", "content": "United States"}]},
        {"criteria_id": "age", "content": "Age", "min": 25, "max": 45},
    ],
    "screener": {
        "sections": [{
            "questions": [
                {"content": "你是否拥有便携式咖啡器具？",
                 "options": [{"content": "是", "qualify": True},
                             {"content": "否", "qualify": False}]},
            ]
        }]
    },
    "sample_size": 1,
    "screen_type": 2,
}


def build_context(row):
    """把输入字段拼成 LLM context 文本。"""
    parts = [f"Project: {row['project_name']}"]

    if row.get("group_name"):
        parts.append(f"Target group: {row['group_name']}")
    if row.get("segment_name") and row["segment_name"] != row.get("group_name"):
        parts.append(f"Segment: {row['segment_name']}")
    if row.get("segment_bio"):
        parts.append(f"Segment description: {row['segment_bio'][:400]}")

    # Demographics
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

    # Screener
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
    """调用 Claude API，返回解析后的 JSON dict。"""
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
    """从 9 维度计算 MRDI 和 Segment。"""
    ir = max(0.001, scores["incidence_rate"])
    vis = max(0.05, scores["visibility"])
    acc = max(1.0, scores["accessibility"])
    ver = max(1.0, scores["verification"])
    com = max(1.0, scores["compliance"])

    mrdi = (1 / ir) * (1 / vis) ** 0.5 * acc ** 0.5 * ver * com

    # Segment 分档
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

    return mrdi, seg


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("Error: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    # 1. 加载 prompt
    with open(PROMPT_FILE) as f:
        prompt_template = f.read()

    # 2. 构造 context
    context = build_context(EXAMPLE_INPUT)
    full_prompt = prompt_template + "\n\n" + context

    print("=" * 50)
    print("  MRDI Scoring — Example")
    print("=" * 50)
    print(f"\n[Input Context]\n{context}\n")

    # 3. 调用 LLM
    print("[Calling API] ...")
    scores = call_api(full_prompt, api_key)
    print(f"[LLM Output]\n{json.dumps(scores, indent=2)}\n")

    # 4. 计算 MRDI
    mrdi, seg = compute_mrdi(scores)
    price = "$99" if mrdi < 1000 else "$199"

    print(f"[Result]")
    print(f"  MRDI:    {mrdi:.0f}")
    print(f"  Segment: {seg} (1=极易, 5=极难)")
    print(f"  定价:    {price}")
    print()

    # 5. 预期范围校验
    expected_seg = 4
    ir = scores["incidence_rate"]
    ok = "PASS" if 3 <= seg <= 5 and 0.001 <= ir <= 0.05 else "CHECK"
    print(f"[Sanity Check] {ok}")
    print(f"  预期: Segment 3-5, IR 0.001-0.05 (便携咖啡器具是小众爱好)")
    print(f"  实际: Segment {seg}, IR {ir:.4f}")


if __name__ == "__main__":
    main()

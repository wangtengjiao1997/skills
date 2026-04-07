# MRDI 难度评分 — 接口说明

## 概述

MRDI (Market Research Difficulty Index) 通过 LLM 对目标人群打分，输出 0-1 难度评级，用于招募定价。

## 模型

| 环境 | Model ID | 精度 | 成本 |
|------|----------|------|------|
| 生产 | `claude-haiku-4-5-20251001` | ρ=0.915 | ~$0.001/次 |
| 高精度 | `claude-sonnet-4-20250514` | ρ=0.945 | ~$0.01/次 |

## API 调用

```
POST https://api.anthropic.com/v1/messages

Headers:
  x-api-key: <ANTHROPIC_API_KEY>
  anthropic-version: 2023-06-01
  Content-Type: application/json

Body:
{
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 400,
  "messages": [{"role": "user", "content": "<PROMPT + CONTEXT>"}]
}
```

## Prompt

完整 prompt 见 `prompt.txt`（约 2000 字符）。使用时在 prompt 末尾拼接 segment context。

## 输入 Context

拼在 prompt 后面的 segment 信息，格式如下：

```
Project: 【trooly】便携式冷萃咖啡机用户需求与市场潜力研究
Target group: 美国便携咖啡爱好者
Segment description: 美国居民，年龄25-45岁，拥有并在过去6个月内使用过便携式咖啡器具（如AeroPress等）的资深咖啡爱好者。每周至少制作咖啡3次以上...
Demographics: Age: 25-45; Country: US
Screener: 你是否拥有便携咖啡器具？ [qualify: 是] | 每周制作咖啡频率？ [qualify: 3次以上]
Sample size: 1
Has screener questionnaire
```

Context 所需字段来源：

| 字段 | 来源表 | 说明 |
|------|--------|------|
| project_name | t_projects | 项目名称 |
| group_name | t_project_target_groups | 目标组名称 |
| segment_name | t_segments.name | Segment 名称 |
| segment_bio | t_segments.bio | Segment 描述（最重要的输入） |
| demographic | t_project_target_groups.demographic | JSON，含年龄/性别/国家等筛选条件 |
| screener | t_project_target_groups.screener | JSON，含筛选问卷问题和合格选项 |
| sample_size | t_project_target_groups.sample_size | 需要招募的样本量 |
| screen_type | t_project_target_groups.screen_type | 0=无筛选, 2=有筛选问卷 |

## 输出

LLM 返回一个 JSON，包含 9 个维度：

```json
{
  "audience_rarity": 7,
  "panel_fit": 4,
  "topic_engagement": 2,
  "expertise_required": 6,
  "incidence_rate": 0.008,
  "visibility": 0.70,
  "accessibility": 2.2,
  "verification": 2.1,
  "compliance": 1.0
}
```

### 9 个维度说明

| Key | 类型 | 范围 | 含义 |
|-----|------|------|------|
| audience_rarity | int | 1-10 | 人群稀有度（越大越稀有） |
| panel_fit | int | 1-10 | 与在线 panel 的匹配度（越大越差） |
| topic_engagement | int | 1-10 | 话题参与意愿（越大意愿越低） |
| expertise_required | int | 1-10 | 所需专业深度（越大越深） |
| incidence_rate | float | 0.001-1.0 | Panel 中的发生率（越小越稀有） |
| visibility | float | 0.05-1.0 | 数字足迹可见性（越小越隐蔽） |
| accessibility | float | 1.0-5.0 | 触达难度（越大越难） |
| verification | float | 1.0-3.5 | 身份验证难度（越大越难） |
| compliance | float | 1.0-2.5 | 合规风险（越大风险越高） |

## MRDI 计算公式

```
MRDI = (1/incidence_rate) × (1/visibility)^0.5 × accessibility^0.5 × verification × compliance
```

MRDI 值域通常在 10 ~ 15000 之间。

## Segment 分档 (1-5)

| Segment | MRDI 范围 | 难度 |
|---------|----------|------|
| 1 | 0-10 | 极易 |
| 2 | 10-50 | 容易 |
| 3 | 50-200 | 中等 |
| 4 | 200-1000 | 困难 |
| 5 | 1000+ | 极难 |

## 定价规则

| 条件 | 定价 | 占比 | 7天交付失败率 |
|------|------|------|-------------|
| MRDI < 1000 (Segment 1-4) | $99 | ~61% | ~22% |
| MRDI ≥ 1000 (Segment 5) | $199 | ~39% | ~40% |

## 快速验证

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 score_one.py
```

预期输出（数值会有浮动，范围正确即可）：

```
[LLM Output]
{
  "audience_rarity": 6-7,
  "panel_fit": 3-4,
  "topic_engagement": 2-3,
  "expertise_required": 5-7,
  "incidence_rate": 0.005-0.02,     ← 便携咖啡器具是小众爱好
  "visibility": 0.6-0.8,
  "accessibility": 1.5-2.5,
  "verification": 1.8-2.2,
  "compliance": 1.0
}

[Result]
  MRDI:    100-600
  Segment: 3-4
  定价:    $99
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档 |
| `prompt.txt` | 完整 prompt（拼 context 后直接发给 API） |
| `example.json` | 完整示例数据（input → context → output → MRDI → 定价） |
| `score_one.py` | 可运行的单条评分脚本（零依赖，只需 ANTHROPIC_API_KEY） |

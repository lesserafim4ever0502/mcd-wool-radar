---
name: mcd-wool-radar
description: 麦麦羊毛雷达——基于麦当劳 MCP 的省钱巡检 Skill。用户提到麦当劳领券、麦麦省、积分过期、积分兑换、麦当劳活动/优惠时触发。自动巡检可领券、券包、积分账户（含即将过期积分）、活动日历、抽奖与主题活动，给出兑换建议，并可一键领取麦麦省全部优惠券。
---

# 麦麦羊毛雷达（McD Wool Radar）

一个跑在 WorkBuddy 里的麦当劳省钱巡检 Skill：一句话完成「领券 + 盘点积分 + 查活动」。

## 依赖

- Python 3.8+（零第三方依赖）
- 麦当劳 MCP Token（环境变量 `MCD_MCP_TOKEN`）
- 已按 `mcp-config.example.json` 配置 WorkBuddy 自定义连接器 `mcd-mcp`

## 触发词

- 「麦当劳有什么券可以领」「帮我领麦麦省的券」→ 巡检 / `--claim`
- 「我的麦当劳积分快过期了吗」→ 积分理财建议
- 「麦当劳最近有什么活动」→ 活动日历巡检

## 执行流程

1. **巡检（只读，安全默认）**：
   ```bash
   python skill/radar.py --out report.html
   ```
   依次调用：`now-time-info` → `available-coupons` → `query-my-coupons` →
   `query-my-account` → `mall-points-products` → `campaign-calendar` →
   `query-lottery-info` → `query-party-city`，生成一份 HTML 巡检报告。

2. **积分理财建议**：`points_advisor.py` 将「即将过期积分」与商城商品面额做匹配，
   按「小面额优先、优先兜住过期分」排序输出建议。

3. **一键领券（写操作，需用户明确同意）**：
   ```bash
   python skill/radar.py --claim
   ```
   调用 `auto-bind-coupons` 领取麦麦省全部可领券。**默认不执行**，只有当用户说
   「帮我领券/把券领了」才加 `--claim`。

4. **向用户汇报**：优先转述报告要点（几张券可领、积分是否快过期、本月活动亮点），
   再附上 report.html 链接。

## 安全边界

- 写操作只有 `auto-bind-coupons`（领券），无下单/支付/抽奖类写操作。
- Token 只从环境变量 `MCD_MCP_TOKEN` 读取，绝不写入仓库或日志。
- 接口限流 600 次/分钟，巡检一次共 8 次调用，远低于阈值。

## 推荐 Automation（可选）

每日 09:00 定时巡检并推送：
- 提示词：「运行麦麦羊毛雷达巡检，把 report.html 的要点发给我」
- 依赖：本 Skill 已安装 + MCD_MCP_TOKEN 已配置。

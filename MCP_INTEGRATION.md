# MCP_INTEGRATION.md — 麦当劳 MCP 集成说明

## 实际使用的 MCP Server

- **Server**：麦当劳中国官方 MCP Server（`M-China/mcd-mcp-server`）
- **接入地址**：`https://mcp.mcd.cn`
- **传输协议**：Streamable HTTP
- **鉴权**：`Authorization: Bearer <MCP_TOKEN>`，Token 于 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 控制台免费激活领取

## 本项目实际调用的 Tools

| # | Tool | 用途 | 调用场景 |
|---|---|---|---|
| 1 | `now-time-info` | 获取服务器当前时间 | 每次巡检开头校准时钟，保证"活动是否进行中"判断准确 |
| 2 | `available-coupons` | 麦麦省可领券列表 | 「可领优惠券」板块：展示当前所有可领券 |
| 3 | `query-my-coupons` | 我的券包 | 「我的券包」板块：盘点已持有券及有效期 |
| 4 | `query-my-account` | 积分账户 | 「积分理财」板块：可用积分、**即将过期积分**及过期日期 |
| 5 | `mall-points-products` | 积分商城商品列表 | 「积分理财」板块：获取全部可兑换商品及面额 |
| 6 | `campaign-calendar` | 当月营销活动日历 | 「活动日历」板块：进行中/往期/未来活动 |
| 7 | `query-lottery-info` | 积分抽奖活动信息 | 「积分抽奖」板块：活动状态、奖品池、消耗规则 |
| 8 | `query-party-city` | 主题活动城市列表 | 「主题活动」板块：派对/品鉴会开放城市 |
| 9 | `auto-bind-coupons` | 麦麦省一键领券 | **写操作**：仅在用户显式 `--claim` 时调用 |

## 调用流程

```
radar.py（巡检主流程）
│
├─ McdMcpClient.initialize()          # JSON-RPC initialize 握手 + initialized 通知
│     ├─ protocolVersion: 2025-03-26
│     ├─ capabilities: {}
│     └─ clientInfo: {name: mcd-wool-radar, version: 1.0.0}
│
├─ 串行调用 8 个只读 Tool（见上表 #1–#8）
│     ├─ 每个调用单独 try/catch，失败不中断巡检
│     ├─ HTTP 429（限流）→ 指数退避重试（限流阈值 600 次/分钟，巡检共 8~9 次调用）
│     └─ 返回解析：content[].text → 优先按 JSON 解析，失败则保留原文
│
├─ points_advisor.advise(account, products)
│     └─ 纯本地计算：即将过期积分 × 商城面额 → 兑换建议序列
│
└─ render_html(data) → report.html   # 单文件巡检报告
```

响应解析示例（`query-my-account`）：

```json
{
  "availablePoints": 2500,
  "expiringPoints": 800,
  "expiringDate": "2026-10-30"
}
```

`points_advisor` 会将 `expiringPoints=800` 与商城商品面额匹配，优先推荐 ≤800 分的商品，
避免过期清零（字段名做了多键名兼容，见 `extract_account`）。

## 业务价值

1. **把"碎接口"编排成"一条用户愿意每天跑的闭环"**——单独看，每个 Tool 只是查询；串起来，
   就是"领券—盘点—到期预警—兑换建议"的省钱工作流。
2. **积分沉没成本救星**：官方积分会过期，且没有到期提醒。雷达将"即将过期积分"提升为
   一级告警，并与商城面额自动匹配，把"查—比—换"压缩成一步。
3. **写操作最小化与显式化**：全项目唯一写操作是领券（`auto-bind-coupons`），
   默认关闭、需显式开启，杜绝误下单风险；下单/支付/抽奖类工具一律不碰。
4. **可扩展为定时自动化**：配合 WorkBuddy Automation 每日巡检，即"个人优惠资产管理"。

## 兼容性与限制

- 商城/账户接口返回字段存在版本差异，`extract_*` 系列做了多键名兼容；如遇新命名请提 Issue。
- 主题活动仅展示到城市级（`query-party-city`）；门店级预约流程未纳入巡检，属未来工作。
- 本项目不调用任何下单（`create-order`）、支付或抽奖执行类工具。

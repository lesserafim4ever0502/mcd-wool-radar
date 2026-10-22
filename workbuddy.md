# workbuddy.md — WorkBuddy 开发对话上下文

本项目全程使用腾讯 WorkBuddy 智能体开发（AI 结对编程），以下为本会话的真实开发记录摘编。

> 会话环境：WorkBuddy 桌面端 · Agent 模式 · 2026-10-22

---

## 1. 任务发起

**用户**：
> https://www.workbuddy.link/p/8QYARuAmZ9RgQty3FSzNUs?source=2 你去参加这个活动

**WorkBuddy**：识别出这是 WorkBuddy「1024 造物挑战」程序员节应用创作大赛（麦当劳 × 腾讯 WorkBuddy），
自动完成了三步侦察：
1. 拉取大赛完整规则（M-China/mcd-developer-innovation-challenge 的 activityGuidelines.md）；
2. 拉取麦当劳 MCP Server 文档与全部 Tool 清单（约 30 个工具）；
3. 检查本机环境：GitHub CLI 已登录、git 已配置、WorkBuddy mcp.json 可合并接入。

## 2. 选题讨论

WorkBuddy 分析已有参赛作品后发现「营养计算」「点餐助手」方向扎堆，按"看 Tool 列表里没被用满的数据"思路，
选中被普遍忽略的资产类接口（`query-my-account` 的即将过期积分、`available-coupons`、`auto-bind-coupons`、
`campaign-calendar`、`query-lottery-info`、`query-party-city`），确定选题：

> **麦麦羊毛雷达 mcd-wool-radar** —— 一句话完成「领券 + 盘点积分 + 查活动」的省钱巡检 Skill

设计三原则（由 WorkBuddy 提出，用户默认采纳）：
- **零第三方依赖**：纯标准库实现 MCP Streamable HTTP 客户端，评审克隆即跑；
- **读写分离**：默认只读巡检，唯一写操作领券需显式 `--claim`；
- **一次巡检一份报告**：全部结果汇总为单文件 HTML。

## 3. 开发过程

| 轮次 | WorkBuddy 动作 | 产出 |
|---|---|---|
| 1 | 创建任务清单（4 项：骨架→标准文件→实测→发布报名） | TaskList |
| 2 | 编写零依赖 MCP 客户端：JSON-RPC 封装、SSE 流解析、429 退避重试、会话保持 | `mcd_client.py` |
| 3 | 编写积分到期理财顾问：多键名字段兼容、小面额优先兑换建议 | `points_advisor.py` |
| 4 | 编写巡检主程序：8 接口容错采集 + HTML 报告渲染（麦当劳红金配色） | `radar.py` |
| 5 | 编写 WorkBuddy Skill 定义与触发词 | `skill/SKILL.md` |
| 6 | 语法检查 + 积分理财纯函数自测（构造 2500 分/800 分过期样例，建议输出符合预期） | 通过 |
| 7 | 编写大赛 5 个标准文件：README / CONTEST_DECLARATION / MCP_INTEGRATION / mcp-config.example.json / workbuddy.md | 全部就位 |
| 8 | git 初始化并提交 | 本仓库 |

## 4. 关键技术决策（对话实录摘编）

**用户倾向**：直接推进、少问多做（用户长期偏好：简洁直接、AI 主动排查实操）。

**WorkBuddy 决策记录**：
- 「麦当劳积分会过期清零但没有到期提醒——把"即将过期积分"提升为一级告警，并与商城面额自动匹配，
  把"查—比—换"压缩成一步。」（radar.py 积分理财板块设计动机）
- 「写操作最小化与显式化：全项目唯一写操作是领券，默认关闭。下单/支付/抽奖类工具一律不碰。」
- 「单个接口失败不拖垮巡检，报告中标红展示」→ `safe_call` 容错包装。
- SSE 响应解析：服务端以 `text/event-stream` 返回时逐行剥离 `data:` 前缀再拼 JSON。

## 5. 验证情况

- `python -m py_compile` 三个模块全部通过；
- `points_advisor.advise()` 纯函数单测：可用 2500 分、800 分即将过期（2026-10-30）样例下，
  正确输出 warn 级提醒与 3 条排序兑换建议；
- 真实 MCP 接口联调：待用户提供 MCP Token 后执行（见任务 #3）。

## 6. 后续计划

1. Token 到位后跑通真实巡检，报告截图入 README；
2. `gh repo create` 发布公开仓库；
3. 按官方 Issue 模板向 M-China/mcd-developer-innovation-challenge 提交参赛申请（截止 10-25 23:59）。

---

*本文件按大赛要求记录 WorkBuddy 开发对话上下文，用于 WorkBuddy 专项奖励核验。*

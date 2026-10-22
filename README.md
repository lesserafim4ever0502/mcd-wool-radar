# 🍟 麦麦羊毛雷达 mcd-wool-radar

> 基于麦当劳中国官方 MCP 的省钱巡检 Skill —— 一句话完成「领券 + 盘点积分 + 查活动」。
> 1024 程序员节 · 麦当劳程序员创意开发大赛参赛作品

## 解决什么问题？

麦当劳的优惠散落在四个角落：麦麦省的券要手动领、积分会**默默过期清零**、活动日历没人看、主题活动预约没人盯。普通用户既不知道有，也懒得每天查。

**麦麦羊毛雷达**把这一切自动化：跑一次巡检，8 个官方 MCP 接口扫一遍，生成一份 HTML 巡检报告，告诉你——

- 🎟️ 现在能领哪些券（一键全领）
- 💰 积分还剩多少、**多少分即将过期**、过期前最划算的兑换姿势
- 📅 本月有哪些营销活动（第二件半价、买一送一…）
- 🎡 积分抽奖活动状态与奖品池
- 🎈 派对/品鉴会等主题活动开到了哪些城市

## 核心特性

| 特性 | 说明 |
|---|---|
| **零依赖** | 纯 Python 标准库实现 MCP Streamable HTTP 客户端，克隆即跑，不装任何包 |
| **读写分离** | 默认只巡检（8 个只读接口）；领券等写操作必须显式 `--claim` |
| **积分理财** | 「即将过期积分」自动匹配商城商品面额，按"小面额优先、兜住过期分"给出兑换顺序 |
| **容错设计** | 单个接口失败不拖垮巡检，报告中标红展示；429 限流自动退避重试 |
| **一份报告** | 所有结果汇总为单文件 HTML（麦当劳红金配色），可直接转发 |

## 安装

```bash
git clone https://github.com/lesserafim4ever0502/mcd-wool-radar.git
cd mcd-wool-radar
export MCD_MCP_TOKEN=你的Token   # Windows: set MCD_MCP_TOKEN=xxx
```

Token 获取：打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 手机号登录 → 控制台 → 激活，免费领取。

## 使用示例

```bash
# 1. 日常巡检（只读，生成 report.html）
python radar.py

# 2. 巡检 + 一键领取麦麦省全部可领券
python radar.py --claim

# 3. 只查积分理财建议
python points_advisor.py

# 4. 直接命令行调用任意 MCP 工具
python mcd_client.py --list-tools
python mcd_client.py --call query-my-account
python mcd_client.py --call query-meals '{"storeCode": "xxxx"}'
```

### 作为 WorkBuddy Skill 使用

把 `skill/` 目录安装为 WorkBuddy 技能，之后在 WorkBuddy 里说：

- 「麦当劳有什么券可以领」→ 自动巡检
- 「帮我领麦麦省的券」→ 巡检 + 领券（写操作前会确认）
- 「我的积分快过期了吗」→ 积分理财建议

还可以配置每日 09:00 定时巡检的 Automation，报告要点自动推送。

## 目标用户

- 麦当劳的高频消费者（上班族/学生党）：不想错过任何一张券
- "积分清零党"：月底才发现几千积分过期的惨剧受害者
- 喜欢自动化的折腾党：想用 Agent + 定时任务接管一切重复劳动的人

## 项目结构

```
mcd-wool-radar/
├── radar.py              # 巡检主程序：8 接口巡检 + HTML 报告
├── points_advisor.py     # 积分到期理财顾问
├── mcd_client.py         # 零依赖 MCP Streamable HTTP 客户端
├── skill/
│   └── SKILL.md          # WorkBuddy Skill 定义
├── mcp-config.example.json  # 脱敏 MCP 配置示例
├── MCP_INTEGRATION.md    # MCP 调用流程与业务价值说明
├── CONTEST_DECLARATION.md   # 参赛声明
└── workbuddy.md          # WorkBuddy 开发对话上下文
```

## 声明

本项目为个人非商业开源作品，与麦当劳中国无隶属关系。数据接口来自麦当劳中国官方 MCP Server（mcp.mcd.cn），使用须遵守《麦当劳 MCP 服务规则》。健康饮食，理性消费 🍟

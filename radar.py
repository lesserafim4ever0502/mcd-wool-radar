#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radar.py — 麦麦羊毛雷达：一次巡检，摸清所有可薅的羊毛

巡检内容（全部来自麦当劳 MCP 真实接口）：
  1. 麦麦省：当前可领的优惠券（available-coupons）
  2. 我的券包：已领取的优惠券（query-my-coupons）
  3. 积分账户：可用/即将过期积分 + 兑换建议（query-my-account + mall-points-products）
  4. 活动日历：当月营销活动（campaign-calendar）
  5. 抽奖活动：积分抽奖状态与奖品池（query-lottery-info）
  6. 主题活动：可预约的派对/品鉴会城市（query-party-city）

写操作（默认关闭）：
  --claim   自动领取麦麦省全部可领优惠券（auto-bind-coupons）

用法：
  python radar.py                    # 只巡检，生成 report.html
  python radar.py --claim            # 巡检 + 一键领券
  python radar.py --out my.html      # 指定报告路径
"""
import argparse
import datetime
import html
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import points_advisor
from mcd_client import McpError, McdMcpClient

# 巡检面板：(板块名, [(条目名, 工具名)], 引言)
PANELS = [
    ("麦麦省 · 可领优惠券", [("可领列表", "available-coupons")],
     "下面这些券现在就能领，不领白不领"),
    ("我的券包", [("已持有优惠券", "query-my-coupons")],
     "券包里已有的券，注意有效期别放过期了"),
    ("积分账户", [],
     "积分是会过期的！见下方理财建议"),
    ("活动日历", [("当月营销活动", "campaign-calendar")],
     "麦当劳官方活动日历：第二件半价、买一送一都在这"),
    ("积分抽奖", [("抽奖活动信息", "query-lottery-info")],
     "有富余积分可以试试手气（本雷达不自动抽奖）"),
    ("主题活动", [("可预约城市", "query-party-city")],
     "派对/品鉴会等主题活动的预约入口"),
]


def safe_call(client, tool, args=None):
    """容错调用：失败返回 (None, 错误消息)，不让单个接口挂掉整个巡检。"""
    try:
        parsed, _ = client.call_tool(tool, args)
        return parsed, None
    except McpError as e:
        return None, str(e)
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


def collect(client, claim=False):
    """跑完整巡检，返回结构化结果 dict。"""
    data = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "panels": [], "actions": []}

    # 0. 服务器时间（校准时差）
    t, err = safe_call(client, "now-time-info")
    if t is not None:
        data["server_time"] = t

    # 1~2. 各只读板块
    for title, entries, intro in PANELS:
        if not entries:
            continue
        panel = {"title": title, "intro": intro, "items": []}
        for label, tool in entries:
            parsed, err = safe_call(client, tool)
            panel["items"].append({"label": label, "tool": tool,
                                   "ok": err is None, "error": err, "data": parsed})
        data["panels"].append(panel)

    # 3. 积分理财
    acc_raw, err_acc = safe_call(client, "query-my-account")
    prod_raw, err_prod = safe_call(client, "mall-points-products")
    account = points_advisor.extract_account(acc_raw) if acc_raw is not None else {}
    products = points_advisor.extract_products(prod_raw) if prod_raw is not None else []
    advice = points_advisor.advise(account, products)
    data["panels"].append({
        "title": "积分理财建议", "intro": "按面额从小到大，优先消耗即将过期的积分",
        "items": [
            {"label": "账户概览（query-my-account）", "tool": "query-my-account",
             "ok": err_acc is None, "error": err_acc, "data": acc_raw},
            {"label": "积分商城（mall-points-products，共 %d 件）" % len(products),
             "tool": "mall-points-products", "ok": err_prod is None,
             "error": err_prod, "data": None},
        ],
        "account": account, "advice": advice,
    })

    # 4. 写操作：一键领券
    if claim:
        parsed, err = safe_call(client, "auto-bind-coupons")
        data["actions"].append({"tool": "auto-bind-coupons", "ok": err is None,
                                "error": err, "result": parsed})
    return data


# ---------------- HTML 报告 ----------------

def _esc(x):
    return html.escape(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))


def _count_items(parsed):
    """估算接口返回里的条目数，用于徽标展示。"""
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        for k in ("list", "records", "items", "coupons", "activities", "cities", "data"):
            v = parsed.get(k)
            if isinstance(v, list):
                return len(v)
            if isinstance(v, dict):
                for k2 in ("list", "records", "items", "coupons"):
                    if isinstance(v.get(k2), list):
                        return len(v[k2])
    return None


def render_html(data):
    css = """
    :root{--red:#da291c;--gold:#ffc72c;--ink:#1f2329;--muted:#8a919f;--bg:#f7f7f8;--card:#fff}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--ink);padding:24px}
    .wrap{max-width:860px;margin:0 auto}
    header{background:linear-gradient(135deg,var(--red),#a71d12);color:#fff;border-radius:16px;padding:28px 32px;margin-bottom:20px}
    header h1{font-size:24px;display:flex;align-items:center;gap:10px}
    header p{margin-top:8px;opacity:.9;font-size:13px}
    .panel{background:var(--card);border-radius:14px;padding:20px 24px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
    .panel h2{font-size:16px;display:flex;align-items:center;gap:8px;margin-bottom:6px}
    .panel .intro{font-size:12px;color:var(--muted);margin-bottom:12px}
    .badge{background:var(--gold);color:#5a3e00;border-radius:999px;font-size:11px;padding:2px 10px;font-weight:600}
    .err{color:var(--red);font-size:12px}
    pre{background:#f2f3f5;border-radius:8px;padding:12px;font-size:12px;overflow:auto;max-height:320px;line-height:1.5}
    .advice{border-left:4px solid var(--gold);background:#fffaf0;border-radius:8px;padding:12px 16px;font-size:13px;margin-bottom:10px;white-space:pre-wrap}
    .advice.warn{border-left-color:var(--red);background:#fff2f0}
    .advice.ok{border-left-color:#2e9e5b;background:#f0faf4}
    .meta{font-size:11px;color:var(--muted);margin-top:10px}
    footer{text-align:center;color:var(--muted);font-size:11px;margin-top:24px;line-height:1.8}
    """

    parts = []
    parts.append("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append("<title>麦麦羊毛雷达巡检报告</title><style>%s</style></head><body><div class='wrap'>" % css)
    parts.append(
        "<header><h1>🍟 麦麦羊毛雷达 · 巡检报告</h1>"
        "<p>生成时间：%s ｜ 数据来源：麦当劳中国官方 MCP（mcp.mcd.cn）</p></header>"
        % _esc(data["generated_at"]))

    # 动作结果（领券等）
    for act in data.get("actions", []):
        if act["ok"]:
            parts.append("<div class='advice ok'>✅ 已执行 %s：成功。详见下方「我的券包」。</div>"
                         % _esc(act["tool"]))
        else:
            parts.append("<div class='advice warn'>⚠️ %s 执行失败：%s</div>"
                         % (_esc(act["tool"]), _esc(act["error"] or "未知错误")))

    for panel in data["panels"]:
        n = sum(1 for i in panel.get("items", []) if i.get("ok")) or 1
        parts.append("<section class='panel'><h2>%s</h2><div class='intro'>%s</div>"
                     % (_esc(panel["title"]), _esc(panel.get("intro", ""))))
        if "advice" in panel:  # 积分理财面板
            adv = panel["advice"]
            cls = adv.get("level", "info")
            parts.append("<div class='advice %s'>%s</div>"
                         % (cls if cls in ("warn", "ok") else "", _esc(adv.get("message", ""))))
            for i, s in enumerate(adv.get("suggestions", []), 1):
                parts.append("<div class='advice'>%d. %s（%d 分）%s</div>"
                             % (i, _esc(s["name"]), s["points"], _esc(s.get("note", ""))))
        for item in panel.get("items", []):
            cnt = _count_items(item.get("data"))
            badge = (" <span class='badge'>%s 条</span>" % cnt) if cnt is not None else ""
            state = "✅%s" % badge if item["ok"] else "❌"
            parts.append("<p style='font-size:13px;margin:10px 0 6px'><b>%s</b> · %s</p>"
                         % (_esc(item["label"]), state))
            if not item["ok"]:
                parts.append("<p class='err'>%s</p>" % _esc(item["error"] or "调用失败"))
            elif item.get("data") is not None:
                pretty = json.dumps(item["data"], ensure_ascii=False, indent=2)
                parts.append("<pre>%s</pre>" % _esc(pretty if len(pretty) < 8000
                                                    else pretty[:8000] + "\n…(截断)"))
        parts.append("</section>")

    parts.append(
        "<footer>麦麦羊毛雷达 mcd-wool-radar · 1024 程序员节参赛作品<br>"
        "数据接口 © 麦当劳中国 MCP Server，本项目与麦当劳无隶属关系，仅供个人非商业使用</footer>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="麦麦羊毛雷达巡检")
    parser.add_argument("--claim", action="store_true",
                        help="执行一键领券（auto-bind-coupons，写操作）")
    parser.add_argument("--out", default="report.html", help="HTML 报告输出路径")
    parser.add_argument("--json", action="store_true", help="同时输出结构化 JSON")
    opts = parser.parse_args()

    try:
        client = McdMcpClient()
        client.initialize()
    except McpError as e:
        sys.exit("初始化失败：%s" % e)

    print("🛰 巡检开始：%s" % datetime.datetime.now().strftime("%H:%M:%S"))
    data = collect(client, claim=opts.claim)

    ok = sum(1 for p in data["panels"] for i in p.get("items", []) if i.get("ok"))
    total = sum(len(p.get("items", [])) for p in data["panels"])
    print("🛰 巡检完成：%d/%d 个接口成功" % (ok, total))
    for act in data["actions"]:
        print("🧾 %s → %s" % (act["tool"], "成功" if act["ok"] else "失败：" + str(act["error"])))

    with io.open(opts.out, "w", encoding="utf-8") as f:
        f.write(render_html(data))
    print("📄 报告已生成：%s" % os.path.abspath(opts.out))

    if opts.json:
        jp = os.path.splitext(opts.out)[0] + ".json"
        with io.open(jp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("📄 JSON 已生成：%s" % os.path.abspath(jp))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
points_advisor.py — 积分到期理财顾问

问题：麦当劳积分会过期（query-my-account 里的"即将过期积分"），
     大多数人不知道自己有分、更不知道过期前能换什么。

思路：
  1. query-my-account          → 可用积分 / 即将过期积分
  2. mall-points-products      → 积分商城全部可兑换商品
  3. 在"当前可用积分"预算内给出兑换建议：
     - 优先消耗即将过期积分对应面额的商品
     - 按 积分性价比（商品价值/所需积分）与实用性排序
"""
import json

# 积分商城商品字段在不同版本中命名不完全一致，做多键名兼容
POINTS_KEYS = ("points", "point", "exchangePoints", "needPoints", "costPoints", "redeemPoints")
PRICE_KEYS = ("price", "salePrice", "value", "originalPrice")
NAME_KEYS = ("name", "productName", "title", "goodsName")


def _first(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def extract_products(raw):
    """从 mall-points-products 的原始返回中抽出商品列表（兼容 list / {list:[]} / {products:[]} 等）。"""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = None
        for k in ("list", "products", "items", "data", "records", "productList"):
            v = raw.get(k)
            if isinstance(v, list):
                items = v
                break
            if isinstance(v, dict):  # 再下钻一层
                for k2 in ("list", "products", "items", "records"):
                    if isinstance(v.get(k2), list):
                        items = v[k2]
                        break
                break
        if items is None:
            items = []
    else:
        items = []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append({
            "name": _first(it, NAME_KEYS, "未命名商品"),
            "points": _first(it, POINTS_KEYS),
            "price": _first(it, PRICE_KEYS),
            "raw": it,
        })
    return out


def extract_account(raw):
    """从 query-my-account 返回中尽量提取 可用积分/即将过期积分（兼容多种字段命名）。"""
    acc = raw if isinstance(raw, dict) else {}
    available = None
    expiring = None
    expiring_date = None
    for k in ("availablePoints", "available_points", "points", "balance"):
        if isinstance(acc.get(k), (int, float)):
            available = acc[k]
            break
    for k in ("expiringPoints", "expiring_points", "soonExpiredPoints", "willExpirePoints"):
        if isinstance(acc.get(k), (int, float)):
            expiring = acc[k]
            break
    for k in ("expiringDate", "expireDate", "willExpireDate"):
        if acc.get(k):
            expiring_date = acc[k]
            break
    # 有时嵌在子结构里
    if available is None or expiring is None:
        for v in acc.values():
            if isinstance(v, dict):
                sub = extract_account(v)
                if available is None and sub.get("available") is not None:
                    available = sub["available"]
                if expiring is None and sub.get("expiring") is not None:
                    expiring = sub["expiring"]
                if expiring_date is None and sub.get("expiring_date"):
                    expiring_date = sub["expiring_date"]
    return {"available": available, "expiring": expiring, "expiring_date": expiring_date}


def advise(account, products, top_n=5):
    """生成兑换建议。返回 dict：状态 + 建议列表 + 消息。"""
    available = account.get("available") or 0
    expiring = account.get("expiring") or 0

    if available <= 0:
        return {"level": "info", "message": "当前没有可用积分，先去消费攒分或抽奖吧。",
                "suggestions": []}

    affordable = [p for p in products
                  if isinstance(p.get("points"), (int, float)) and 0 < p["points"] <= available]
    affordable.sort(key=lambda p: p["points"])  # 小额优先：优先花掉快过期的分

    suggestions = []
    for p in affordable[:top_n]:
        line = {
            "name": p["name"],
            "points": int(p["points"]),
            "note": "",
        }
        if expiring > 0 and p["points"] <= expiring:
            line["note"] = "✅ 面额不超过即将过期积分（%d），优先用它兜住快过期的分" % expiring
        elif expiring > 0:
            line["note"] = "略高于过期积分面额，需补少量当前积分"
        suggestions.append(line)

    if not suggestions:
        return {"level": "warn",
                "message": "可用积分 %d 分，但商城没有能单独兑下的商品（最低面额更高）。可考虑抽奖或继续攒分。" % available,
                "suggestions": []}
    if expiring > 0:
        return {"level": "warn",
                "message": "⚠️ 有 %d 积分即将过期%s！过期自动清零。建议在过期前按下列顺序兑换：" % (
                    expiring, ("（" + str(account.get("expiring_date") or "日期未知") + "）") if account.get("expiring_date") else ""),
                "suggestions": suggestions}
    return {"level": "ok",
            "message": "积分暂无近期过期风险。当前 %d 分可兑换：" % available,
            "suggestions": suggestions}


def run(client):
    """用 MCP client 跑完整建议流程，返回 (account, products, advice)。"""
    acc_raw, _ = client.call_tool("query-my-account")
    account = extract_account(acc_raw)
    prod_raw, _ = client.call_tool("mall-points-products")
    products = extract_products(prod_raw)
    advice = advise(account, products)
    return account, products, advice


if __name__ == "__main__":
    from mcd_client import McdMcpClient
    c = McdMcpClient()
    c.initialize()
    account, products, advice = run(c)
    print(json.dumps({"account": account, "advice": advice}, ensure_ascii=False, indent=2))

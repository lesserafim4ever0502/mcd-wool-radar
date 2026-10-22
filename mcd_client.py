#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd_client.py — 麦当劳中国 MCP Server 的零依赖 Python 客户端

- 传输协议：Streamable HTTP（https://mcp.mcd.cn）
- 鉴权：Bearer Token（环境变量 MCD_MCP_TOKEN）
- 依赖：仅 Python 3.8+ 标准库

既可作为库被 radar.py / points_advisor.py 导入，
也可以命令行直接调用：

    python mcd_client.py --list-tools
    python mcd_client.py --call query-my-account
    python mcd_client.py --call query-meals '{"storeCode": "1234"}'
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-03-26"
CLIENT_INFO = {"name": "mcd-wool-radar", "version": "1.0.0"}


class McpError(RuntimeError):
    """MCP 调用失败（JSON-RPC error / HTTP error / 解析失败）。"""


class McdMcpClient:
    def __init__(self, token=None, url=None, timeout=30):
        self.token = (token or os.environ.get("MCD_MCP_TOKEN", "")).strip()
        self.url = (url or os.environ.get("MCD_MCP_URL", DEFAULT_URL)).strip().rstrip("/")
        self.timeout = timeout
        self.session_id = None
        self._id = 0
        if not self.token:
            raise McpError(
                "缺少麦当劳 MCP Token。请到 https://open.mcd.cn/mcp 登录后在控制台激活领取，"
                "然后设置环境变量 MCD_MCP_TOKEN。"
            )

    # ---------------- 底层传输 ----------------

    def _post(self, payload, retries=2):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.token,
            "User-Agent": "mcd-wool-radar/1.0 (+python-urllib)",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        last_err = None
        for attempt in range(retries + 1):
            req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    sid = resp.headers.get("Mcp-Session-Id")
                    if sid:
                        self.session_id = sid
                    ctype = resp.headers.get("Content-Type", "")
                    raw = resp.read().decode("utf-8", errors="replace")
                break
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
                last_err = McpError("HTTP %s %s %s" % (e.code, e.reason, detail))
                if e.code == 429:  # 限流：600 次/分钟，退避重试
                    time.sleep(2 * (attempt + 1))
                    continue
                raise last_err
            except urllib.error.URLError as e:
                last_err = McpError("网络错误：%s" % e.reason)
                time.sleep(1 + attempt)
                continue
        else:
            raise last_err or McpError("请求失败")

        if "text/event-stream" in ctype:
            return self._parse_sse(raw)
        if not raw.strip():
            return {}
        return json.loads(raw)

    @staticmethod
    def _parse_sse(raw):
        """从 SSE 流里取出第一条完整 JSON（MCP Streamable HTTP 的服务端返回格式）。"""
        buf, decoded = [], None
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                if buf and decoded is None:
                    decoded = McdMcpClient._try_json("\n".join(buf))
                    buf = []
                continue
            if line.startswith(":"):
                continue  # SSE 注释/心跳
            if line.startswith("data:"):
                buf.append(line[5:].strip())
        if buf and decoded is None:
            decoded = McdMcpClient._try_json("\n".join(buf))
        if decoded is None:
            raise McpError("无法解析 SSE 响应：%s" % raw[:300])
        return decoded

    @staticmethod
    def _try_json(text):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    # ---------------- JSON-RPC ----------------

    def _rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        result = self._post(payload)
        if isinstance(result, dict) and "error" in result and result["error"]:
            err = result["error"]
            raise McpError("%s 调用失败：[%s] %s" % (method, err.get("code"), err.get("message")))
        return (result or {}).get("result", {})

    def _notify(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload)

    # ---------------- MCP 会话 ----------------

    def initialize(self):
        result = self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        self._notify("notifications/initialized")
        return result

    def list_tools(self):
        tools, cursor = [], None
        while True:
            params = {"cursor": cursor} if cursor else {}
            result = self._rpc("tools/list", params)
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name, arguments=None):
        """调用工具，返回 (parsed, raw_result)。

        parsed：若工具文本为合法 JSON 则解析为 dict/list，否则原样返回字符串。
        """
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        result = self._rpc("tools/call", params)
        if result.get("isError"):
            texts = [b.get("text", "") for b in result.get("content", []) if isinstance(b, dict)]
            raise McpError("%s 工具执行出错：%s" % (name, " ".join(texts)[:300]))
        texts = [b.get("text", "") for b in result.get("content", []) if isinstance(b, dict)]
        joined = "\n".join(texts)
        try:
            return json.loads(joined), result
        except (json.JSONDecodeError, TypeError):
            return joined, result


# ---------------- CLI ----------------

def main():
    parser = argparse.ArgumentParser(description="麦当劳 MCP 零依赖命令行客户端")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-tools", action="store_true", help="列出 MCP Server 支持的全部工具")
    group.add_argument("--call", metavar="TOOL", help="调用指定工具")
    parser.add_argument("--args", metavar="JSON", default="{}", help="工具参数，JSON 字符串，默认 {}")
    parser.add_argument("--init-info", action="store_true", help="打印 initialize 握手信息")
    opts = parser.parse_args()

    client = McdMcpClient()
    init = client.initialize()
    if opts.init_info:
        print(json.dumps(init, ensure_ascii=False, indent=2))

    if opts.list_tools:
        tools = client.list_tools()
        print("共 %d 个工具：" % len(tools))
        for t in tools:
            desc = (t.get("description") or "").strip().split("\n")[0]
            print("  %-28s %s" % (t.get("name"), desc))
        return

    if opts.call:
        try:
            arguments = json.loads(opts.args)
        except json.JSONDecodeError as e:
            sys.exit("参数不是合法 JSON：%s" % e)
        parsed, _ = client.call_tool(opts.call, arguments)
        if isinstance(parsed, (dict, list)):
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        else:
            print(parsed)


if __name__ == "__main__":
    main()

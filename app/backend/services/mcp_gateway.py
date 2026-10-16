from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from config import MCP_COMMAND, MCP_DATA_DIR, MCP_WORKDIR


class MCPError(RuntimeError):
    pass


class MCPGateway:
    """Small stdio MCP client used by the product backend.

    The course scripts remain outside the product package. The gateway only
    starts them as a child process and communicates over JSON-RPC lines.
    """

    def __init__(
        self,
        command: str | None = None,
        cwd: Path | None = None,
        data_dir: str | None = None,
        timeout: int = 20,
    ):
        self.command = command or MCP_COMMAND
        self.cwd = cwd or MCP_WORKDIR
        self.data_dir = data_dir or MCP_DATA_DIR
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self.counter = 0
        self.server = None
        self._tools = None

    def __enter__(self):
        argv = shlex.split(self.command)
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable
        env = os.environ.copy()
        env["DATA_PACK_DIR"] = self.data_dir
        env["PYTHONIOENCODING"] = "utf-8"
        self.process = subprocess.Popen(
            argv,
            cwd=str(self.cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.server = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "wind-ops-product",
                    "version": "0.2.0",
                },
            },
        )
        self.notify("notifications/initialized")
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        if not self.process:
            return
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process = None

    def _send(self, message):
        if not self.process or not self.process.stdin:
            raise MCPError("MCP 服务未启动")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def notify(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        self._send(payload)

    def request(self, method, params=None):
        self.counter += 1
        ident = self.counter
        payload = {"jsonrpc": "2.0", "id": ident, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        while True:
            if not self.process or not self.process.stdout:
                raise MCPError("MCP 服务已关闭")
            line = self.process.stdout.readline()
            if not line:
                error = ""
                if self.process.stderr:
                    try:
                        error = self.process.stderr.read(500)
                    except OSError:
                        pass
                raise MCPError(f"MCP 服务已关闭：{error}")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError as exc:
                raise MCPError("MCP 返回了无效内容") from exc
            if message.get("id") != ident:
                continue
            if "error" in message:
                error = message["error"]
                raise MCPError(
                    f"{error.get('code')}: {error.get('message')}"
                )
            return message.get("result")

    def list_tools(self):
        if self._tools is None:
            self._tools = self.request("tools/list", {}).get("tools", [])
        return self._tools

    def call(self, name, arguments=None):
        try:
            result = self.request(
                "tools/call",
                {"name": name, "arguments": arguments or {}},
            )
        except MCPError as exc:
            return {"ok": False, "error": str(exc)}
        content = result.get("content") or []
        text = content[0].get("text", "") if content else ""
        if result.get("isError"):
            return {"ok": False, "error": text or "tool_error"}
        data = result.get("structuredContent")
        if data is None:
            try:
                data = json.loads(text)
            except ValueError:
                data = {"text": text}
        return {"ok": True, "data": data}

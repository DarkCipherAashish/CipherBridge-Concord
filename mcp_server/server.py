"""A Model Context Protocol (MCP) server over stdio.

Implements the JSON-RPC 2.0 messages MCP clients use: initialize, ping,
tools/list, tools/call, resources/list, resources/templates/list,
resources/read, prompts/list and prompts/get. Messages are newline-delimited
JSON on stdin/stdout; diagnostics go to stderr so stdout stays protocol-only."""
import json
import sys
from typing import Any, Dict, Optional

from mcp_server import tools

SERVER_INFO = {"name": "cipherbridge-concord", "version": "1.0.0"}
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "CipherBridge Concord supports cryptography decisions. Use check_cryptography_scope first, "
    "search_knowledge_base for evidence, and run_stakeholder_dialogue to have two stakeholder roles "
    "reach a joint conclusion. Outputs are AI-generated and need human security review."
)

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603
RESOURCE_NOT_FOUND = -32002


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _error(msg_id: Any, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _log(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


class McpServer:
    def __init__(self) -> None:
        self._methods = {
            "initialize": self._initialize,
            "ping": lambda params: {},
            "tools/list": lambda params: {"tools": tools.list_tools()},
            "tools/call": self._call_tool,
            "resources/list": lambda params: {"resources": tools.list_resources()},
            "resources/templates/list": lambda params: {"resourceTemplates": []},
            "resources/read": self._read_resource,
            "prompts/list": lambda params: {"prompts": tools.list_prompts()},
            "prompts/get": self._get_prompt,
        }

    # ----- method handlers -------------------------------------------------
    def _initialize(self, params: Dict) -> Dict:
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0],
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        }

    def _call_tool(self, params: Dict) -> Dict:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise RpcError(INVALID_PARAMS, "Missing tool name.")
        if tools.find_tool(name) is None:
            raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
        try:
            output = tools.call_tool(name, params.get("arguments"))
            text, is_error = json.dumps(output, ensure_ascii=False, indent=2), False
        except tools.ToolError as exc:
            text, is_error = str(exc), True
        except Exception as exc:  # noqa: BLE001 - a tool bug must not crash the server
            _log(f"tool {name} failed: {type(exc).__name__}: {exc}")
            text, is_error = f"The tool failed unexpectedly ({type(exc).__name__}).", True
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    def _read_resource(self, params: Dict) -> Dict:
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise RpcError(INVALID_PARAMS, "Missing resource uri.")
        try:
            return {"contents": [tools.read_resource(uri)]}
        except tools.ResourceNotFound:
            raise RpcError(RESOURCE_NOT_FOUND, f"Resource not found: {uri}")

    def _get_prompt(self, params: Dict) -> Dict:
        name = params.get("name")
        if not isinstance(name, str):
            raise RpcError(INVALID_PARAMS, "Missing prompt name.")
        try:
            return tools.get_prompt(name, params.get("arguments"))
        except tools.ToolError as exc:
            raise RpcError(INVALID_PARAMS, str(exc))

    # ----- protocol --------------------------------------------------------
    def handle(self, message: Any) -> Optional[Dict]:
        """Process one JSON-RPC message; return the response, or None for notifications/responses."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "Invalid Request")
        method = message.get("method")
        if method is None:
            return None  # a response from the client; this server sends no requests
        msg_id = message.get("id")
        if not isinstance(method, str):
            return _error(msg_id, INVALID_REQUEST, "Invalid Request")
        if "id" not in message:
            return None  # notification, e.g. notifications/initialized
        params = message.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(msg_id, INVALID_PARAMS, "params must be an object")
        handler = self._methods.get(method)
        if handler is None:
            return _error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")
        try:
            return {"jsonrpc": "2.0", "id": msg_id, "result": handler(params)}
        except RpcError as exc:
            return _error(msg_id, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001
            _log(f"{method} failed: {type(exc).__name__}: {exc}")
            return _error(msg_id, INTERNAL_ERROR, "Internal error")

    def serve(self, stdin=None, stdout=None) -> None:
        stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._write(stdout, _error(None, PARSE_ERROR, "Parse error"))
                continue
            if isinstance(message, list):
                responses = [r for r in (self.handle(m) for m in message) if r is not None]
                if responses:
                    self._write(stdout, responses)
            else:
                response = self.handle(message)
                if response is not None:
                    self._write(stdout, response)

    @staticmethod
    def _write(stdout, payload: Any) -> None:
        # ASCII-escaped JSON on a single line is valid UTF-8 JSON and safe on any console encoding.
        stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
        stdout.flush()


def main() -> None:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    _log("CipherBridge Concord MCP server ready (stdio). Press Ctrl+C to stop.")
    try:
        McpServer().serve()
    except KeyboardInterrupt:
        pass

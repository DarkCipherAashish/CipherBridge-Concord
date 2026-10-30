import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server import tools
from mcp_server.server import McpServer
from tests.test_dialogue import fake_llm
from tests.test_evaluation import A, B, turns as sample_turns

ROOT = Path(__file__).resolve().parent.parent


def request(method, params=None, msg_id=1):
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def call(server, name, arguments=None):
    response = server.handle(request("tools/call", {"name": name, "arguments": arguments}))
    result = response["result"]
    text = result["content"][0]["text"]
    return result["isError"], (text if result["isError"] else json.loads(text))


class McpTestCase(unittest.TestCase):
    def setUp(self):
        self.server = McpServer()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.dict(os.environ, {"CIPHERBRIDGE_DATA_DIR": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)


class ProtocolTests(McpTestCase):
    def test_initialize_negotiates_version(self):
        for version in ("2025-06-18", "2025-03-26", "2024-11-05"):
            result = self.server.handle(request("initialize", {"protocolVersion": version}))["result"]
            self.assertEqual(result["protocolVersion"], version)
        unknown = self.server.handle(request("initialize", {"protocolVersion": "1999-01-01"}))["result"]
        self.assertEqual(unknown["protocolVersion"], "2025-06-18")
        self.assertEqual(unknown["serverInfo"]["name"], "cipherbridge-concord")
        self.assertEqual(set(unknown["capabilities"]), {"tools", "resources", "prompts"})

    def test_response_echoes_the_request_id(self):
        self.assertEqual(self.server.handle(request("ping", msg_id="abc"))["id"], "abc")
        self.assertEqual(self.server.handle(request("ping", msg_id=0))["id"], 0)

    def test_notifications_get_no_response(self):
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}))

    def test_client_responses_are_ignored(self):
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "id": 5, "result": {}}))

    def test_error_codes(self):
        self.assertEqual(self.server.handle(request("nope"))["error"]["code"], -32601)
        self.assertEqual(self.server.handle({"id": 1, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(self.server.handle("not an object")["error"]["code"], -32600)
        self.assertEqual(self.server.handle({"jsonrpc": "2.0", "id": 1, "method": 5})["error"]["code"], -32600)
        self.assertEqual(self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1]})["error"]["code"], -32602)

    def test_tools_list_has_valid_schemas(self):
        listed = self.server.handle(request("tools/list"))["result"]["tools"]
        self.assertEqual({t["name"] for t in listed}, {
            "check_cryptography_scope", "search_knowledge_base", "list_stakeholder_personas",
            "evaluate_transcript", "run_stakeholder_dialogue", "list_decision_history", "get_decision"})
        for tool in listed:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertTrue(tool["description"])
            self.assertNotIn("handler", tool)
            json.dumps(tool)
            for required in tool["inputSchema"].get("required", []):
                self.assertIn(required, tool["inputSchema"]["properties"])

    def test_unknown_tool_is_a_protocol_error(self):
        response = self.server.handle(request("tools/call", {"name": "nope"}))
        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(self.server.handle(request("tools/call", {}))["error"]["code"], -32602)

    def test_serve_handles_bad_json_batches_and_blank_lines(self):
        import io
        lines = "\n".join(["", "{broken", json.dumps([request("ping", msg_id=1), request("ping", msg_id=2)]),
                           json.dumps(request("ping", msg_id=3)), json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})])
        out = io.StringIO()
        self.server.serve(io.StringIO(lines + "\n"), out)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual([r["id"] for r in replies[1]], [1, 2])
        self.assertEqual(replies[2]["id"], 3)
        self.assertEqual(len(replies), 3)
        self.assertTrue(all("\n" not in line for line in out.getvalue().rstrip("\n").splitlines()))

    def test_non_ascii_output_is_escaped_for_any_console(self):
        import io
        out = io.StringIO()
        self.server.serve(io.StringIO(json.dumps(request("tools/call", {"name": "check_cryptography_scope", "arguments": {"topic": "ünïcode — résumé 密码学"}})) + "\n"), out)
        out.getvalue().encode("ascii")  # must not raise
        self.assertIn("result", json.loads(out.getvalue()))


class ToolTests(McpTestCase):
    def test_scope_tool(self):
        is_error, data = call(self.server, "check_cryptography_scope", {"topic": "How should a web app store passwords?"})
        self.assertFalse(is_error)
        self.assertEqual((data["in_scope"], data["status"]), (True, "accepted"))
        _, data = call(self.server, "check_cryptography_scope", {"topic": "Recommend romantic movies"})
        self.assertEqual((data["in_scope"], data["status"]), (False, "rejected"))

    def test_argument_validation_returns_tool_errors_not_crashes(self):
        for name, args, fragment in [
            ("check_cryptography_scope", {}, "Missing required argument: topic"),
            ("check_cryptography_scope", {"topic": 5}, "must be of type string"),
            ("check_cryptography_scope", {"topic": "   "}, "must not be empty"),
            ("search_knowledge_base", {"query": "aes", "top_k": 0}, "between 1 and 10"),
            ("search_knowledge_base", {"query": "aes", "top_k": True}, "must be of type integer"),
            ("get_decision", {"id": "x", "format": "pdf"}, "must be one of"),
            ("check_cryptography_scope", ["not", "an", "object"], "must be a JSON object"),
        ]:
            is_error, text = call(self.server, name, args)
            self.assertTrue(is_error, (name, args))
            self.assertIn(fragment, text)

    def test_search_knowledge_base(self):
        is_error, data = call(self.server, "search_knowledge_base", {"query": "AES-GCM nonce reuse", "top_k": 2})
        self.assertFalse(is_error)
        self.assertEqual(data["count"], len(data["results"]))
        self.assertLessEqual(data["count"], 2)
        self.assertEqual(data["results"][0]["heading"], "Nonce handling")
        _, none = call(self.server, "search_knowledge_base", {"query": "pasta recipe"})
        self.assertEqual((none["count"], none["results"]), (0, []))
        self.assertTrue(none["note"])

    def test_personas_tool(self):
        _, data = call(self.server, "list_stakeholder_personas")
        names = [p["name"] for p in data["personas"]]
        self.assertIn("Software Developer", names)
        self.assertEqual(len(names), 5)

    def test_evaluate_transcript(self):
        raw = [{"speaker": t["speaker"], "content": t["content"]} for t in sample_turns()]
        is_error, data = call(self.server, "evaluate_transcript", {"turns": raw, "persona_a": A, "persona_b": B})
        self.assertFalse(is_error)
        self.assertEqual(data["agreement_status"], "agreed")
        self.assertEqual(data["agreement"]["score"], 100)
        self.assertEqual(len(data["agreement"]["checks"]), 7)
        self.assertIn("A", data["persona_consistency"])

    def test_evaluate_transcript_rejects_bad_input(self):
        raw = [{"speaker": t["speaker"], "content": t["content"]} for t in sample_turns()]
        for args, fragment in [
            ({"turns": raw[:2], "persona_a": A, "persona_b": B}, "At least 4 turns"),
            ({"turns": raw, "persona_a": A, "persona_b": A}, "must be different"),
            ({"turns": raw, "persona_a": "Wizard", "persona_b": B}, "must be one of"),
            ({"turns": raw[:3] + [{"speaker": "x"}], "persona_a": A, "persona_b": B}, "Turn 4"),
            ({"turns": raw * 11, "persona_a": A, "persona_b": B}, "At most"),
        ]:
            is_error, text = call(self.server, "evaluate_transcript", args)
            self.assertTrue(is_error)
            self.assertIn(fragment, text)

    def test_run_dialogue_rejects_out_of_scope_topics_before_calling_the_model(self):
        with patch("services.dialogue_manager.chat_completion") as mocked:
            is_error, text = call(self.server, "run_stakeholder_dialogue", {"topic": "Recommend romantic movies"})
        self.assertTrue(is_error)
        self.assertIn("cryptography", text.lower())
        mocked.assert_not_called()

    def test_run_dialogue_without_api_key_is_a_clear_error(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            is_error, text = call(self.server, "run_stakeholder_dialogue", {"topic": "Password hashing for a web app", "turns": 4})
        self.assertTrue(is_error)
        self.assertIn("API key", text)

    def test_run_dialogue_returns_conclusion_sources_and_checks(self):
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            is_error, data = call(self.server, "run_stakeholder_dialogue", {"topic": "Choosing password hashing for a web application", "turns": 4})
        self.assertFalse(is_error)
        self.assertEqual(data["agreement_status"], "agreed")
        self.assertIn("Argon2id", data["decision"])
        self.assertIn("benchmark", data["action_plan"])
        self.assertEqual(len(data["turns"]), 4)
        self.assertTrue(data["sources"])
        self.assertIsNone(data["history_id"])  # saving is opt-in for tool calls
        self.assertIn("grounding", data["evaluation"])

    def test_run_dialogue_without_knowledge_base_and_with_history(self):
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            _, data = call(self.server, "run_stakeholder_dialogue", {
                "topic": "Choosing password hashing for a web application", "turns": 4,
                "use_knowledge_base": False, "save_to_history": True, "persona_a": "Product Manager", "persona_b": "Software Developer"})
        self.assertEqual(data["sources"], [])
        self.assertTrue(data["history_id"])
        _, listed = call(self.server, "list_decision_history", {"limit": 5})
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["decisions"][0]["id"], data["history_id"])
        _, md = call(self.server, "get_decision", {"id": data["history_id"], "format": "markdown"})
        self.assertIn("## Transcript", md["content"])
        _, full = call(self.server, "get_decision", {"id": data["history_id"]})
        self.assertEqual(full["topic"], "Choosing password hashing for a web application")

    def test_same_persona_twice_is_rejected(self):
        is_error, text = call(self.server, "run_stakeholder_dialogue", {"topic": "Password hashing for a web app", "persona_a": "Product Manager", "persona_b": "Product Manager"})
        self.assertTrue(is_error)
        self.assertIn("different", text)

    def test_history_lookup_errors(self):
        _, listed = call(self.server, "list_decision_history")
        self.assertEqual(listed["count"], 0)
        is_error, text = call(self.server, "get_decision", {"id": "missing"})
        self.assertTrue(is_error)
        self.assertIn("No saved decision", text)

    def test_unexpected_tool_failure_does_not_crash_the_server(self):
        with patch.dict(tools._BY_NAME["list_stakeholder_personas"], {"handler": lambda args: 1 / 0}):
            is_error, text = call(self.server, "list_stakeholder_personas")
        self.assertTrue(is_error)
        self.assertIn("failed unexpectedly", text)
        self.assertNotIn("division", text)  # internal details are not leaked to the client


class ResourceAndPromptTests(McpTestCase):
    def test_resources_list_and_read(self):
        resources = self.server.handle(request("resources/list"))["result"]["resources"]
        uris = [r["uri"] for r in resources]
        self.assertIn("cipherbridge://personas", uris)
        self.assertIn("cipherbridge://knowledge/01-password-storage", uris)
        self.assertEqual(len(uris), 1 + len([u for u in uris if "knowledge" in u]))
        personas = self.server.handle(request("resources/read", {"uri": "cipherbridge://personas"}))["result"]["contents"][0]
        self.assertEqual(personas["mimeType"], "application/json")
        self.assertIn("Software Developer", personas["text"])
        note = self.server.handle(request("resources/read", {"uri": "cipherbridge://knowledge/01-password-storage"}))["result"]["contents"][0]
        self.assertIn("Argon2id", note["text"])

    def test_resource_errors(self):
        self.assertEqual(self.server.handle(request("resources/read", {"uri": "cipherbridge://knowledge/nope"}))["error"]["code"], -32002)
        self.assertEqual(self.server.handle(request("resources/read", {"uri": "file:///etc/passwd"}))["error"]["code"], -32002)
        self.assertEqual(self.server.handle(request("resources/read", {"uri": "cipherbridge://knowledge/../../etc/passwd"}))["error"]["code"], -32002)
        self.assertEqual(self.server.handle(request("resources/read", {}))["error"]["code"], -32602)
        self.assertEqual(self.server.handle(request("resources/templates/list"))["result"], {"resourceTemplates": []})

    def test_user_notes_appear_as_resources(self):
        from services.rag import add_user_document
        info = add_user_document("course.md", "# Course\n\n## S\nnotes about rsa")
        uris = [r["uri"] for r in self.server.handle(request("resources/list"))["result"]["resources"]]
        self.assertIn(f"cipherbridge://knowledge/{info['doc_id']}", uris)

    def test_prompts(self):
        prompts = self.server.handle(request("prompts/list"))["result"]["prompts"]
        self.assertEqual(prompts[0]["name"], "cryptography_decision_brief")
        got = self.server.handle(request("prompts/get", {"name": "cryptography_decision_brief", "arguments": {"topic": "TLS for our API"}}))["result"]
        text = got["messages"][0]["content"]["text"]
        self.assertIn("TLS for our API", text)
        for tool in ("check_cryptography_scope", "search_knowledge_base", "run_stakeholder_dialogue"):
            self.assertIn(tool, text)
        self.assertEqual(self.server.handle(request("prompts/get", {"name": "cryptography_decision_brief"}))["error"]["code"], -32602)
        self.assertEqual(self.server.handle(request("prompts/get", {"name": "nope"}))["error"]["code"], -32602)


class StdioProcessTests(unittest.TestCase):
    """Run the real server as a subprocess, exactly as an MCP client would."""

    def _run(self, messages, cwd=ROOT, script=False):
        env = dict(os.environ, GROQ_API_KEY="", CIPHERBRIDGE_DATA_DIR=tempfile.mkdtemp())
        cmd = [sys.executable, str(ROOT / "mcp_server" / "__main__.py")] if script else [sys.executable, "-m", "mcp_server"]
        done = subprocess.run(cmd, input="\n".join(m if isinstance(m, str) else json.dumps(m) for m in messages) + "\n",
                              capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=cwd, env=env)
        return done

    def _session(self):
        return [request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}, 1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                request("tools/list", None, 2),
                request("tools/call", {"name": "search_knowledge_base", "arguments": {"query": "post-quantum migration"}}, 3),
                request("resources/list", None, 4),
                "{this is not json",
                request("tools/call", {"name": "run_stakeholder_dialogue", "arguments": {"topic": "Password hashing for a web app"}}, 5)]

    def _check(self, done):
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        replies = [json.loads(line) for line in lines]  # every stdout line must be valid JSON-RPC
        self.assertTrue(all(r.get("jsonrpc") == "2.0" for r in replies))
        by_id = {r.get("id"): r for r in replies}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "cipherbridge-concord")
        self.assertEqual(len(by_id[2]["result"]["tools"]), 7)
        found = json.loads(by_id[3]["result"]["content"][0]["text"])
        self.assertIn("Post-quantum cryptography", [r["title"] for r in found["results"]])
        self.assertGreaterEqual(len(by_id[4]["result"]["resources"]), 12)
        self.assertEqual(by_id[None]["error"]["code"], -32700)
        self.assertTrue(by_id[5]["result"]["isError"])
        self.assertIn("API key", by_id[5]["result"]["content"][0]["text"])
        self.assertIn("MCP server ready", done.stderr)  # logs go to stderr only

    def test_module_launch(self):
        self._check(self._run(self._session()))

    def test_script_launch_from_another_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            self._check(self._run(self._session(), cwd=elsewhere, script=True))

    def test_server_exits_cleanly_when_the_client_disconnects(self):
        done = self._run([])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")


if __name__ == "__main__":
    unittest.main()

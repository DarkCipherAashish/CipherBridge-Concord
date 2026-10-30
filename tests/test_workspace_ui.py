"""Smoke tests for the chat workspace using a stubbed `streamlit` module.

These exercise the real control flow in ui/workspace.py (scope check, setup
check, generation, conclusion, partial failure) without a browser or API key.
They do not verify visual layout; run the app to check that."""
import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from tests.test_dialogue import fake_llm


class _State(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


def _fake_streamlit(prompt=None):
    st = MagicMock(name="streamlit")
    st.session_state = _State()
    st.chat_input.return_value = prompt
    st.button.return_value = False
    st.checkbox.return_value = False
    st.download_button.return_value = False
    st._columns = []

    def _column():
        col = MagicMock()
        col.button.return_value = False  # a column's button is "not clicked" unless a test says otherwise
        col.download_button.return_value = False
        st._columns.append(col)
        return col

    st.columns.side_effect = lambda spec, **kw: [_column() for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.selectbox.side_effect = lambda label, options, key=None, **kw: st.session_state[key]
    st.slider.side_effect = lambda label, lo=None, hi=None, key=None, **kw: st.session_state[key]
    st.text_area.side_effect = lambda label, key=None, **kw: st.session_state.get(key, "")
    return st


def _load_workspace(fake):
    sys.modules.pop("ui.workspace", None)
    with patch.dict(sys.modules, {"streamlit": fake}):
        return importlib.import_module("ui.workspace")


class WorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.dict(os.environ, {"CIPHERBRIDGE_DATA_DIR": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self):
        sys.modules.pop("ui.workspace", None)

    def run_ws(self, prompt, configured=True, llm=fake_llm, turns=None):
        fake = _fake_streamlit(prompt)
        ws = self.ws = _load_workspace(fake)
        if turns:
            fake.session_state["ws_turns"] = turns
        with patch("services.dialogue_manager.chat_completion", side_effect=llm) as mocked:
            ws.render_workspace(configured)
        return fake, mocked

    def test_welcome_shown_when_empty(self):
        fake, mocked = self.run_ws(None)
        self.assertEqual(fake.session_state.ws_messages, [])
        mocked.assert_not_called()

    def test_off_topic_gets_scope_notice_and_no_api_call(self):
        fake, mocked = self.run_ws("Recommend romantic movies for date night")
        kinds = [(m["kind"], m.get("level")) for m in fake.session_state.ws_messages]
        self.assertEqual(kinds, [("user", None), ("notice", "scope")])
        self.assertIn("cryptography", fake.session_state.ws_messages[1]["content"].lower())
        mocked.assert_not_called()

    def test_missing_api_key_gives_setup_notice(self):
        fake, mocked = self.run_ws("Choose password hashing for our web app", configured=False)
        self.assertEqual(fake.session_state.ws_messages[-1]["level"], "setup")
        mocked.assert_not_called()

    def test_full_discussion_ends_with_agreed_conclusion(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        msgs = fake.session_state.ws_messages
        self.assertEqual([m["kind"] for m in msgs], ["user", "sources"] + ["turn"] * 4 + ["conclusion"])
        self.assertEqual([m["side"] for m in msgs[2:6]], list("ABAB"))
        self.assertEqual([m["phase"] for m in msgs[2:6]], ["opening", "convergence", "closing", "conclusion"])
        result = msgs[-1]["result"]
        self.assertEqual(result["agreement_status"], "agreed")
        self.assertIn("Argon2id", result["conclusion"]["decision"])
        self.assertIs(fake.session_state.last_result, result)

    def test_failure_midway_keeps_partial_transcript_without_conclusion_claim(self):
        calls = {"n": 0}

        def flaky(messages, **kwargs):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("boom")
            return fake_llm(messages, **kwargs)

        fake, _ = self.run_ws("Choose password hashing for our web app", llm=flaky, turns=8)
        msgs = fake.session_state.ws_messages
        self.assertEqual([m["kind"] for m in msgs], ["user", "sources", "turn", "turn", "notice", "conclusion"])
        self.assertEqual(msgs[4]["level"], "error")
        self.assertEqual(msgs[-1]["result"]["agreement_status"], "incomplete")

    def test_quick_start_pending_prompt_is_processed(self):
        fake = _fake_streamlit(None)
        ws = _load_workspace(fake)
        fake.session_state["ws_pending"] = "Plan a post-quantum migration for long-lived data"
        fake.session_state["ws_turns"] = 4
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            ws.render_workspace(True)
        self.assertEqual(fake.session_state.ws_messages[0]["kind"], "user")
        self.assertEqual(fake.session_state.ws_messages[-1]["kind"], "conclusion")
        self.assertIsNone(fake.session_state.ws_pending)

    def test_persona_b_resets_if_it_matches_a(self):
        fake = _fake_streamlit(None)
        ws = _load_workspace(fake)
        fake.session_state["ws_persona_a"] = "Software Developer"
        fake.session_state["ws_persona_b"] = "Software Developer"
        ws.render_workspace(True)
        self.assertNotEqual(fake.session_state.ws_persona_a, fake.session_state.ws_persona_b)

    def test_history_rerenders_from_state(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        fake.chat_input.return_value = None
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm) as mocked:
            self.ws.render_workspace(True)  # a second script run must only re-render history
        mocked.assert_not_called()
        self.assertEqual(len(fake.session_state.ws_messages), 7)

    def test_exact_turn_count_is_respected(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=7)
        msgs = fake.session_state.ws_messages
        self.assertEqual(sum(m["kind"] == "turn" for m in msgs), 7)
        self.assertEqual(msgs[-1]["result"]["metadata"]["turns_requested"], 7)

    def test_completed_decision_is_saved_to_history(self):
        from utils.history_store import list_history
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        saved = list_history()
        self.assertEqual(len(saved), 1)
        self.assertEqual(fake.session_state.last_result["history_id"], saved[0]["id"])

    def test_history_saving_can_be_switched_off(self):
        from utils.history_store import list_history
        fake = _fake_streamlit("Choose password hashing for our web app")
        ws = _load_workspace(fake)
        fake.session_state["ws_turns"] = 4
        fake.session_state["ws_save_history"] = False
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            ws.render_workspace(True)
        self.assertEqual(list_history(), [])
        self.assertNotIn("history_id", fake.session_state.ws_messages[-1]["result"])

    def test_stress_test_appends_three_turns_and_an_advisory_notice(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        rid = fake.session_state.ws_messages[-1]["id"]
        fake.chat_input.return_value = None
        fake.session_state["ws_stress"] = (rid, "budget")
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            self.ws.render_workspace(True)
        kinds = [m["kind"] for m in fake.session_state.ws_messages]
        self.assertEqual(kinds, ["user", "sources"] + ["turn"] * 4 + ["conclusion", "user", "turn", "turn", "turn", "notice"])
        stress_turns = [m for m in fake.session_state.ws_messages if m["kind"] == "turn"][4:]
        self.assertEqual([m["phase"] for m in stress_turns], ["stress", "stress", "stress_outcome"])
        self.assertTrue(all(m["note"] == "Scenario: Limited budget" for m in stress_turns))
        self.assertIsNone(fake.session_state.ws_stress)

    def test_stress_test_needs_api_key(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        rid = fake.session_state.ws_messages[-1]["id"]
        fake.chat_input.return_value = None
        fake.session_state["ws_stress"] = (rid, "audit")
        with patch("services.dialogue_manager.chat_completion") as mocked:
            self.ws.render_workspace(False)
        self.assertEqual(fake.session_state.ws_messages[-1]["level"], "setup")
        mocked.assert_not_called()

    def test_open_saved_decision_in_workspace(self):
        from utils.history_store import list_history
        self.run_ws("Choose password hashing for our web app", turns=4)
        record = list_history()[0]
        fake2 = _fake_streamlit(None)
        ws2 = _load_workspace(fake2)
        ws2.open_result_in_workspace(record)
        kinds = [m["kind"] for m in fake2.session_state.ws_messages]
        self.assertEqual(kinds, ["user", "sources"] + ["turn"] * 4 + ["conclusion"])
        self.assertEqual(fake2.session_state.page, "Stakeholder Dialogue")
        self.assertEqual(fake2.session_state.ws_messages[-1]["result"]["history_id"], record["id"])

    def test_rag_grounds_the_discussion_by_default(self):
        fake, _ = self.run_ws("Choose password hashing for our web app", turns=4)
        msgs = fake.session_state.ws_messages
        self.assertEqual(msgs[1]["kind"], "sources")
        self.assertTrue(msgs[1]["sources"])
        result = msgs[-1]["result"]
        self.assertEqual(result["sources"], msgs[1]["sources"])
        self.assertEqual(result["evaluation"]["grounding"]["sources_retrieved"], len(result["sources"]))
        self.assertTrue(result["metadata"]["retrieval"]["enabled"])

    def test_rag_can_be_switched_off(self):
        fake = _fake_streamlit("Choose password hashing for our web app")
        ws = _load_workspace(fake)
        fake.session_state["ws_turns"] = 4
        fake.session_state["ws_use_rag"] = False
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[0]["content"])
            return fake_llm(messages, **kwargs)

        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            ws.render_workspace(True)
        kinds = [m["kind"] for m in fake.session_state.ws_messages]
        self.assertNotIn("sources", kinds)
        self.assertEqual(fake.session_state.ws_messages[-1]["result"]["sources"], [])
        self.assertTrue(all("REFERENCE NOTES" not in text for text in seen))

    def test_retrieved_notes_reach_every_model_call(self):
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[0]["content"])
            return fake_llm(messages, **kwargs)

        self.run_ws("Choose password hashing for our web app", turns=4, llm=spy)
        self.assertEqual(len(seen), 4)
        self.assertTrue(all("[S1]" in text and "untrusted" in text for text in seen))

    def test_no_relevant_passages_still_completes_with_an_explanation(self):
        fake = _fake_streamlit("Choose password hashing for our web app")
        ws = _load_workspace(fake)
        fake.session_state["ws_turns"] = 4
        with patch.object(ws, "retrieve_sources", return_value=[]), \
                patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            ws.render_workspace(True)
        msgs = fake.session_state.ws_messages
        self.assertEqual((msgs[1]["kind"], msgs[1]["sources"]), ("sources", []))
        self.assertEqual(msgs[-1]["result"]["agreement_status"], "agreed")

    def test_retrieval_failure_does_not_block_the_discussion(self):
        fake = _fake_streamlit("Choose password hashing for our web app")
        ws = _load_workspace(fake)
        fake.session_state["ws_turns"] = 4
        with patch.object(ws, "retrieve_sources", side_effect=RuntimeError("index broken")), \
                patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            ws.render_workspace(True)
        self.assertEqual(fake.session_state.ws_messages[-1]["kind"], "conclusion")


class KnowledgePageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.dict(os.environ, {"CIPHERBRIDGE_DATA_DIR": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: sys.modules.pop("ui.knowledge", None))

    def _fake(self, query="", button_key=None):
        fake = _fake_streamlit(None)
        fake.text_input.side_effect = lambda label, key=None, **kw: {"kb_query": query, "kb_paste_name_0": "Pairing notes"}.get(key, "")
        fake.button.side_effect = lambda label, key=None, **kw: key == button_key
        fake.file_uploader.return_value = None
        return fake

    def _load(self, fake):
        sys.modules.pop("ui.knowledge", None)
        with patch.dict(sys.modules, {"streamlit": fake}):
            return importlib.import_module("ui.knowledge")

    def test_page_renders_and_searches(self):
        fake = self._fake(query="AES-GCM nonce reuse")
        self._load(fake).render_knowledge()
        fake.info.assert_not_called()  # the query has results, so no "nothing found" message

    def test_search_without_results_shows_guidance(self):
        fake = self._fake(query="best pasta recipe")
        self._load(fake).render_knowledge()
        fake.info.assert_called_once()

    def test_adding_pasted_notes_makes_them_searchable(self):
        from services.rag import get_knowledge_base
        fake = self._fake(button_key="kb_add")
        fake.session_state["kb_paste_text_0"] = "## Pairing\nBLS signatures aggregate many signatures into one short signature."
        self._load(fake).render_knowledge()
        self.assertIn("Added", fake.session_state["kb_flash"])
        self.assertEqual(fake.session_state["kb_upload_n"], 1)
        hits = get_knowledge_base().search("BLS aggregate signatures", top_k=3)
        self.assertTrue(any(h["origin"] == "user" for h in hits))

    def test_adding_nothing_shows_an_error(self):
        fake = self._fake(button_key="kb_add")
        self._load(fake).render_knowledge()
        fake.error.assert_called_once()


class McpPageTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("ui.mcp_page", None)

    def _load(self, fake):
        sys.modules.pop("ui.mcp_page", None)
        with patch.dict(sys.modules, {"streamlit": fake}):
            return importlib.import_module("ui.mcp_page")

    def test_page_runs_a_tool_in_process(self):
        import json
        fake = _fake_streamlit(None)
        fake.session_state["mcp_tool"] = "check_cryptography_scope"
        fake.session_state["mcp_args_check_cryptography_scope"] = json.dumps({"topic": "Recommend romantic movies"})
        fake.button.side_effect = lambda label, key=None, **kw: key == "mcp_run"
        self._load(fake).render_mcp(True)
        fake.success.assert_called_once()
        shown = [c.args[0] for c in fake.code.call_args_list if c.args]
        self.assertTrue(any('"status": "rejected"' in text for text in shown))

    def test_invalid_json_and_tool_errors_are_reported(self):
        fake = _fake_streamlit(None)
        fake.session_state["mcp_tool"] = "check_cryptography_scope"
        fake.session_state["mcp_args_check_cryptography_scope"] = "{not json"
        fake.button.side_effect = lambda label, key=None, **kw: key == "mcp_run"
        self._load(fake).render_mcp(True)
        fake.error.assert_called_once()
        fake2 = _fake_streamlit(None)
        fake2.session_state["mcp_tool"] = "check_cryptography_scope"
        fake2.session_state["mcp_args_check_cryptography_scope"] = "{}"
        fake2.button.side_effect = lambda label, key=None, **kw: key == "mcp_run"
        self._load(fake2).render_mcp(True)
        fake2.error.assert_called_once()

    def test_client_config_points_at_the_server_script(self):
        mod = self._load(_fake_streamlit(None))
        cfg = mod._client_config()["mcpServers"]["cipherbridge-concord"]
        self.assertTrue(cfg["args"][0].endswith("__main__.py"))
        self.assertTrue(os.path.exists(cfg["args"][0]))


class HistoryPageTests(unittest.TestCase):
    def test_history_page_renders_saved_records_and_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CIPHERBRIDGE_DATA_DIR": tmp}):
            from utils.history_store import save_result
            fake = _fake_streamlit(None)
            fake.text_input.return_value = ""
            fake.session_state["ws_pdf_cache"] = {}
            sys.modules.pop("ui.workspace", None)
            sys.modules.pop("ui.history", None)
            with patch.dict(sys.modules, {"streamlit": fake}):
                history = importlib.import_module("ui.history")
                history.render_history()  # empty state must not crash
                fake.info.assert_called_once()
                with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
                    from services.dialogue_manager import generate_dialogue
                    result = generate_dialogue("Password hashing choice", "Cryptographer / Security Researcher", "Software Developer", 4)
                save_result(result)
                history.render_history()
                metric_calls = [c for col in fake._columns for c in col.metric.call_args_list]
                self.assertIn(call("Saved decisions", 1), metric_calls)
            sys.modules.pop("ui.workspace", None)
            sys.modules.pop("ui.history", None)


if __name__ == "__main__":
    unittest.main()

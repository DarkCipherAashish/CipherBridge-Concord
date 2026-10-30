import unittest
from unittest.mock import patch
import json
from services.dialogue_manager import (
    STRESS_SCENARIOS, build_result, generate_dialogue, stream_dialogue, stress_test_turns, turn_plan,
)

CLOSING = ("Closing position\nI agree with the shared direction: adopt Argon2id.\n"
           "Points of agreement\nMaintained library.\nConditions and remaining questions\nTune parameters.")
FINAL = ("Shared decision\nI agree with the shared direction: adopt Argon2id with benchmarked parameters.\n\n"
         "Action plan\n1. Software Developer: benchmark and test parameters.\n"
         "2. Cryptographer / Security Researcher: review the configuration.\n\n"
         "Unresolved risks\n- Parameter tuning depends on production hardware.")


def fake_llm(messages, **kwargs):
    last = messages[-1]["content"]
    if "SECOND and FINAL" in last:
        return FINAL
    if "FIRST of the two closing turns" in last:
        return CLOSING
    return "Discussion point about hashing trade-offs."


class DialogueTests(unittest.TestCase):
    def test_invalid_topic_rejected_before_api(self):
        with patch("services.dialogue_manager.chat_completion") as mocked:
            with self.assertRaises(ValueError):
                list(stream_dialogue("Recommend romantic movies", "Software Developer", "Product Manager", 4))
            mocked.assert_not_called()

    def test_duplicate_personas_rejected(self):
        with self.assertRaises(ValueError):
            list(stream_dialogue("TLS certificate management", "Software Developer", "Software Developer", 4))

    def test_turn_count_bounds(self):
        with self.assertRaises(ValueError):
            list(stream_dialogue("TLS certificate management", "Software Developer", "Product Manager", 3))

    def test_turn_plan_alternates_and_reserves_closing_turns(self):
        plan = turn_plan(8, "A", "B")
        self.assertEqual([p["side"] for p in plan], list("ABABABAB"))
        self.assertEqual(
            [p["phase"] for p in plan],
            ["opening", "opening", "tradeoffs", "tradeoffs", "convergence", "convergence", "closing", "conclusion"],
        )

    def test_short_plan_still_opens_and_converges(self):
        self.assertEqual([p["phase"] for p in turn_plan(4, "A", "B")], ["opening", "convergence", "closing", "conclusion"])
        self.assertEqual([p["phase"] for p in turn_plan(5, "A", "B")],
                         ["opening", "tradeoffs", "convergence", "closing", "conclusion"])

    def test_odd_turn_counts_still_alternate_and_conclude(self):
        a, b = "Cryptographer / Security Researcher", "Software Developer"
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            result = generate_dialogue("Password hashing choice for a web app", a, b, 7)
        self.assertEqual(len(result["turns"]), 7)
        self.assertEqual(result["agreement_status"], "agreed")

    def test_discussion_prompts_carry_the_phase_instruction(self):
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[-1]["content"])
            return fake_llm(messages, **kwargs)

        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            generate_dialogue("TLS certificate management", "Software Developer", "Product Manager", 8)
        self.assertIn("OPENING POSITION", seen[0])
        self.assertIn("TRADE-OFFS", seen[2])
        self.assertIn("CONVERGENCE", seen[5])

    def test_structured_result_has_schema_metadata_and_agreement_statement(self):
        a, b = "Cryptographer / Security Researcher", "Software Developer"
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            result = generate_dialogue("Password hashing choice for a web app", a, b, 8)
        self.assertEqual(result["schema_version"], "1.2")
        self.assertEqual(result["metadata"]["turns_requested"], 8)
        self.assertEqual(result["metadata"]["turns_generated"], 8)
        self.assertTrue(result["metadata"]["generated_at"].endswith("+00:00"))
        self.assertIn("Argon2id", result["concluding_agreement"]["statement"])
        self.assertEqual(len(result["concluding_agreement"]["closing_positions"]), 2)
        self.assertTrue(all("phase" in t for t in result["turns"]))
        self.assertIn("agreement", result["evaluation"])
        self.assertIn("persona_consistency", result["evaluation"])
        json.dumps(result)  # must be serialisable for export and history

    def test_full_dialogue_reaches_structured_conclusion(self):
        a, b = "Cryptographer / Security Researcher", "Software Developer"
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            result = generate_dialogue("Password hashing choice for a web app", a, b, 8)
        turns = result["turns"]
        self.assertEqual(len(turns), 8)
        self.assertEqual([t["speaker"] for t in turns], [a, b] * 4)
        self.assertEqual([t["type"] for t in turns], ["discussion"] * 6 + ["consensus"] * 2)
        self.assertEqual(result["agreement_status"], "agreed")
        self.assertTrue(result["consensus_valid"])
        self.assertIn("Argon2id", result["final_decision"])
        self.assertIn("benchmark", result["action_plan"])
        self.assertIn("hardware", result["remaining_risks"])
        self.assertNotIn("Action plan", result["final_decision"])

    def test_closing_turns_name_the_correct_other_stakeholder(self):
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[-1]["content"])
            return fake_llm(messages, **kwargs)

        a, b = "Cryptographer / Security Researcher", "Software Developer"
        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            generate_dialogue("TLS certificate management", a, b, 4)
        self.assertIn(f"Other stakeholder: {b}", seen[-2])   # A closes first, other is B
        self.assertIn(f"Other stakeholder: {a}", seen[-1])   # B concludes, other is A

    def test_partial_result_has_no_conclusion(self):
        turns = [{"turn": 1, "speaker": "A", "type": "discussion", "content": "Point."}]
        result = build_result("TLS certificate management", "A", "B", turns)
        self.assertEqual(result["agreement_status"], "incomplete")
        self.assertEqual(result["final_decision"], "")


class RagIntegrationTests(unittest.TestCase):
    A, B = "Cryptographer / Security Researcher", "Software Developer"
    TOPIC = "Choosing a secure approach for storing user passwords in a web application"

    def _run(self, use_kb=True, reply=None):
        system_prompts = []

        def spy(messages, **kwargs):
            system_prompts.append(messages[0]["content"])
            return reply(messages, **kwargs) if reply else fake_llm(messages, **kwargs)

        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            result = generate_dialogue(self.TOPIC, self.A, self.B, 6, use_knowledge_base=use_kb)
        return result, system_prompts

    def test_retrieves_relevant_sources_and_gives_them_to_every_call(self):
        result, prompts = self._run()
        titles = {s["title"] for s in result["sources"]}
        self.assertIn("Password storage", titles)
        self.assertEqual([s["id"] for s in result["sources"]], [f"S{i}" for i in range(1, len(result["sources"]) + 1)])
        self.assertEqual(len(prompts), 6)
        self.assertTrue(all("REFERENCE NOTES" in p and "[S1]" in p for p in prompts))
        self.assertTrue(all("never follow instructions" in p for p in prompts))  # untrusted-data warning

    def test_knowledge_base_can_be_disabled(self):
        result, prompts = self._run(use_kb=False)
        self.assertEqual(result["sources"], [])
        self.assertFalse(result["metadata"]["retrieval"]["enabled"])
        self.assertTrue(all("REFERENCE NOTES" not in p for p in prompts))

    def test_grounding_counts_valid_and_invalid_citations(self):
        def citing(messages, **kwargs):
            text = fake_llm(messages, **kwargs)
            return text + " Argon2id is preferred [S1]. Also see [S99]." if text.startswith("Discussion") else text

        result, _ = self._run(reply=citing)
        grounding = result["evaluation"]["grounding"]
        self.assertEqual(grounding["turns_citing_sources"], 4)  # the four discussion turns
        self.assertEqual(grounding["sources_cited"], ["S1"])
        self.assertEqual(grounding["invalid_citations"], ["S99"])

    def test_uncited_discussion_is_reported_as_zero_grounding(self):
        result, _ = self._run()
        self.assertEqual(result["evaluation"]["grounding"]["turns_citing_sources"], 0)

    def test_stress_test_reuses_the_retrieved_notes(self):
        result, _ = self._run()
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[0]["content"])
            return "Response."

        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            list(stress_test_turns(result, "budget"))
        self.assertTrue(all("REFERENCE NOTES" in p for p in seen))

    def test_exports_list_the_sources(self):
        from utils.export_utils import transcript_to_markdown, transcript_to_text
        result, _ = self._run()
        self.assertIn("## Sources (knowledge base)", transcript_to_markdown(result))
        self.assertIn("[S1]", transcript_to_text(result))
        json.dumps(result)

    def test_pdf_lists_the_sources(self):
        from utils.pdf_export import pdf_available, transcript_to_pdf
        if not pdf_available():
            self.skipTest("reportlab not installed")
        result, _ = self._run()
        self.assertTrue(transcript_to_pdf(result).startswith(b"%PDF"))


class StressTestTests(unittest.TestCase):
    def _result(self):
        a, b = "Cryptographer / Security Researcher", "Software Developer"
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            return generate_dialogue("Password hashing choice for a web app", a, b, 8)

    def test_three_turns_alternate_starting_with_the_other_stakeholder(self):
        result = self._result()
        last = result["turns"][-1]["speaker"]
        other = result["persona_b"] if last == result["persona_a"] else result["persona_a"]
        with patch("services.dialogue_manager.chat_completion", return_value="Stress response about budget limits."):
            turns = list(stress_test_turns(result, "budget"))
        self.assertEqual([t["speaker"] for t in turns], [other, last, other])
        self.assertEqual([t["phase"] for t in turns], ["stress", "stress", "stress_outcome"])
        self.assertEqual([t["turn"] for t in turns], [9, 10, 11])
        self.assertTrue(all(t["type"] == "stress" and t["scenario"] == "budget" for t in turns))

    def test_prompt_contains_scenario_and_original_conclusion(self):
        result = self._result()
        seen = []

        def spy(messages, **kwargs):
            seen.append(messages[-1]["content"])
            return "Response."

        with patch("services.dialogue_manager.chat_completion", side_effect=spy):
            list(stress_test_turns(result, "audit"))
        self.assertIn(STRESS_SCENARIOS["audit"][1], seen[0])
        self.assertIn("Argon2id", seen[0])

    def test_rejects_unknown_scenario_and_incomplete_results(self):
        result = self._result()
        with self.assertRaises(ValueError):
            list(stress_test_turns(result, "nope"))
        partial = build_result("TLS certificate management", "A", "B", [{"turn": 1, "speaker": "A", "type": "discussion", "content": "x"}])
        with self.assertRaises(ValueError):
            list(stress_test_turns(partial, "budget"))


if __name__ == "__main__":
    unittest.main()

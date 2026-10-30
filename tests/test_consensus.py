import unittest
from services.consensus import validate_consensus, get_consensus_report

def sample():
    return [
      {"turn":1,"speaker":"A","type":"discussion","content":"We need to protect stored credentials."},
      {"turn":2,"speaker":"B","type":"discussion","content":"Use a maintained password-hashing library and verify settings."},
      {"turn":3,"speaker":"A","type":"consensus","content":"Areas of agreement: we agree to test a maintained password-hashing design. Remaining questions: deployment parameters. Proposed next step: verify configuration."},
      {"turn":4,"speaker":"B","type":"consensus","content":"Shared decision: We agree to use a maintained password-hashing library after review. Action plan: implement a prototype, test parameters, and review access controls. Unresolved risks: configuration and operational mistakes."},
    ]
class ConsensusTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(validate_consensus(sample()))
    def test_report(self): self.assertTrue(get_consensus_report(sample())["valid"])
    def test_rejects_missing_action_plan(self):
        turns=sample(); turns[-1]["content"]="Shared decision: We agree to proceed. Unresolved risks: unknown."
        self.assertFalse(validate_consensus(turns))
    def test_rejects_missing_decision(self):
        turns=sample(); turns[-1]["content"]="We agree. Action plan: test the system. Unresolved risks: unknown."
        self.assertFalse(validate_consensus(turns))
    def test_rejects_wrong_turn_number(self):
        turns=sample(); turns[1]["turn"]=3
        self.assertFalse(validate_consensus(turns))
    def test_rejects_non_alternating_discussion(self):
        turns=sample(); turns[1]["speaker"]="A"
        self.assertFalse(validate_consensus(turns))
    def test_rejects_incomplete(self): self.assertFalse(validate_consensus([]))
    def test_both_closing_turns_must_explicitly_agree(self):
        turns=sample()
        turns[-2]["content"]="Closing position: The proposal is sensible. Points of agreement: test the library. Conditions and remaining questions: deployment review."
        self.assertFalse(validate_consensus(turns))
    def test_all_turns_must_alternate_including_closing_exchange(self):
        turns=sample()
        turns[-2]["speaker"]="B"
        self.assertFalse(validate_consensus(turns))
    def test_non_agreement_is_not_reported_as_consensus(self):
        turns=sample()
        turns[-1]["content"]="Shared decision: Full agreement has not been reached. Action plan: review the design and test the prototype. Unresolved risks: implementation assumptions."
        self.assertFalse(validate_consensus(turns))
if __name__=="__main__": unittest.main()


class ConclusionParsingTests(unittest.TestCase):
    def test_extracts_plain_headings(self):
        from services.consensus import extract_conclusion_sections
        text = ("Shared decision\nI agree with the shared direction: use Argon2id.\n\n"
                "Action plan\n1. Developer: benchmark.\n2. Cryptographer: review.\n\n"
                "Unresolved risks\n- Tuning depends on hardware.")
        s = extract_conclusion_sections(text)
        self.assertIn("Argon2id", s["decision"])
        self.assertIn("benchmark", s["action_plan"])
        self.assertIn("hardware", s["risks"])

    def test_extracts_markdown_and_inline_headings(self):
        from services.consensus import extract_conclusion_sections
        text = "**Shared decision:** We agree on X.\n### Action plan\n1. Verify X.\n**Unresolved risks:** Y."
        s = extract_conclusion_sections(text)
        self.assertEqual(s["decision"], "We agree on X.")
        self.assertEqual(s["action_plan"], "1. Verify X.")
        self.assertEqual(s["risks"], "Y.")

    def test_text_without_headings_becomes_decision(self):
        from services.consensus import extract_conclusion_sections
        s = extract_conclusion_sections("We will adopt the library.")
        self.assertEqual(s["decision"], "We will adopt the library.")
        self.assertEqual((s["action_plan"], s["risks"]), ("", ""))

    def test_agreement_status(self):
        from services.consensus import agreement_status
        self.assertEqual(agreement_status(sample()), "agreed")
        turns = sample()
        turns[-1]["content"] = "Shared decision: Full agreement has not been reached. Action plan: review. Unresolved risks: many."
        self.assertEqual(agreement_status(turns), "partial")
        self.assertEqual(agreement_status(sample()[:2]), "incomplete")
        self.assertEqual(agreement_status([]), "incomplete")

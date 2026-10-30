import unittest
from services.evaluation import agreement_evaluation, persona_consistency
from tests.test_dialogue import CLOSING, FINAL

A, B = "Cryptographer / Security Researcher", "Software Developer"


def turns(final=FINAL, closing=CLOSING):
    return [
        {"turn": 1, "speaker": A, "type": "discussion", "content": "Attackers and the threat model matter; follow NIST standards."},
        {"turn": 2, "speaker": B, "type": "discussion", "content": "We need a maintained library with good performance and tests."},
        {"turn": 3, "speaker": A, "type": "consensus", "content": closing},
        {"turn": 4, "speaker": B, "type": "consensus", "content": final},
    ]


class EvaluationTests(unittest.TestCase):
    def test_strong_agreement_scores_full_marks(self):
        result = agreement_evaluation(turns(), A, B)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["label"], "Strong")
        self.assertTrue(all(c["passed"] for c in result["checks"]))
        self.assertEqual(len(result["checks"]), 7)

    def test_missing_risks_and_verification_lower_the_score(self):
        weak_final = "Shared decision\nI agree with the shared direction: adopt X.\n\nAction plan\n1. Do the work."
        result = agreement_evaluation(turns(final=weak_final), A, B)
        failed = {c["name"] for c in result["checks"] if not c["passed"]}
        self.assertIn("Unresolved risks are listed", failed)
        self.assertIn("The action plan includes verification steps", failed)
        self.assertLess(result["score"], 85)

    def test_no_agreement_statement_fails_that_check(self):
        result = agreement_evaluation(turns(closing="Closing position\nStill unsure."), A, B)
        failed = {c["name"] for c in result["checks"] if not c["passed"]}
        self.assertIn("Both closing turns state agreement explicitly", failed)

    def test_incomplete_discussion_is_not_scored(self):
        result = agreement_evaluation(turns()[:2], A, B)
        self.assertEqual((result["score"], result["label"], result["checks"]), (0, "Not available", []))

    def test_persona_consistency_reflects_role_terms(self):
        info = persona_consistency(turns(), A, B)
        self.assertGreaterEqual(info["A"]["coverage"], 0.5)
        self.assertGreaterEqual(info["B"]["coverage"], 0.5)
        self.assertIn("attack", info["A"]["terms_used"])
        self.assertIn("librar", info["B"]["terms_used"])

    def test_off_role_turns_score_low(self):
        generic = [{"turn": i, "speaker": A if i % 2 else B, "type": "discussion", "content": "Sounds nice."} for i in range(1, 5)]
        info = persona_consistency(generic, A, B)
        self.assertEqual((info["A"]["coverage"], info["A"]["label"]), (0.0, "Low"))


if __name__ == "__main__":
    unittest.main()

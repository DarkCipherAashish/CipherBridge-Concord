import json, unittest
from utils.export_utils import transcript_to_json, transcript_to_markdown, transcript_to_text


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.result = {"topic":"TLS certificate rotation","persona_a":"A","persona_b":"B",
          "turns":[{"turn":1,"speaker":"A","type":"discussion","content":"Review the expiry process."}],
          "consensus_valid":False,"consensus_note":"Incomplete"}
        self.agreed = dict(self.result, agreement_status="agreed",
            conclusion={"decision": "Automate renewal.", "action_plan": "1. Test renewal.", "risks": "Clock drift."})

    def test_txt_contains_transcript(self):
        text = transcript_to_text(self.result)
        self.assertIn("TLS certificate rotation", text)
        self.assertIn("Review the expiry process.", text)

    def test_json_round_trip(self):
        parsed = json.loads(transcript_to_json(self.result))
        self.assertEqual(parsed["turns"][0]["speaker"], "A")
        self.assertEqual(parsed["topic"], self.result["topic"])

    def test_markdown_includes_final_conclusion_when_agreed(self):
        md = transcript_to_markdown(self.agreed)
        for expected in ("## Final conclusion", "Automate renewal.", "Test renewal.", "Clock drift.", "## Transcript"):
            self.assertIn(expected, md)

    def test_markdown_omits_conclusion_for_partial_transcript(self):
        md = transcript_to_markdown(dict(self.result, agreement_status="incomplete"))
        self.assertNotIn("## Final conclusion", md)
        self.assertIn("Incomplete", md)

    def test_txt_includes_conclusion_when_agreed(self):
        self.assertIn("FINAL CONCLUSION", transcript_to_text(self.agreed))


if __name__ == "__main__":
    unittest.main()

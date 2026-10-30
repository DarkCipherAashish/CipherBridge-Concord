import unittest
from unittest.mock import patch

from services.dialogue_manager import generate_dialogue
from tests.test_dialogue import fake_llm
from utils.pdf_export import _text, pdf_available, transcript_to_pdf


@unittest.skipUnless(pdf_available(), "reportlab is not installed")
class PdfExportTests(unittest.TestCase):
    def _result(self, turns=4):
        with patch("services.dialogue_manager.chat_completion", side_effect=fake_llm):
            return generate_dialogue("Password hashing choice", "Cryptographer / Security Researcher", "Software Developer", turns)

    def test_produces_a_pdf(self):
        pdf = transcript_to_pdf(self._result())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 2000)

    def test_text_is_readable_in_the_pdf(self):
        try:
            import pypdf
            from io import BytesIO
        except ImportError:
            self.skipTest("pypdf not installed")
        text = "".join(page.extract_text() for page in pypdf.PdfReader(BytesIO(transcript_to_pdf(self._result()))).pages)
        for expected in ("Decision Report", "Argon2id", "Action plan".upper(), "Transcript"):
            self.assertIn(expected, text)

    def test_hostile_or_unusual_text_does_not_break_the_pdf(self):
        result = self._result()
        result["topic"] = "Use <b>bold</b> & <script>alert(1)</script> → 🔐 “quotes” — dashes"
        result["turns"][0]["content"] = "**bold** `code` <unclosed & ampersand\n- bullet\n1. numbered\n# heading ✓"
        self.assertTrue(transcript_to_pdf(result).startswith(b"%PDF"))

    def test_partial_result_still_exports(self):
        result = self._result()
        result["turns"] = result["turns"][:2]
        result["agreement_status"] = "incomplete"
        self.assertTrue(transcript_to_pdf(result).startswith(b"%PDF"))

    def test_text_helper_escapes_markup_and_drops_unsupported_characters(self):
        self.assertEqual(_text("a < b & c"), "a &lt; b &amp; c")
        self.assertNotIn("🔐", _text("key 🔐"))


if __name__ == "__main__":
    unittest.main()

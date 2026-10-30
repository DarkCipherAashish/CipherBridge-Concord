import os, unittest
from unittest.mock import patch
from services.llm_client import _get_client, LLMConfigurationError

class LLMClientTests(unittest.TestCase):
    def test_missing_key_is_controlled_error(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaises(LLMConfigurationError):
                _get_client()
if __name__ == "__main__": unittest.main()

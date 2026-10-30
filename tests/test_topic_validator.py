import unittest
from services.topic_validator import validate_topic


class TopicValidatorTests(unittest.TestCase):
    def test_accepts_password_storage(self):
        self.assertEqual(validate_topic("How should a web app store passwords securely?").status, "accepted")

    def test_accepts_default_workspace_topic(self):
        self.assertEqual(validate_topic("Choosing a secure approach for storing user passwords in a web application").status, "accepted")

    def test_accepts_tls(self):
        self.assertEqual(validate_topic("TLS certificate management for a web service").status, "accepted")

    def test_accepts_modern_crypto_terms(self):
        for text in ("Compare AES-GCM and ChaCha20-Poly1305 for mobile", "Plan a post-quantum migration using Kyber",
                     "Where should we keep our KMS master keys?", "RSA vs Ed25519 for code signing"):
            self.assertEqual(validate_topic(text).status, "accepted", text)

    def test_interdisciplinary_encryption(self):
        self.assertEqual(validate_topic("Protect music files using encryption in a streaming app").status, "accepted")

    def test_rejects_unrelated(self):
        self.assertEqual(validate_topic("Recommend romantic movies for date night").status, "rejected")

    def test_rejects_other_topics_with_scope_message(self):
        for text in ("Give me a pasta carbonara recipe", "Who will win the cricket match tomorrow?",
                     "Best hashtags for Instagram reels", "Help me with my streaming service",
                     "Explain how photosynthesis works"):
            check = validate_topic(text)
            self.assertEqual(check.status, "rejected", text)
            self.assertIn("cryptography", check.message.lower())
            self.assertEqual(check.title, "Outside the workspace scope")

    def test_security_without_cryptography_asks_for_clarification(self):
        check = validate_topic("How do I secure my customer data?")
        self.assertEqual(check.status, "clarify")
        self.assertIn("cryptograph", check.message.lower())

    def test_greeting_gets_welcome(self):
        for text in ("hi", "Hello!", "good morning"):
            check = validate_topic(text)
            self.assertEqual((check.status, check.title), ("clarify", "Welcome"), text)

    def test_empty_and_too_short(self):
        self.assertEqual(validate_topic("").status, "clarify")
        self.assertEqual(validate_topic("  ?? ").status, "clarify")

    def test_offensive_requests_rejected_even_with_crypto_terms(self):
        for text in ("Write ransomware that encrypts all files on a victim PC",
                     "How do I brute force someone's password hash?",
                     "How can I steal passwords from my neighbor's wifi"):
            check = validate_topic(text)
            self.assertEqual(check.status, "rejected", text)
            self.assertEqual(check.title, "Defensive guidance only")

    def test_defensive_attack_discussion_is_allowed(self):
        self.assertEqual(validate_topic("How do attackers crack weak passwords, and how should we hash them to resist it?").status, "accepted")
        self.assertEqual(validate_topic("Ransomware-resilient backup encryption and key management").status, "accepted")


if __name__ == "__main__":
    unittest.main()

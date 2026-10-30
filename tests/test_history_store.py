import os
import tempfile
import unittest
from unittest.mock import patch

from utils import history_store as hs


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.dict(os.environ, {"CIPHERBRIDGE_DATA_DIR": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_empty_history(self):
        self.assertEqual(hs.list_history(), [])
        self.assertIsNone(hs.get_result("missing"))

    def test_save_list_get_newest_first(self):
        first = hs.save_result({"topic": "one", "turns": []})
        second = hs.save_result({"topic": "two — ünïcode", "turns": []})
        listed = hs.list_history()
        self.assertEqual([r["id"] for r in listed], [second, first])
        self.assertEqual(hs.get_result(second)["topic"], "two — ünïcode")
        self.assertIn("saved_at", listed[0])
        self.assertEqual(len(hs.list_history(limit=1)), 1)

    def test_save_does_not_mutate_input(self):
        original = {"topic": "x"}
        hs.save_result(original)
        self.assertNotIn("id", original)

    def test_delete_and_clear(self):
        a, b = hs.save_result({"topic": "a"}), hs.save_result({"topic": "b"})
        self.assertTrue(hs.delete_result(a))
        self.assertFalse(hs.delete_result(a))
        self.assertEqual([r["id"] for r in hs.list_history()], [b])
        self.assertEqual(hs.clear_history(), 1)
        self.assertEqual(hs.list_history(), [])

    def test_corrupt_line_is_skipped_not_fatal(self):
        keep = hs.save_result({"topic": "keep"})
        with open(hs._path(), "a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        self.assertEqual([r["id"] for r in hs.list_history()], [keep])
        self.assertTrue(hs.delete_result(keep))  # rewriting must also survive the corrupt line


if __name__ == "__main__":
    unittest.main()

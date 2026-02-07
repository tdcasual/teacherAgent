import unittest

from services.api.chat_dedupe_service import chat_last_user_text, chat_text_fingerprint


class ChatDedupeServiceTest(unittest.TestCase):
    def test_chat_last_user_text_picks_latest_user_message(self):
        messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "latest"},
        ]
        self.assertEqual(chat_last_user_text(messages), "latest")
        self.assertEqual(chat_last_user_text([]), "")
        self.assertEqual(chat_last_user_text({"role": "user"}), "")

    def test_chat_text_fingerprint_normalizes_whitespace_and_case(self):
        left = chat_text_fingerprint("  Hello   World  ")
        right = chat_text_fingerprint("hello world")
        self.assertEqual(left, right)
        self.assertNotEqual(left, chat_text_fingerprint("hello  world !"))


if __name__ == "__main__":
    unittest.main()

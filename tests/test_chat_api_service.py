import unittest

from services.api.chat_api_service import ChatApiDeps, start_chat_api


class ChatApiServiceTest(unittest.TestCase):
    def test_chat_api_service_start_delegates(self):
        deps = ChatApiDeps(start_chat=lambda req: {"ok": True, "request_id": getattr(req, "request_id", "")})
        req = type("Req", (), {"request_id": "req_1"})()
        payload = start_chat_api(req, deps=deps)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["request_id"], "req_1")


if __name__ == "__main__":
    unittest.main()

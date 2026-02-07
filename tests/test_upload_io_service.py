import unittest

from services.api.upload_io_service import sanitize_filename_io


class UploadIoServiceTest(unittest.TestCase):
    def test_sanitize_filename_io_keeps_safe_name(self):
        self.assertEqual(sanitize_filename_io("a.pdf"), "a.pdf")


if __name__ == "__main__":
    unittest.main()

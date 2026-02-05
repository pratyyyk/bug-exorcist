import unittest
from backend.app.main import sanitize_language

class TestLanguageAllowlist(unittest.TestCase):
    def test_valid_languages(self):
        self.assertEqual(sanitize_language("python"), "python")
        self.assertEqual(sanitize_language("javascript"), "javascript")
        self.assertEqual(sanitize_language("go-test"), "go-test")
        self.assertEqual(sanitize_language("npm-test"), "npm-test")

    def test_normalization(self):
        self.assertEqual(sanitize_language("  PYTHON  "), "python")
        self.assertEqual(sanitize_language("JavaScript"), "javascript")

    def test_mappings(self):
        self.assertEqual(sanitize_language("js"), "javascript")
        self.assertEqual(sanitize_language("golang"), "go")
        self.assertEqual(sanitize_language("shell"), "bash")
        self.assertEqual(sanitize_language("run-npm-tests"), "npm-test")

    def test_sanitization(self):
        # Injection attempts
        self.assertEqual(sanitize_language("python\nimport os"), "python")
        self.assertEqual(sanitize_language("python; rm -rf /"), "python")
        self.assertEqual(sanitize_language("javascript<script>"), "javascript")

    def test_default(self):
        self.assertEqual(sanitize_language("cobol"), "python")
        self.assertEqual(sanitize_language(""), "python")
        self.assertEqual(sanitize_language(None), "python")

if __name__ == "__main__":
    unittest.main()

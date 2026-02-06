import sys
import os
import unittest
import asyncio
from unittest.mock import MagicMock, patch

# Add project root and backend to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'backend'))

from app.sandbox import Sandbox

class TestSandboxLanguages(unittest.TestCase):
    def setUp(self):
        with patch('docker.from_env') as mock_docker:
            self.mock_client = MagicMock()
            mock_docker.return_value = self.mock_client
            self.sandbox = Sandbox()

    def test_language_mappings(self):
        """Verify that all requested languages map to the correct shell commands."""
        test_cases = [
            ("python", ["/bin/sh", "-c", "python3 -c \"import sys; exec(sys.stdin.read())\""]),
            ("javascript", ["/bin/sh", "-c", "node -e \"$(cat)\""]),
            ("nodejs", ["/bin/sh", "-c", "node -e \"$(cat)\""]),
            ("go", ["/bin/sh", "-c", "cat > main.go && go run main.go"]),
            ("go-test", ["/bin/sh", "-c", "cat > main_test.go && go test -v"]),
            ("rust", ["/bin/sh", "-c", "cat > main.rs && rustc main.rs -o main && ./main"]),
            ("cargo-test", ["/bin/sh", "-c", "cargo test"]),
            ("npm-test", ["/bin/sh", "-c", "cat > test.js && npm test -- --test-file=test.js"]),
        ]

        for lang, expected_cmd in test_cases:
            with self.subTest(lang=lang):
                asyncio.run(self.sandbox.run_code("test_code", language=lang))
                args, kwargs = self.mock_client.containers.run.call_args
                self.assertEqual(kwargs['command'], expected_cmd, f"Failed mapping for {lang}")

    def test_default_fallback(self):
        """Verify fallback to python for unknown languages."""
        asyncio.run(self.sandbox.run_code("test_code", language="unknown-lang"))
        args, kwargs = self.mock_client.containers.run.call_args
        self.assertEqual(kwargs['command'], ["/bin/sh", "-c", "python3 -c \"import sys; exec(sys.stdin.read())\""])

if __name__ == "__main__":
    unittest.main()

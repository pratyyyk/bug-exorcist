import unittest
from unittest.mock import MagicMock, patch
from app.sandbox import Sandbox

class TestSandboxIntegration(unittest.TestCase):
    def setUp(self):
        # We'll mock the docker client but verify the commands being sent
        self.mock_docker = MagicMock()
        with patch('docker.from_env', return_value=self.mock_docker):
            self.sandbox = Sandbox()

    def test_npm_test_command(self):
        code = "const assert = require('assert'); it('works', () => assert(true));"
        self.sandbox.run_code(code, language="npm-test")
        
        # Verify docker run was called with the correct command
        args, kwargs = self.mock_docker.containers.run.call_args
        self.assertIn("npm test -- --test-file=test.js", kwargs['command'][2])
        self.assertIn("cat > test.js", kwargs['command'][2])

    def test_go_test_command(self):
        code = "package main; import \"testing\"; func TestPass(t *testing.T) {}"
        self.sandbox.run_code(code, language="go-test")
        
        # Verify docker run was called with the correct command
        args, kwargs = self.mock_docker.containers.run.call_args
        self.assertIn("go test -v", kwargs['command'][2])
        self.assertIn("cat > main_test.go", kwargs['command'][2])

    def test_shell_injection_prevention(self):
        # Even with shell support, the language itself is sanitized before reaching Sandbox
        # But we test that Sandbox handles the commands correctly as lists
        code = "echo hello"
        self.sandbox.run_code(code, language="bash")
        
        args, kwargs = self.mock_docker.containers.run.call_args
        self.assertEqual(kwargs['command'], ["/bin/bash", "-c", "$(cat)"])

if __name__ == "__main__":
    unittest.main()

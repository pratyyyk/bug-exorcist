import unittest
from app.sandbox import Sandbox
import docker

class TestSandboxShell(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox()
        self.client = docker.from_env()
        # Ensure image exists
        try:
            self.client.images.get("bug-exorcist-sandbox")
        except docker.errors.ImageNotFound:
            self.skipTest("bug-exorcist-sandbox image not found. Run docker-compose build sandbox first.")

    def test_shell_features(self):
        # Test && and pipes
        code = "echo 'hello' && echo 'world' | rev"
        result = self.sandbox.run_code(code, language="bash")
        self.assertIn("hello", result)
        self.assertIn("dlrow", result)

    def test_python_with_shell(self):
        # Even python should run through shell now
        code = "print('hello' + ' ' + 'world')"
        result = self.sandbox.run_code(code, language="python")
        self.assertEqual(result.strip(), "hello world")

if __name__ == "__main__":
    unittest.main()

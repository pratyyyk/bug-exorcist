import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root and backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from core.agent import BugExorcistAgent

async def test_ollama_retry_logic():
    """
    Test that the self-healing loop works correctly with the unified architecture.
    """
    print("\n--- Testing Unified Architecture Self-Healing Loop ---")
    
    # Mock environment variables
    with patch.dict(os.environ, {
        "PRIMARY_AGENT": "ollama",
        "OLLAMA_MODEL": "llama3",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "ALLOW_MOCK_LLM": "true"
    }):
        # Mock Sandbox class to avoid Docker initialization errors
        with patch('app.sandbox.Sandbox') as MockSandbox:
            mock_sandbox_instance = MockSandbox.return_value
            mock_sandbox_instance.run_code = MagicMock()
            mock_sandbox_instance.run_code.side_effect = [
                "Error: NameError: name 'fail' is not defined", # Verification 1
                "success\n" # Verification 2
            ]

            # Mock is_ollama_available to return True
            with patch('core.agent.is_ollama_available', return_value=True):
                # Mock ChatOllama.ainvoke to simulate a failure then a success
                with patch('langchain_ollama.ChatOllama.ainvoke') as mock_invoke:
                    # Mock AI responses
                    mock_response_1 = MagicMock()
                    mock_response_1.content = """
Root Cause: Attempt 1 root cause
```python
print('fail')
```
Explanation: Attempt 1 explanation
"""
                    mock_response_2 = MagicMock()
                    mock_response_2.content = """
Root Cause: Attempt 2 root cause
```python
print('success')
```
Explanation: Attempt 2 explanation
"""
                    mock_invoke.side_effect = [mock_response_1, mock_response_2]
                    
                    # Initialize agent
                    agent = BugExorcistAgent(bug_id="test-unified-retry")
                    # Ensure the agent uses our mocked sandbox instance
                    agent.sandbox = mock_sandbox_instance
                    
                    print(f"Primary Agent: {agent.primary_agent_type}")
                    
                    # Run the self-healing loop
                    result = await agent.analyze_and_fix_with_retry(
                        error_message="Original Error",
                        code_snippet="print('bug')",
                        max_attempts=3
                    )
                    
                    # Assertions
                    print(f"Success: {result['success']}")
                    print(f"Total Attempts: {result['total_attempts']}")
                    
                    assert result['success'] is True
                    assert result['total_attempts'] == 2
                    assert "success" in result['final_fix']['fixed_code']
                    
                    print("✅ Unified architecture self-healing loop verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_ollama_retry_logic())

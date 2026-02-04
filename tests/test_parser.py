import sys
import os
from typing import Dict, Any
from unittest.mock import MagicMock, patch

# Add the project root and backend to sys.path
# Since this is in tests/, we go up one level to reach the root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'backend'))

from core.agent import BugExorcistAgent

def test_parser_with_inline_content():
    print("\n--- Testing Parser with Inline Content ---")
    
    # Mock Sandbox to avoid Docker connection
    with patch('app.sandbox.Sandbox'):
        # Mock agent for testing
        agent = BugExorcistAgent(bug_id="test-parser")
        
        ai_response = """
Root Cause: The variable 'x' was used before it was defined.
It also happened because of a missing import.

Explanation: I added the definition of 'x' and the missing import.
I also refactored the code for better readability.

```python print("fixed code here")
x = 10
print(x)
```
"""
        
        result = agent._parse_ai_response(ai_response, "original code")
        
        print(f"Root Cause: {result['root_cause']}")
        print(f"Explanation: {result['explanation']}")
        print(f"Fixed Code: {result['fixed_code']}")
        
        assert "The variable 'x'" in result['root_cause']
        assert "It also happened" in result['root_cause']
        assert "I added the definition" in result['explanation']
        assert 'print("fixed code here")' in result['fixed_code']
        assert 'x = 10' in result['fixed_code']
        
        print("✅ Parser with inline content verified successfully!")

def test_parser_with_code_fence_inline():
    print("\n--- Testing Parser with Code Fence Inline ---")
    
    with patch('app.sandbox.Sandbox'):
        agent = BugExorcistAgent(bug_id="test-parser")
        
        ai_response = """
Root Cause: Test
```python
print("line 1")
print("line 2")```
"""
        result = agent._parse_ai_response(ai_response, "original code")
        print(f"Fixed Code: {result['fixed_code']}")
        assert 'print("line 1")' in result['fixed_code']
        assert 'print("line 2")' in result['fixed_code']
        
        ai_response_2 = "Root Cause: Test\n```python print('inline')\n```"
        result_2 = agent._parse_ai_response(ai_response_2, "original code")
        print(f"Fixed Code 2: {result_2['fixed_code']}")
        assert "print('inline')" in result_2['fixed_code']

        print("✅ Parser with code fence inline verified successfully!")

if __name__ == "__main__":
    test_parser_with_inline_content()
    test_parser_with_code_fence_inline()

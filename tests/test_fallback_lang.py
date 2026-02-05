import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root and backend to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'backend'))

from core.agent import BugExorcistAgent

async def test_fallback_preserves_language():
    """
    Test that the fallback path in analyze_error correctly preserves the language parameter.
    """
    print("Running Fallback Language Preservation test...")
    
    bug_id = "test-fallback-lang"
    js_code = "console.log(x);"
    error_message = "ReferenceError: x is not defined"
    
    # 1. Setup Mock Providers
    primary_provider = MagicMock()
    # Primary fails with an exception
    primary_provider.ainvoke = AsyncMock(side_effect=Exception("Primary provider failed"))
    
    secondary_provider = MagicMock()
    # Secondary succeeds
    mock_response = MagicMock()
    mock_response.content = "**Root Cause:** ...\n**Fixed Code:**\n```javascript\nconsole.log(1);\n```\n**Explanation:** ..."
    mock_response.usage_metadata = {"input_tokens": 5, "output_tokens": 5}
    secondary_provider.ainvoke = AsyncMock(return_value=mock_response)
    secondary_provider.model_name = "secondary-model"
    
    # 2. Patch Sandbox to avoid Docker issues
    with patch('app.sandbox.Sandbox') as MockSandbox:
        # 3. Patch Agent initialization
        with patch.object(BugExorcistAgent, '_init_provider') as mock_init:
            agent = BugExorcistAgent(bug_id=bug_id)
            agent.primary_provider = primary_provider
            agent.secondary_provider = secondary_provider
            
            # 4. Execute analyze_error with javascript
            print("Executing analyze_error with language='javascript'...")
            result = await agent.analyze_error(
                error_message=error_message,
                code_snippet=js_code,
                language="javascript"
            )
            
            # 5. Verify results
            print("Verifying fallback and language preservation...")
            
            # Check that primary was called once
            assert primary_provider.ainvoke.call_count == 1
            print("  Primary called: PASS")
            
            # Check that secondary was called once
            assert secondary_provider.ainvoke.call_count == 1
            print("  Secondary called: PASS")
            
            # Verify language in secondary call's prompt
            args, kwargs = secondary_provider.ainvoke.call_args
            prompt_content = args[0][1].content
            assert "**Language:** javascript" in prompt_content
            print("  Language 'javascript' preserved in fallback prompt: PASS")
            
            # Check result
            assert result['ai_agent'] == "secondary-model"
            
    print("\nFALLBACK LANGUAGE PRESERVATION TEST PASSED!")

if __name__ == "__main__":
    asyncio.run(test_fallback_preserves_language())

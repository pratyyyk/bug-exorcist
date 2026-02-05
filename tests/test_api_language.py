import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root and backend to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'backend'))

from app.api.agent import BugAnalysisRequest, BugAnalysisResponse, VerifyFixRequest, QuickFixRequest
from app.api.agent import analyze_bug, verify_bug_fix, quick_fix_endpoint, fix_bug_with_retry, RetryFixRequest

async def test_rest_api_language_support():
    """
    Test that REST API endpoints correctly accept and forward the language parameter.
    """
    print("Running REST API language support tests...")
    
    # 1. Test /analyze endpoint
    print("Testing /analyze endpoint...")
    mock_db = MagicMock()
    mock_bug_report = MagicMock()
    mock_bug_report.id = 1
    
    # Mock BugExorcistAgent to avoid Docker initialization
    with patch('app.api.agent.BugExorcistAgent') as MockAgent:
        mock_agent_instance = MockAgent.return_value
        mock_agent_instance.analyze_and_fix_with_retry = AsyncMock()
        mock_agent_instance.analyze_and_fix_with_retry.return_value = {
            "success": True,
            "final_fix": {
                "root_cause": "Test cause",
                "fixed_code": "console.log('fixed')",
                "explanation": "Test explanation",
                "confidence": 0.9,
                "timestamp": "2023-01-01T00:00:00"
            },
            "total_attempts": 1,
            "all_attempts": []
        }
        
        with patch('app.crud.create_bug_report', return_value=mock_bug_report), \
             patch('app.crud.create_session'), \
             patch('app.crud.update_session_usage'), \
             patch('app.crud.update_bug_report_status'):
            
            request = BugAnalysisRequest(
                error_message="ReferenceError: x is not defined",
                code_snippet="console.log(x)",
                language="javascript",
                use_retry=True
            )
            
            response = await analyze_bug(request, db=mock_db)
            
            # Verify language was forwarded to agent
            args, kwargs = mock_agent_instance.analyze_and_fix_with_retry.call_args
            assert kwargs['language'] == "javascript"
            assert response.language == "javascript"
            print("  /analyze (retry) language check: PASS")

    # 2. Test /fix-with-retry endpoint
    print("Testing /fix-with-retry endpoint...")
    with patch('app.api.agent.BugExorcistAgent') as MockAgent:
        mock_agent_instance = MockAgent.return_value
        mock_agent_instance.analyze_and_fix_with_retry = AsyncMock()
        mock_agent_instance.analyze_and_fix_with_retry.return_value = {
            "success": True,
            "final_fix": {"code": "fixed"},
            "all_attempts": [],
            "total_attempts": 1,
            "message": "Fixed"
        }
        
        with patch('app.crud.create_bug_report', return_value=mock_bug_report), \
             patch('app.crud.update_bug_report_status'):
            
            request = RetryFixRequest(
                error_message="err",
                code_snippet="code",
                language="go",
                max_attempts=3
            )
            
            response = await fix_bug_with_retry(request, db=mock_db)
            
            # Verify language was forwarded
            args, kwargs = mock_agent_instance.analyze_and_fix_with_retry.call_args
            assert kwargs['language'] == "go"
            assert response.language == "go"
            print("  /fix-with-retry language check: PASS")

    # 3. Test /quick-fix endpoint
    print("Testing /quick-fix endpoint...")
    with patch('app.api.agent.quick_fix', new_callable=AsyncMock) as mock_quick_fix:
        mock_quick_fix.return_value = "fixed code"
        
        request = QuickFixRequest(
            error="err",
            code="code",
            language="rust"
        )
        
        response = await quick_fix_endpoint(request)
        
        # Verify language was forwarded to the convenience function
        args, kwargs = mock_quick_fix.call_args
        assert kwargs['language'] == "rust"
        print("  /quick-fix language check: PASS")

    # 4. Test /verify endpoint
    print("Testing /verify endpoint...")
    with patch('app.api.agent.BugExorcistAgent') as MockAgent:
        mock_agent_instance = MockAgent.return_value
        mock_agent_instance.verify_fix = AsyncMock()
        mock_agent_instance.verify_fix.return_value = {
            "verified": True,
            "output": "ok",
            "timestamp": "now"
        }
        
        with patch('app.crud.get_bug_report', return_value=mock_bug_report), \
             patch('app.crud.update_bug_report_status'):
            
            request = VerifyFixRequest(
                fixed_code="console.log('fixed')",
                language="javascript"
            )
            
            response = await verify_bug_fix(bug_id="BUG-1", request=request, db=mock_db)
            
            # Verify language was forwarded
            args, kwargs = mock_agent_instance.verify_fix.call_args
            assert kwargs['language'] == "javascript"
            print("  /verify language check: PASS")

    print("\nALL REST API LANGUAGE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_rest_api_language_support())

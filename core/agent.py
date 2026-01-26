"""
Add these methods to the BugExorcistAgent class in core/agent.py

These methods enable real-time streaming of the agent's thought process
"""

async def stream_thought_process(
    self,
    error_message: str,
    code_snippet: str,
    file_path: Optional[str] = None,
    additional_context: Optional[str] = None,
    use_retry: bool = True,
    max_attempts: int = 3
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream the agent's thought process in real-time as it analyzes and fixes bugs.
    
    This method yields thought events as they happen, providing visibility into:
    - Initialization steps
    - AI analysis progress
    - Code generation
    - Test execution
    - Retry logic
    - Final results
    
    Yields:
        Dict containing:
        - type: "thought" | "status" | "result" | "error"
        - timestamp: ISO format timestamp
        - message: Human-readable description
        - stage: Current processing stage
        - data: Additional structured data (optional)
    """
    from datetime import datetime
    
    def emit_thought(message: str, stage: str, data: Optional[Dict] = None):
        """Helper to create consistent thought events"""
        return {
            "type": "thought",
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "stage": stage,
            "data": data or {}
        }
    
    def emit_status(message: str, stage: str, data: Optional[Dict] = None):
        """Helper for status updates"""
        return {
            "type": "status",
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "stage": stage,
            "data": data or {}
        }
    
    try:
        # Stage 1: Initialization
        yield emit_status(
            f"🧟‍♂️ Initializing Bug Exorcist for {self.bug_id}",
            "initialization"
        )
        
        yield emit_thought(
            "Preparing sandbox environment...",
            "initialization"
        )
        
        yield emit_thought(
            f"Error type detected: {error_message.split(':')[0] if ':' in error_message else 'Unknown'}",
            "initialization",
            {"error_preview": error_message[:100]}
        )
        
        if file_path:
            yield emit_thought(
                f"Target file: {file_path}",
                "initialization",
                {"file_path": file_path}
            )
        
        # Stage 2: Analysis
        yield emit_status(
            "🔍 Analyzing error with AI...",
            "analysis"
        )
        
        if use_retry:
            yield emit_thought(
                f"Retry logic enabled (max {max_attempts} attempts)",
                "analysis",
                {"max_attempts": max_attempts, "retry_enabled": True}
            )
            
            # Use retry logic with streaming
            all_attempts = []
            
            for attempt_num in range(1, max_attempts + 1):
                yield emit_thought(
                    f"🤖 Attempt {attempt_num}/{max_attempts}: Requesting AI analysis...",
                    "analysis",
                    {"attempt": attempt_num, "total_attempts": max_attempts}
                )
                
                # Check if Gemini fallback is active
                using_gemini = attempt_num > 1 and self.gemini_agent
                ai_model = "gemini-1.5-pro" if using_gemini else "gpt-4o"
                
                yield emit_thought(
                    f"Using {ai_model} for analysis...",
                    "analysis",
                    {"model": ai_model, "attempt": attempt_num}
                )
                
                # Perform analysis
                try:
                    fix_result = await self.analyze_error(
                        error_message=error_message,
                        code_snippet=code_snippet,
                        file_path=file_path,
                        additional_context=additional_context,
                        previous_attempts=all_attempts,
                        use_gemini=using_gemini
                    )
                    
                    yield emit_thought(
                        f"✅ AI generated a fix (confidence: {fix_result.get('confidence', 0):.0%})",
                        "analysis",
                        {
                            "attempt": attempt_num,
                            "confidence": fix_result.get('confidence', 0),
                            "root_cause": fix_result.get('root_cause', '')[:200]
                        }
                    )
                    
                    # Stage 3: Code Generation
                    yield emit_status(
                        "💻 Fix generated, preparing for verification...",
                        "fixing"
                    )
                    
                    yield emit_thought(
                        "Root cause identified",
                        "fixing",
                        {"root_cause": fix_result.get('root_cause', '')}
                    )
                    
                    # Stage 4: Verification
                    yield emit_status(
                        "🧪 Verifying fix in sandbox...",
                        "verification"
                    )
                    
                    yield emit_thought(
                        "Executing code in isolated Docker container...",
                        "verification"
                    )
                    
                    verification = await self.verify_fix(
                        fixed_code=fix_result['fixed_code'],
                        original_error=error_message
                    )
                    
                    # Record attempt
                    attempt_record = {
                        "attempt_number": attempt_num,
                        "ai_agent": fix_result.get('ai_agent', 'unknown'),
                        "fix_result": fix_result,
                        "verification": verification,
                        "fixed_code": fix_result['fixed_code'],
                        "verification_result": "PASSED" if verification['verified'] else "FAILED",
                        "new_error": verification.get('new_error'),
                        "timestamp": datetime.now().isoformat()
                    }
                    all_attempts.append(attempt_record)
                    
                    if verification['verified']:
                        # Success!
                        yield emit_status(
                            f"✅ Fix verified successfully on attempt {attempt_num}!",
                            "complete"
                        )
                        
                        yield emit_thought(
                            f"Bug exorcised using {ai_model}! 🎉",
                            "complete",
                            {
                                "success": True,
                                "attempts": attempt_num,
                                "ai_model": ai_model
                            }
                        )
                        
                        # Stage 5: Final Result
                        yield {
                            "type": "result",
                            "timestamp": datetime.now().isoformat(),
                            "message": "Bug fix complete",
                            "stage": "complete",
                            "data": {
                                "success": True,
                                "bug_id": self.bug_id,
                                "root_cause": fix_result['root_cause'],
                                "fixed_code": fix_result['fixed_code'],
                                "explanation": fix_result['explanation'],
                                "confidence": fix_result['confidence'],
                                "attempts": attempt_num,
                                "ai_model": ai_model,
                                "all_attempts": all_attempts
                            }
                        }
                        return
                    
                    else:
                        # Verification failed
                        yield emit_thought(
                            f"❌ Verification failed: {verification.get('new_error', 'Unknown error')[:100]}",
                            "verification",
                            {
                                "attempt": attempt_num,
                                "error": verification.get('new_error', '')[:200]
                            }
                        )
                        
                        if attempt_num < max_attempts:
                            yield emit_thought(
                                f"Preparing retry {attempt_num + 1}/{max_attempts}...",
                                "verification"
                            )
                        else:
                            yield emit_thought(
                                f"Maximum attempts ({max_attempts}) reached",
                                "verification"
                            )
                
                except Exception as e:
                    yield emit_thought(
                        f"⚠️ Error during attempt {attempt_num}: {str(e)[:100]}",
                        "error",
                        {"attempt": attempt_num, "error": str(e)}
                    )
                    
                    if attempt_num >= max_attempts:
                        break
            
            # All attempts exhausted - check for fallback
            if self.fallback_handler.is_enabled():
                yield emit_status(
                    "Generating manual debugging guidance...",
                    "fallback"
                )
                
                fallback_response = self.fallback_handler.generate_fallback_response(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    bug_id=self.bug_id,
                    total_attempts=len(all_attempts),
                    all_attempts=all_attempts
                )
                
                yield {
                    "type": "result",
                    "timestamp": datetime.now().isoformat(),
                    "message": "AI fix attempts exhausted. Manual guidance provided.",
                    "stage": "fallback",
                    "data": {
                        "success": False,
                        "fallback_provided": True,
                        "fallback_response": fallback_response,
                        "all_attempts": all_attempts
                    }
                }
            else:
                yield {
                    "type": "result",
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Failed to fix bug after {len(all_attempts)} attempts",
                    "stage": "failed",
                    "data": {
                        "success": False,
                        "all_attempts": all_attempts
                    }
                }
        
        else:
            # Single attempt mode (no retry)
            yield emit_thought(
                "Single attempt mode (retry disabled)",
                "analysis"
            )
            
            yield emit_thought(
                "Requesting AI analysis...",
                "analysis"
            )
            
            fix_result = await self.analyze_error(
                error_message=error_message,
                code_snippet=code_snippet,
                file_path=file_path,
                additional_context=additional_context
            )
            
            yield emit_status(
                "AI analysis complete",
                "analysis"
            )
            
            yield emit_thought(
                "Verifying fix...",
                "verification"
            )
            
            verification = await self.verify_fix(fix_result['fixed_code'])
            
            if verification['verified']:
                yield emit_status(
                    "✅ Fix verified!",
                    "complete"
                )
            else:
                yield emit_status(
                    "❌ Verification failed",
                    "failed"
                )
            
            yield {
                "type": "result",
                "timestamp": datetime.now().isoformat(),
                "message": "Analysis complete",
                "stage": "complete" if verification['verified'] else "failed",
                "data": {
                    "success": verification['verified'],
                    "fix_result": fix_result,
                    "verification": verification
                }
            }
    
    except Exception as e:
        yield {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "message": f"Fatal error: {str(e)}",
            "stage": "error",
            "data": {"error": str(e)}
        }


# Add this import at the top of the file
from typing import AsyncGenerator
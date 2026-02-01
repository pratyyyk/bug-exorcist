"""
core/agent.py - Bug Exorcist Agent with Refactored Retry Logic

This module provides the main autonomous debugging agent with:
- Shared retry logic between REST and WebSocket streaming
- GPT-4o integration for bug analysis
- Gemini fallback support
- Docker sandbox verification
- Real-time thought streaming

REFACTORED: Extracted common retry logic into _execute_retry_logic private helper
to eliminate duplication between analyze_and_fix_with_retry and stream_thought_process.
"""

import os
from datetime import datetime
from typing import Dict, Optional, Any, List, AsyncGenerator, Callable, Awaitable
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class BugExorcistAgent:
    """
    Autonomous debugging agent that analyzes and fixes bugs using AI.
    
    Features:
    - GPT-4o powered analysis with Gemini fallback
    - Automatic retry logic with learning
    - Docker sandbox verification
    - Real-time thought streaming via WebSocket
    - Graceful fallback when AI fails
    """

    SYSTEM_PROMPT = """You are the Bug Exorcist, an elite AI debugging specialist.

Your mission is to analyze runtime errors and generate production-ready fixes with surgical precision.

**Analysis Process:**
1. Carefully examine error messages and stack traces
2. Identify the exact failure point and error type
3. Understand the code context thoroughly
4. Determine the root cause (not just symptoms)
5. Generate a minimal, targeted fix
6. Provide clear explanations

**Retry Context:**
When analyzing a bug with previous failed attempts, you will receive:
- The original error
- Previous fix attempts and why they failed
- New errors that occurred after each fix
- Verification results

Use this information to:
- Understand what approaches didn't work
- Avoid repeating the same mistakes
- Generate more robust solutions that handle edge cases
- Consider defensive programming patterns

**Fix Requirements:**
- Minimal, surgical changes only
- Preserve existing code style and patterns
- Add defensive programming where needed
- Include brief inline comments for critical fixes
- Ensure backwards compatibility
- Handle edge cases that previous attempts missed

**Output Format:**
Provide:
1. Root Cause Analysis (2-3 sentences, precise and technical)
2. Complete fixed code (ready to deploy)
3. Explanation of changes (what and why)
4. (On retry) Analysis of why previous attempts failed

Be systematic, thorough, and learn from failures."""

    def __init__(self, bug_id: str, openai_api_key: Optional[str] = None):
        """
        Initialize the Bug Exorcist Agent.
        
        Args:
            bug_id: Unique identifier for this bug
            openai_api_key: OpenAI API key (uses env var if not provided)
        """
        self.bug_id = bug_id
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize GPT-4o via LangChain
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=self.api_key,
            max_tokens=2000
        )
        
        # Initialize Gemini fallback if available
        self.gemini_agent = None
        try:
            from core.gemini_agent import GeminiFallbackAgent, is_gemini_available
            if is_gemini_available():
                self.gemini_agent = GeminiFallbackAgent()
        except ImportError:
            pass
        
        # Initialize fallback handler
        from core.fallback import get_fallback_handler
        self.fallback_handler = get_fallback_handler()
        
        # Initialize sandbox
        from app.sandbox import Sandbox
        self.sandbox = Sandbox()

    async def _execute_retry_logic(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        max_attempts: int = 3,
        on_attempt_start: Optional[Callable[[int, str, bool], Awaitable[None]]] = None,
        on_fix_generated: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
        on_verification_complete: Optional[Callable[[int, Dict[str, Any], bool], Awaitable[None]]] = None,
        on_attempt_failed: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        **PRIVATE SHARED HELPER** - Execute retry logic for bug fixing.
        
        This is the core retry logic shared by both:
        1. REST API endpoint (analyze_and_fix_with_retry)
        2. WebSocket streaming endpoint (stream_thought_process)
        
        The callbacks allow the streaming method to emit events while the REST
        method can simply ignore them or use them for logging.
        
        Args:
            error_message: The error/exception message
            code_snippet: The problematic code
            file_path: Optional file path
            additional_context: Optional additional context
            max_attempts: Maximum number of retry attempts
            on_attempt_start: Optional async callback(attempt_num, ai_model, using_gemini)
            on_fix_generated: Optional async callback(attempt_num, fix_result)
            on_verification_complete: Optional async callback(attempt_num, verification, verified)
            on_attempt_failed: Optional async callback(attempt_num, error_msg)
            
        Returns:
            Dictionary containing:
            - success: bool - Whether a working fix was found
            - final_fix: Dict - The successful fix (if success=True)
            - all_attempts: List[Dict] - All attempt records
            - total_attempts: int - Number of attempts made
            - message: str - Result message
            - last_error: str - Last error encountered (if success=False)
            - ai_model: str - The AI model that succeeded (if success=True)
            - fallback_response: Dict - Fallback guidance (if enabled and failed)
        """
        all_attempts = []
        
        for attempt_num in range(1, max_attempts + 1):
            # Determine which AI to use
            use_gemini = attempt_num > 1 and self.gemini_agent is not None
            ai_model = "gemini-1.5-pro" if use_gemini else "gpt-4o"
            
            # Notify: attempt starting
            if on_attempt_start:
                await on_attempt_start(attempt_num, ai_model, use_gemini)
            
            try:
                # Perform analysis
                fix_result = await self.analyze_error(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    previous_attempts=all_attempts,
                    use_gemini=use_gemini
                )
                
                # Notify: fix generated
                if on_fix_generated:
                    await on_fix_generated(attempt_num, fix_result)
                
                # Verify the fix
                verification = await self.verify_fix(
                    fixed_code=fix_result['fixed_code'],
                    original_error=error_message
                )
                
                # Record attempt
                attempt_record = {
                    "attempt_number": attempt_num,
                    "ai_agent": fix_result.get('ai_agent', ai_model),
                    "fix_result": fix_result,
                    "verification": verification,
                    "fixed_code": fix_result['fixed_code'],
                    "verification_result": "PASSED" if verification['verified'] else "FAILED",
                    "new_error": verification.get('new_error'),
                    "timestamp": datetime.now().isoformat()
                }
                all_attempts.append(attempt_record)
                
                # Notify: verification complete
                if on_verification_complete:
                    await on_verification_complete(attempt_num, verification, verification['verified'])
                
                # Check if fix is verified
                if verification['verified']:
                    return {
                        "success": True,
                        "final_fix": fix_result,
                        "all_attempts": all_attempts,
                        "total_attempts": attempt_num,
                        "message": f"Bug fixed successfully on attempt {attempt_num}",
                        "ai_model": ai_model
                    }
                
                # Notify: attempt failed
                if on_attempt_failed and attempt_num < max_attempts:
                    await on_attempt_failed(attempt_num, verification.get('new_error', 'Verification failed'))
                
            except Exception as e:
                # Record failed attempt
                attempt_record = {
                    "attempt_number": attempt_num,
                    "ai_agent": ai_model,
                    "verification_result": "ERROR",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                all_attempts.append(attempt_record)
                
                # Notify: attempt failed
                if on_attempt_failed and attempt_num < max_attempts:
                    await on_attempt_failed(attempt_num, str(e))
                
                if attempt_num >= max_attempts:
                    break
        
        # All attempts exhausted - check for fallback
        if self.fallback_handler.is_enabled():
            fallback_response = self.fallback_handler.generate_fallback_response(
                error_message=error_message,
                code_snippet=code_snippet,
                bug_id=self.bug_id,
                total_attempts=len(all_attempts),
                all_attempts=all_attempts
            )
            
            return {
                "success": False,
                "final_fix": None,
                "all_attempts": all_attempts,
                "total_attempts": len(all_attempts),
                "message": f"Failed to fix bug after {len(all_attempts)} attempts. Fallback guidance provided.",
                "last_error": all_attempts[-1].get('new_error') or all_attempts[-1].get('error') if all_attempts else None,
                "fallback_response": fallback_response
            }
        else:
            return {
                "success": False,
                "final_fix": None,
                "all_attempts": all_attempts,
                "total_attempts": len(all_attempts),
                "message": f"Failed to fix bug after {len(all_attempts)} attempts",
                "last_error": all_attempts[-1].get('new_error') or all_attempts[-1].get('error') if all_attempts else None
            }

    async def analyze_and_fix_with_retry(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze and fix a bug with automatic retry logic (REST API interface).
        
        This method uses the shared retry logic helper and is called by REST endpoints.
        No callbacks are provided, so it runs silently and returns the final result.
        
        Args:
            error_message: The error message with stack trace
            code_snippet: The code that caused the error
            file_path: Optional path to the file containing the bug
            additional_context: Optional additional context about the bug
            max_attempts: Maximum retry attempts (default: 3, max: 5)
            
        Returns:
            Dictionary containing detailed results of all attempts:
            - success: bool
            - final_fix: Dict (if successful)
            - all_attempts: List[Dict]
            - total_attempts: int
            - message: str
            - last_error: str (if failed)
        """
        return await self._execute_retry_logic(
            error_message=error_message,
            code_snippet=code_snippet,
            file_path=file_path,
            additional_context=additional_context,
            max_attempts=min(max_attempts, 5)
            # No callbacks - REST endpoint doesn't need streaming
        )

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
        Stream the agent's thought process in real-time (WebSocket interface).
        
        This method uses the shared retry logic helper and emits thought events
        as the analysis progresses via callbacks.
        
        Yields:
            Dict containing:
            - type: "thought" | "status" | "result" | "error"
            - timestamp: ISO format timestamp
            - message: Human-readable description
            - stage: Current processing stage
            - data: Additional structured data (optional)
        """
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
                
                # Define callbacks for the shared retry logic
                async def on_attempt_start(attempt_num: int, ai_model: str, using_gemini: bool):
                    """Called before each attempt"""
                    yield emit_thought(
                        f"🤖 Attempt {attempt_num}/{max_attempts}: Requesting AI analysis...",
                        "analysis",
                        {"attempt": attempt_num, "total_attempts": max_attempts, "using_gemini": using_gemini}
                    )
                    
                    yield emit_thought(
                        f"Using {ai_model} for analysis...",
                        "analysis",
                        {"model": ai_model, "attempt": attempt_num}
                    )
                
                async def on_fix_generated(attempt_num: int, fix_result: Dict[str, Any]):
                    """Called after AI generates a fix"""
                    yield emit_thought(
                        f"✅ AI generated a fix (confidence: {fix_result.get('confidence', 0):.0%})",
                        "analysis",
                        {
                            "attempt": attempt_num,
                            "confidence": fix_result.get('confidence', 0),
                            "root_cause": fix_result.get('root_cause', '')[:200],
                            "usage": fix_result.get('usage', {})
                        }
                    )
                    
                    yield emit_status(
                        "💻 Fix generated, preparing for verification...",
                        "fixing"
                    )
                    
                    yield emit_thought(
                        "Root cause identified",
                        "fixing",
                        {"root_cause": fix_result.get('root_cause', '')}
                    )
                
                async def on_verification_complete(attempt_num: int, verification: Dict[str, Any], verified: bool):
                    """Called after verification completes"""
                    yield emit_status(
                        "🧪 Verifying fix in sandbox...",
                        "verification"
                    )
                    
                    yield emit_thought(
                        "Executing code in isolated Docker container...",
                        "verification"
                    )
                    
                    if verified:
                        yield emit_status(
                            f"✅ Fix verified successfully on attempt {attempt_num}!",
                            "complete"
                        )
                        
                        yield emit_thought(
                            f"Bug exorcised! 🎉",
                            "complete",
                            {
                                "success": True,
                                "attempts": attempt_num
                            }
                        )
                    else:
                        yield emit_thought(
                            f"❌ Verification failed: {verification.get('new_error', 'Unknown error')[:100]}",
                            "verification",
                            {
                                "attempt": attempt_num,
                                "error": verification.get('new_error', '')[:200]
                            }
                        )
                
                async def on_attempt_failed(attempt_num: int, error_msg: str):
                    """Called when an attempt fails"""
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
                
                # Execute shared retry logic with streaming callbacks
                result = await self._execute_retry_logic(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    max_attempts=max_attempts,
                    on_attempt_start=on_attempt_start,
                    on_fix_generated=on_fix_generated,
                    on_verification_complete=on_verification_complete,
                    on_attempt_failed=on_attempt_failed
                )
                
                # Emit final result
                if result['success']:
                    yield {
                        "type": "result",
                        "timestamp": datetime.now().isoformat(),
                        "message": "Bug fix complete",
                        "stage": "complete",
                        "data": {
                            "success": True,
                            "bug_id": self.bug_id,
                            "root_cause": result['final_fix']['root_cause'],
                            "fixed_code": result['final_fix']['fixed_code'],
                            "explanation": result['final_fix']['explanation'],
                            "confidence": result['final_fix']['confidence'],
                            "attempts": result['total_attempts'],
                            "ai_model": result.get('ai_model', 'unknown'),
                            "all_attempts": result['all_attempts']
                        }
                    }
                else:
                    if 'fallback_response' in result:
                        yield emit_status(
                            "Generating manual debugging guidance...",
                            "fallback"
                        )
                        
                        yield {
                            "type": "result",
                            "timestamp": datetime.now().isoformat(),
                            "message": "AI fix attempts exhausted. Manual guidance provided.",
                            "stage": "fallback",
                            "data": {
                                "success": False,
                                "fallback_provided": True,
                                "fallback_response": result['fallback_response'],
                                "all_attempts": result['all_attempts']
                            }
                        }
                    else:
                        yield {
                            "type": "result",
                            "timestamp": datetime.now().isoformat(),
                            "message": f"Failed to fix bug after {result['total_attempts']} attempts",
                            "stage": "failed",
                            "data": {
                                "success": False,
                                "all_attempts": result['all_attempts']
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

    async def analyze_error(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
        use_gemini: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze an error and generate a fix using AI.
        
        Args:
            error_message: The error/exception message
            code_snippet: The problematic code
            file_path: Optional file path for context
            additional_context: Optional additional context
            previous_attempts: Optional list of previous failed attempts
            use_gemini: Whether to use Gemini instead of GPT-4o
            
        Returns:
            Dictionary containing analysis results
        """
        attempt_number = len(previous_attempts) + 1 if previous_attempts else 1
        
        # Use Gemini if requested and available
        if use_gemini and self.gemini_agent:
            return await self.gemini_agent.analyze_error(
                error_message=error_message,
                code_snippet=code_snippet,
                file_path=file_path,
                additional_context=additional_context,
                previous_attempts=previous_attempts
            )
        
        # Construct the analysis prompt
        user_prompt = f"""Analyze and fix this bug:

**Error Message:**
```
{error_message}
```

**Original Code:**
```python
{code_snippet}
```
"""
        
        if file_path:
            user_prompt += f"\n**File Path:** `{file_path}`\n"
        
        if additional_context:
            user_prompt += f"\n**Additional Context:**\n{additional_context}\n"
        
        # Add retry context if this is not the first attempt
        if previous_attempts:
            user_prompt += f"\n**RETRY ATTEMPT #{attempt_number}**\n"
            user_prompt += f"**Previous attempts have failed. Learn from these mistakes:**\n\n"
            
            for i, attempt in enumerate(previous_attempts, 1):
                user_prompt += f"--- Attempt {i} ---\n"
                user_prompt += f"**Fix Attempted:**\n```python\n{attempt['fixed_code']}\n```\n"
                user_prompt += f"**Result:** {attempt['verification_result']}\n"
                if attempt.get('new_error'):
                    user_prompt += f"**New Error:** {attempt['new_error']}\n"
                user_prompt += "\n"
            
            user_prompt += f"""
**CRITICAL:** 
- Analyze why the previous fix(es) failed
- Do NOT repeat the same approach
- Generate a MORE ROBUST solution
- Consider edge cases that were missed
"""
        
        user_prompt += """
Please provide:
1. Root Cause Analysis
2. The complete fixed code
3. Explanation of your changes
"""
        
        if previous_attempts:
            user_prompt += "4. What was wrong with the previous attempt(s) and how this fix is different\n"
        
        try:
            # Call GPT-4o via LangChain
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.agenerate([messages])
            ai_response = response.generations[0][0].text
            
            # Extract usage metrics
            usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            # Calculate estimated cost for GPT-4o
            # Input: $5.00 / 1M tokens, Output: $15.00 / 1M tokens
            estimated_cost = (prompt_tokens * 0.000005) + (completion_tokens * 0.000015)
            
            # Parse the AI response
            result = self._parse_ai_response(ai_response, code_snippet)
            
            return {
                "ai_agent": "gpt-4o",
                "root_cause": result["root_cause"],
                "fixed_code": result["fixed_code"],
                "explanation": result["explanation"],
                "confidence": result["confidence"],
                "original_error": error_message,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": attempt_number,
                "retry_analysis": result.get("retry_analysis", ""),
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "estimated_cost": estimated_cost,
                    "model": "gpt-4o"
                }
            }
            
        except Exception as e:
            # If GPT-4o fails, try Gemini fallback
            if self.gemini_agent and not use_gemini:
                return await self.gemini_agent.analyze_error(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    previous_attempts=previous_attempts,
                    gpt_failure_context=f"GPT-4o failed: {str(e)}"
                )
            
            raise Exception(f"AI analysis failed: {str(e)}")

    def _parse_ai_response(self, ai_response: str, original_code: str) -> Dict[str, Any]:
        """
        Parse AI's response to extract structured components.
        """
        lines = ai_response.split('\n')
        
        root_cause = ""
        fixed_code = ""
        explanation = ""
        retry_analysis = ""
        in_code_block = False
        
        for i, line in enumerate(lines):
            # Detect code blocks
            if '```python' in line.lower() or '```' in line:
                in_code_block = not in_code_block
                continue
            
            if in_code_block:
                fixed_code += line + '\n'
            elif 'root cause' in line.lower() and i + 1 < len(lines):
                # Capture next few lines as root cause
                root_cause = '\n'.join(lines[i+1:i+4]).strip()
            elif 'explanation' in line.lower() or 'changes' in line.lower():
                explanation = '\n'.join(lines[i+1:i+5]).strip()
            elif 'wrong with' in line.lower() or 'previous attempt' in line.lower():
                retry_analysis = '\n'.join(lines[i:i+4]).strip()
        
        # Fallback: if no code found, use original
        if not fixed_code.strip():
            fixed_code = original_code
        
        # Estimate confidence based on response quality
        confidence = 0.85 if fixed_code.strip() and root_cause else 0.6
        
        return {
            "root_cause": root_cause or "Analysis completed",
            "fixed_code": fixed_code.strip(),
            "explanation": explanation or "Code has been fixed",
            "confidence": confidence,
            "retry_analysis": retry_analysis
        }

    async def verify_fix(
        self,
        fixed_code: str,
        original_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a fix by running it in the sandbox.
        
        Args:
            fixed_code: The fixed code to verify
            original_error: Optional original error for comparison
            
        Returns:
            Dictionary containing verification results
        """
        try:
            result = self.sandbox.run_code(fixed_code)
            
            # Check if execution was successful
            verified = not result.startswith("Error")
            
            return {
                "verified": verified,
                "output": result,
                "new_error": result if not verified else None,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "verified": False,
                "output": "",
                "new_error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def execute_full_workflow(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the full bug fixing workflow with status updates.
        
        This is a convenience method for simple use cases.
        For more control, use stream_thought_process directly.
        
        Yields:
            Status update dictionaries
        """
        async for event in self.stream_thought_process(
            error_message=error_message,
            code_snippet=code_snippet,
            file_path=file_path,
            additional_context=additional_context,
            use_retry=True,
            max_attempts=3
        ):
            yield event

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        """
        Stream log messages for WebSocket consumption.
        
        This is a placeholder for backward compatibility.
        Use stream_thought_process for detailed event streaming.
        
        Yields:
            Log message strings
        """
        yield f"[{datetime.now().isoformat()}] Bug Exorcist Agent initialized for {self.bug_id}"
        yield f"[{datetime.now().isoformat()}] Use stream_thought_process for detailed event streaming"


# Convenience functions for quick usage
async def quick_fix(error: str, code: str, api_key: Optional[str] = None) -> str:
    """
    Quick fix - returns only the fixed code without full analysis.
    
    Args:
        error: Error message
        code: Problematic code
        api_key: Optional OpenAI API key
        
    Returns:
        Fixed code as string
    """
    agent = BugExorcistAgent(bug_id="quick-fix", openai_api_key=api_key)
    result = await agent.analyze_error(error, code)
    return result['fixed_code']


async def fix_with_retry(
    error: str,
    code: str,
    max_attempts: int = 3,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fix with automatic retry logic.
    
    Args:
        error: Error message
        code: Problematic code
        max_attempts: Maximum retry attempts
        api_key: Optional OpenAI API key
        
    Returns:
        Detailed retry results
    """
    agent = BugExorcistAgent(bug_id="retry-fix", openai_api_key=api_key)
    return await agent.analyze_and_fix_with_retry(
        error_message=error,
        code_snippet=code,
        max_attempts=max_attempts
    )
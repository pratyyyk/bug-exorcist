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
import re
import asyncio
from datetime import datetime
from typing import Dict, Optional, Any, List, AsyncGenerator, Callable, Awaitable
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.gemini_agent import GeminiFallbackAgent, is_gemini_available
from core.ollama_provider import get_ollama_llm, is_ollama_available


class MockLLM:
    def __init__(self, model_name="mock-ai"):
        self.model_name = model_name

    async def ainvoke(self, messages):
        # Very basic mock response logic
        content = "Root Cause Analysis: Division by zero.\nComplete fixed code:\ndef divide(a, b):\n    if b == 0:\n        return 0\n    return a / b\n\ndivide(10, 0)\nExplanation: Added a check for b == 0."
        from langchain_core.messages import AIMessage
        return AIMessage(content=content)

class BugExorcistAgent:
    """
    Autonomous debugging agent that analyzes and fixes bugs using AI.
    
    Features:
    - Multi-provider support (GPT-4o, Gemini, Ollama)
    - Configurable primary and secondary agents via .env
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

    def __init__(self, bug_id: str, openai_api_key: Optional[str] = None, project_path: str = ".", rag: Optional[Any] = None):
        """
        Initialize the Bug Exorcist Agent.
        
        Args:
            bug_id: Unique identifier for this bug
            openai_api_key: OpenAI API key (uses env var if not provided)
            project_path: Path to the project root
            rag: Injected RAG engine instance
        """
        self.bug_id = bug_id
        self.project_path = project_path
        
        # Configuration for agents
        self.primary_agent_type = os.getenv("PRIMARY_AGENT", "gpt-4o").lower()
        self.secondary_agent_type = os.getenv("SECONDARY_AGENT", "gemini-1.5-pro").lower()
        
        # Initialize providers
        self.primary_provider = self._init_provider(self.primary_agent_type, openai_api_key)
        self.secondary_provider = self._init_provider(self.secondary_agent_type)
        
        # Initialize fallback handler
        from core.fallback import get_fallback_handler
        self.fallback_handler = get_fallback_handler()
        
        # Initialize sandbox
        from app.sandbox import Sandbox
        self.sandbox = Sandbox(project_path=project_path)
        
        # Initialize log queue for async log streaming
        self._temp_log_queue = asyncio.Queue()

        # Use injected RAG or initialize if enabled
        if rag:
            self.rag = rag
        elif os.getenv("ENABLE_RAG", "true").lower() == "true":
            from core.rag_engine import CodebaseRAG
            self.rag = CodebaseRAG(project_path=project_path)
        else:
            self.rag = None

    def _init_provider(self, agent_type: str, api_key: Optional[str] = None) -> Any:
        """Initialize a specific AI provider based on type."""
        # Check if MockLLM is explicitly enabled via environment flag
        allow_mock = os.getenv("ALLOW_MOCK_LLM", "false").lower() == "true"

        if agent_type == "gpt-4o":
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                if allow_mock:
                    return MockLLM("mock-gpt-4o")
                raise ValueError("OPENAI_API_KEY is not configured and ALLOW_MOCK_LLM is false")
            return ChatOpenAI(
                model="gpt-4o",
                temperature=0.2,
                api_key=key,
                max_tokens=2000
            )
        elif agent_type == "gemini-1.5-pro":
            if is_gemini_available():
                from core.gemini_agent import GeminiFallbackAgent
                gemini = GeminiFallbackAgent()
                return gemini.llm
            if allow_mock:
                return MockLLM("mock-gemini")
            raise ValueError("Gemini provider is not available (check GOOGLE_API_KEY) and ALLOW_MOCK_LLM is false")
        elif agent_type == "ollama":
            if is_ollama_available():
                return get_ollama_llm()
            if allow_mock:
                return MockLLM("mock-ollama")
            raise ValueError("Ollama provider is not available and ALLOW_MOCK_LLM is false")
        
        if allow_mock:
            return MockLLM("mock-default")
        raise ValueError(f"Unknown agent type '{agent_type}' and ALLOW_MOCK_LLM is false")

    async def _execute_retry_logic(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        max_attempts: int = 3,
        language: str = "python",
        on_attempt_start: Optional[Callable[[int, str, bool], Awaitable[None]]] = None,
        on_fix_generated: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
        on_verification_complete: Optional[Callable[[int, Dict[str, Any], bool], Awaitable[None]]] = None,
        on_attempt_failed: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        **PRIVATE SHARED HELPER** - Execute retry logic for bug fixing.
        Returns an AsyncGenerator that yields events (if any) and finally yields the result dictionary.
        """
        all_attempts = []
        final_result = None
        
        # NEW: Ensure sandbox is provisioned before first attempt in non-streaming context
        if not on_attempt_start:
            # Running in silent/REST mode, build image without callback if needed
            # We can't easily await here if the caller didn't, but _execute_retry_logic is async
            await self.sandbox.build_image()

        for attempt_num in range(1, max_attempts + 1):
            # Determine which AI to use
            # Attempt 1: Primary
            # Attempt 2+: Secondary (if available), otherwise Primary
            use_secondary = attempt_num > 1 and self.secondary_provider is not None
            current_provider = self.secondary_provider if use_secondary else self.primary_provider
            
            # Fallback if primary is not configured
            if current_provider is None:
                current_provider = self.secondary_provider
            
            if current_provider is None:
                raise ValueError("No AI providers are configured. Check your .env file.")

            # Get model name for reporting
            if hasattr(current_provider, "model_name"):
                ai_model = current_provider.model_name
            elif hasattr(current_provider, "model"):
                ai_model = current_provider.model
            else:
                ai_model = str(current_provider)

            # Notify: attempt starting
            if on_attempt_start:
                event = await on_attempt_start(attempt_num, ai_model, use_secondary)
                if event: yield event
            
            try:
                # Perform analysis
                fix_result = await self.analyze_error(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    previous_attempts=all_attempts,
                    use_secondary=use_secondary,
                    language=language
                )
                
                # Notify: fix generated
                if on_fix_generated:
                    event = await on_fix_generated(attempt_num, fix_result)
                    if event: yield event
                
                # Verify the fix
                verification = await self.verify_fix(
                    fixed_code=fix_result['fixed_code'],
                    original_error=error_message,
                    language=language
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
                    event = await on_verification_complete(attempt_num, verification, verification['verified'])
                    if event: yield event
                
                # Check if fix is verified
                if verification['verified']:
                    final_result = {
                        "success": True,
                        "final_fix": fix_result,
                        "all_attempts": all_attempts,
                        "total_attempts": attempt_num,
                        "message": f"Bug fixed successfully on attempt {attempt_num}",
                        "ai_model": ai_model
                    }
                    break
                
                # Notify: attempt failed
                if on_attempt_failed and attempt_num < max_attempts:
                    event = await on_attempt_failed(attempt_num, verification.get('new_error', 'Verification failed'))
                    if event: yield event
                
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
                    event = await on_attempt_failed(attempt_num, str(e))
                    if event: yield event
                
                if attempt_num >= max_attempts:
                    break
        
        # All attempts exhausted - check for fallback
        if not final_result:
            if self.fallback_handler.is_enabled():
                fallback_response = self.fallback_handler.generate_fallback_response(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    bug_id=self.bug_id,
                    total_attempts=len(all_attempts),
                    all_attempts=all_attempts
                )
                
                final_result = {
                    "success": False,
                    "final_fix": None,
                    "all_attempts": all_attempts,
                    "total_attempts": len(all_attempts),
                    "message": f"Failed to fix bug after {len(all_attempts)} attempts. Fallback guidance provided.",
                    "last_error": all_attempts[-1].get('new_error') or all_attempts[-1].get('error') if all_attempts else None,
                    "fallback_response": fallback_response
                }
            else:
                final_result = {
                    "success": False,
                    "final_fix": None,
                    "all_attempts": all_attempts,
                    "total_attempts": len(all_attempts),
                    "message": f"Failed to fix bug after {len(all_attempts)} attempts",
                    "last_error": all_attempts[-1].get('new_error') or all_attempts[-1].get('error') if all_attempts else None
                }
        
        yield final_result

    async def analyze_and_fix_with_retry(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        max_attempts: int = 3,
        language: str = "python",
        session_id: Optional[str] = None
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
            language: The programming language of the code (default: "python")
            session_id: Optional session ID for tracking
            
        Returns:
            Dictionary containing detailed results of all attempts:
            - success: bool
            - final_fix: Dict (if successful)
            - all_attempts: List[Dict]
            - total_attempts: int
            - message: str
            - last_error: str (if failed)
        """
        result = None
        async for event in self._execute_retry_logic(
            error_message=error_message,
            code_snippet=code_snippet,
            file_path=file_path,
            additional_context=additional_context,
            max_attempts=min(max_attempts, 5),
            language=language
            # No callbacks - REST endpoint doesn't need streaming
        ):
            result = event
        return result

    async def stream_thought_process(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        use_retry: bool = True,
        max_attempts: int = 3,
        language: str = "python",
        session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream the agent's thought process in real-time (WebSocket interface).
        
        This method uses the shared retry logic helper and emits thought events
        as the analysis progresses via callbacks.
        
        Args:
            error_message: The error message with stack trace
            code_snippet: The code that caused the error
            file_path: Optional path to the file containing the bug
            additional_context: Optional additional context about the bug
            use_retry: Whether to use retry logic
            max_attempts: Maximum retry attempts
            language: The programming language
            session_id: Optional session ID for tracking
            
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

            # NEW: Dynamic Sandbox Provisioning
            yield emit_status("🏗️ Building dynamic sandbox environment...", "provisioning")
            
            # Start the build in a task
            async def wrapped_log_callback(msg):
                self._temp_log_queue.put_nowait(msg)

            build_task = asyncio.create_task(self.sandbox.build_image(
                log_callback=wrapped_log_callback
            ))
            
            # While the build is running, flush logs
            while not build_task.done():
                while not self._temp_log_queue.empty():
                    log_data = self._temp_log_queue.get_nowait()
                    if isinstance(log_data, dict):
                        yield emit_thought(
                            log_data.get("message", ""), 
                            "provisioning", 
                            {"image": log_data.get("image")}
                        )
                    else:
                        yield emit_thought(log_data, "provisioning")
                await asyncio.sleep(0.1) # Small delay to prevent busy waiting
                
            # Final flush
            await build_task # Ensure it's finished and raise any errors
            while not self._temp_log_queue.empty():
                log_data = self._temp_log_queue.get_nowait()
                if isinstance(log_data, dict):
                    yield emit_thought(
                        log_data.get("message", ""), 
                        "provisioning", 
                        {"image": log_data.get("image")}
                    )
                else:
                    yield emit_thought(log_data, "provisioning")
            
            # NEW: Run environment diagnostics after build
            yield emit_status("🔍 Running environment diagnostics...", "provisioning")
            diagnostics = await self.sandbox.get_diagnostics()
            yield emit_thought(
                f"Environment Ready. Python: {diagnostics['env'].get('PYTHON_VER', 'Unknown')}, "
                f"Disk Free: {diagnostics['env'].get('DISK_FREE', 'Unknown')}",
                "provisioning",
                {"diagnostics": diagnostics}
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
                async def on_attempt_start(attempt_num: int, ai_model: str, using_secondary: bool):
                    """Called before each attempt"""
                    return emit_thought(
                        f"🤖 Attempt {attempt_num}/{max_attempts}: Requesting AI analysis...",
                        "analysis",
                        {"attempt": attempt_num, "total_attempts": max_attempts, "using_secondary": using_secondary}
                    )
                
                async def on_fix_generated(attempt_num: int, fix_result: Dict[str, Any]):
                    """Called after AI generates a fix"""
                    return emit_thought(
                        f"✅ AI generated a fix (confidence: {fix_result.get('confidence', 0):.0%})",
                        "analysis",
                        {
                            "attempt": attempt_num,
                            "confidence": fix_result.get('confidence', 0),
                            "root_cause": fix_result.get('root_cause', '')[:200],
                            "usage": fix_result.get('usage', {}),
                            "referenced_files": fix_result.get('referenced_files', [])
                        }
                    )
                
                async def on_verification_complete(attempt_num: int, verification: Dict[str, Any], verified: bool):
                    """Called after verification completes"""
                    error_msg = verification.get('new_error', 'Unknown error')
                    # Sanitize error message to avoid leaking internal details/tracebacks
                    display_error = error_msg.split('\n')[0] if error_msg else "Unknown error"
                    if len(display_error) > 100:
                        display_error = display_error[:97] + "..."
                        
                    return emit_status(
                        f"✅ Fix verified successfully on attempt {attempt_num}!" if verified else f"❌ Verification failed: {display_error}",
                        "complete" if verified else "verification",
                        {"verified": verified, "attempt": attempt_num}
                    )
                
                async def on_attempt_failed(attempt_num: int, error_msg: str):
                    """Called when an attempt fails"""
                    return emit_thought(
                        f"Preparing retry {attempt_num + 1}/{max_attempts}..." if attempt_num < max_attempts else f"Maximum attempts ({max_attempts}) reached",
                        "verification"
                    )
                
                # Execute shared retry logic with streaming callbacks
                async for event in self._execute_retry_logic(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    max_attempts=max_attempts,
                    language=language,
                    on_attempt_start=on_attempt_start,
                    on_fix_generated=on_fix_generated,
                    on_verification_complete=on_verification_complete,
                    on_attempt_failed=on_attempt_failed
                ):
                    if isinstance(event, dict) and "success" in event:
                        result = event
                    else:
                        yield event
                
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
                            "all_attempts": result['all_attempts'],
                            "referenced_files": result['final_fix'].get('referenced_files', [])
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
                    additional_context=additional_context,
                    language=language,
                    session_id=session_id
                )
                
                yield emit_status(
                    "AI analysis complete",
                    "analysis",
                    {"referenced_files": fix_result.get('referenced_files', [])}
                )
                
                yield emit_thought(
                    "Verifying fix...",
                    "verification"
                )
                
                verification = await self.verify_fix(
                    fixed_code=fix_result['fixed_code'],
                    language=language
                )
                
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
                        "verification": verification,
                        "referenced_files": fix_result.get('referenced_files', [])
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
        use_secondary: bool = False,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Analyze an error and generate a fix using AI.
        """
        # Determine which provider to use
        provider = self.secondary_provider if use_secondary else self.primary_provider
        
        # Fallback if primary is not configured
        if provider is None:
            provider = self.secondary_provider
            
        if provider is None:
            raise ValueError("No AI providers are configured")

        # Centralized analysis logic for MockLLM
        if isinstance(provider, MockLLM):
            # Return a controlled mock response that will pass verification
            return {
                "ai_agent": provider.model_name,
                "provider_mode": "mock",
                "root_cause": "Division by zero.",
                "fixed_code": "def divide(a, b):\n    if b == 0: return 0\n    return a / b",
                "explanation": "Added check for zero.",
                "confidence": 0.95,
                "original_error": error_message,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": len(previous_attempts or []) + 1,
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "estimated_cost": 0.0, "model": provider.model_name},
                "referenced_files": []
            }

        # Sanitize language for prompt safety
        safe_language = re.sub(r'[^a-zA-Z0-9\-]', '', language).strip() or "python"
        
        attempt_number = len(previous_attempts) + 1 if previous_attempts else 1
        
        # All analysis logic is now centralized here
        # Get RAG context for the bug if RAG is enabled
        rag_context = "RAG is disabled."
        referenced_files = []
        if self.rag:
            rag_query = f"Fix {error_message} in {file_path if file_path else 'code'}: {code_snippet[:200]}"
            rag_data = self.rag.get_context_summary(rag_query)
            rag_context = rag_data["summary"]
            referenced_files = rag_data["referenced_files"]

        # Construct the analysis prompt
        user_prompt = f"""Analyze and fix this bug:

**Language:** {safe_language}

**Error Message:**
```
{error_message}
```

**Original Code:**
```{safe_language}
{code_snippet}
```

**Project Context (RAG):**
{rag_context}
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
                user_prompt += f"**Fix Attempted:**\n```{language}\n{attempt['fixed_code']}\n```\n"
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
            # Call LLM via LangChain
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            # Using ainvoke for consistency
            response = await provider.ainvoke(messages)
            ai_response = response.content
            
            # Extract usage metrics if available
            usage = {}
            if hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
            
            prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
            completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
            
            # Calculate estimated cost for GPT-4o if applicable
            estimated_cost = 0
            if self.primary_agent_type == "gpt-4o" and not use_secondary:
                estimated_cost = (prompt_tokens * 0.000005) + (completion_tokens * 0.000015)
            
            # Parse the AI response
            result = self._parse_ai_response(ai_response, code_snippet)
            
            # Get model name for reporting
            model_name = "unknown"
            if hasattr(provider, "model_name"):
                model_name = provider.model_name
            elif hasattr(provider, "model"):
                model_name = provider.model
            elif hasattr(provider, "model_id"):
                model_name = provider.model_id
            
            return {
                "ai_agent": model_name,
                "provider_mode": "real",
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
                    "model": model_name
                },
                "referenced_files": referenced_files
            }
            
        except Exception as e:
            # Log the full internal error details for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"AI analysis internal error: {str(e)}", exc_info=True)
            
            # If primary fails and we have a secondary, try secondary
            if not use_secondary and self.secondary_provider:
                return await self.analyze_error(
                    error_message=error_message,
                    code_snippet=code_snippet,
                    file_path=file_path,
                    additional_context=additional_context,
                    previous_attempts=previous_attempts,
                    use_secondary=True,
                    language=language
                )
            
            # Provide a user-friendly error message without leaking internal details
            raise Exception("AI analysis failed due to an internal provider error. Please check server logs for details.")

    def _parse_ai_response(self, ai_response: str, original_code: str) -> Dict[str, Any]:
        """
        Parse AI's response to extract structured components using a state machine.
        Handles inline content in headers and code fences.
        """
        lines = ai_response.split('\n')
        
        root_cause_lines = []
        fixed_code_lines = []
        explanation_lines = []
        retry_analysis_lines = []
        
        # States: None, 'root_cause', 'code', 'explanation', 'retry_analysis'
        current_state = None
        
        for line in lines:
            stripped_line = line.strip()
            lower_line = stripped_line.lower()
            
            # State transitions
            if '```' in lower_line:
                if current_state != 'code':
                    current_state = 'code'
                    # Check for inline code after the fence: ```python print("hello")
                    fence_content = stripped_line.split('```', 1)[1]
                    # Remove language identifier if present
                    if fence_content.startswith('python'):
                        fence_content = fence_content[6:].strip()
                    else:
                        # Common case: ```python\ncode...
                        # If there's content after the language ID on the same line, keep it
                        parts = fence_content.split(None, 1)
                        if len(parts) > 1:
                            fence_content = parts[1].strip()
                        else:
                            fence_content = ""
                    
                    if fence_content:
                        fixed_code_lines.append(fence_content)
                    continue 
                else:
                    # Closing fence. Check for inline code before the fence: print("done")```
                    fence_prefix = stripped_line.split('```', 1)[0].strip()
                    if fence_prefix:
                        fixed_code_lines.append(fence_prefix)
                    current_state = None
                    continue
            
            # Check for section headers with potential inline content
            header_found = False
            if 'root cause' in lower_line:
                current_state = 'root_cause'
                header_found = True
                content = stripped_line.split(':', 1)[1].strip() if ':' in stripped_line else ""
            elif 'explanation' in lower_line or 'changes' in lower_line:
                current_state = 'explanation'
                header_found = True
                content = stripped_line.split(':', 1)[1].strip() if ':' in stripped_line else ""
            elif 'wrong with' in lower_line or 'previous attempt' in lower_line:
                current_state = 'retry_analysis'
                header_found = True
                content = stripped_line.split(':', 1)[1].strip() if ':' in stripped_line else ""
            
            if header_found:
                if content:
                    if current_state == 'root_cause':
                        root_cause_lines.append(content)
                    elif current_state == 'explanation':
                        explanation_lines.append(content)
                    elif current_state == 'retry_analysis':
                        retry_analysis_lines.append(content)
                continue
            
            # State actions for non-header lines
            if current_state == 'root_cause':
                root_cause_lines.append(line)
            elif current_state == 'code':
                fixed_code_lines.append(line)
            elif current_state == 'explanation':
                explanation_lines.append(line)
            elif current_state == 'retry_analysis':
                retry_analysis_lines.append(line)
        
        fixed_code = '\n'.join(fixed_code_lines).strip()
        root_cause = '\n'.join(root_cause_lines).strip()
        explanation = '\n'.join(explanation_lines).strip()
        retry_analysis = '\n'.join(retry_analysis_lines).strip()
        
        # Fallback: if no code found, use original
        if not fixed_code:
            fixed_code = original_code
        
        # Estimate confidence based on response quality
        confidence = 0.85 if fixed_code and root_cause else 0.6
        
        return {
            "root_cause": root_cause or "Analysis completed",
            "fixed_code": fixed_code,
            "explanation": explanation or "Code has been fixed",
            "confidence": confidence,
            "retry_analysis": retry_analysis
        }

    async def verify_fix(
        self,
        fixed_code: str,
        original_error: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """Verify the fix in the sandbox."""
        # Real verification logic with robust exception handling
        try:
            # Use the existing sandbox instance
            sandbox = self.sandbox
            result = await sandbox.run_code(fixed_code, language)
            
            # Check if Mock Sandbox is being used
            if getattr(sandbox, "use_mock", False):
                allow_mock_sandbox = os.getenv("ALLOW_MOCK_SANDBOX_VERIFICATION", "false").lower() == "true"
                if not allow_mock_sandbox:
                    return {
                        "verified": False,
                        "output": "Sandbox unavailable: Docker not reachable and mock verification is disabled.",
                        "new_error": "Sandbox unavailable: Docker not reachable",
                        "timestamp": datetime.now().isoformat()
                    }
                # If mock is allowed, treat as verified for testing
                return {
                    "verified": True, 
                    "output": "Mock verification passed (Docker not available).", 
                    "new_error": None, 
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            # Handle sandbox initialization/execution errors gracefully
            error_type = type(e).__name__
            error_details = str(e)
            return {
                "verified": False,
                "output": f"Sandbox error ({error_type}): {error_details}",
                "new_error": f"Verification system error: {error_type}",
                "timestamp": datetime.now().isoformat()
            }
        
        # Check if original error is gone
        verified = True
        new_error = None
        
        if original_error and original_error in result:
            verified = False
            new_error = f"Original error persists: {original_error}"
        elif "Error" in result or "Traceback" in result:
            verified = False
            new_error = result
            
        return {
            "verified": verified,
            "output": result,
            "new_error": new_error,
            "timestamp": datetime.now().isoformat()
        }

    async def execute_full_workflow(
        self,
        error_message: str,
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        language: str = "python"
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
            max_attempts=3,
            language=language
        ):
            yield event

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        """
        Stream log messages for WebSocket consumption.
        
        This method streams both general agent logs and Docker build logs.
        """
        yield f"[{datetime.now().isoformat()}] 🧟‍♂️ Bug Exorcist Agent initialized for {self.bug_id}"
        
        # Stream from the temp log queue if it has anything (like build logs)
        while True:
            try:
                # Use a small timeout to not block forever if no logs are coming
                log_msg = await asyncio.wait_for(self._temp_log_queue.get(), timeout=1.0)
                yield f"[{datetime.now().isoformat()}] {log_msg}"
                self._temp_log_queue.task_done()
            except asyncio.TimeoutError:
                # No logs for now, check if we should continue
                # For now, we'll just keep waiting or we could check a 'done' flag
                break 
            except Exception as e:
                yield f"[{datetime.now().isoformat()}] Error streaming logs: {str(e)}"
                break


# Convenience functions for quick usage
async def quick_fix(error: str, code: str, language: str = "python", api_key: Optional[str] = None) -> str:
    """
    Quick fix - returns only the fixed code without full analysis.
    
    Args:
        error: Error message
        code: Problematic code
        language: The programming language of the code
        api_key: Optional OpenAI API key
        
    Returns:
        Fixed code as string
    """
    agent = BugExorcistAgent(bug_id="quick-fix", openai_api_key=api_key)
    result = await agent.analyze_error(error, code, language=language)
    return result['fixed_code']


async def fix_with_retry(
    error: str,
    code: str,
    max_attempts: int = 3,
    language: str = "python",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fix with automatic retry logic.
    
    Args:
        error: Error message
        code: Problematic code
        max_attempts: Maximum retry attempts
        language: The programming language of the code
        api_key: Optional OpenAI API key
        
    Returns:
        Detailed retry results
    """
    agent = BugExorcistAgent(bug_id="retry-fix", openai_api_key=api_key)
    return await agent.analyze_and_fix_with_retry(
        error_message=error,
        code_snippet=code,
        max_attempts=max_attempts,
        language=language
    )
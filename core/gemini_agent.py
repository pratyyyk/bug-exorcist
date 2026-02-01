"""
core/gemini_agent.py - Gemini AI Fallback Agent for Bug Exorcist

This agent serves as a fallback when GPT-4o fails to analyze or fix bugs.
It uses Google's Gemini 1.5 Pro model to provide an alternative AI perspective.
"""

import os
from datetime import datetime
from typing import Dict, Optional, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


class GeminiFallbackAgent:
    """
    Gemini-powered fallback agent that activates when GPT-4o fails.
    
    Features:
    - Uses Gemini 1.5 Pro for alternative AI analysis
    - Same interface as BugExorcistAgent for seamless fallback
    - Configurable via environment variables
    """

    SYSTEM_PROMPT = """You are the Gemini Bug Analyst, an expert AI debugging assistant.

You serve as a fallback when the primary AI system encounters issues. Your mission is to:
- Analyze runtime errors and stack traces with precision
- Identify root causes of bugs
- Generate clean, production-ready code fixes
- Explain solutions in developer-friendly language
- Learn from previous failed attempts when provided

**Analysis Process:**
1. Carefully examine error messages and stack traces
2. Identify the exact failure point and error type
3. Understand the code context
4. Determine the root cause (not symptoms)
5. Generate a minimal, targeted fix
6. Provide clear explanations

**Retry Context:**
When analyzing a bug that has previous failed attempts, you will receive:
- The original error
- Previous fix attempts and why they failed
- New errors that occurred
- Attempt history

Use this information to:
- Understand what approaches didn't work
- Avoid repeating the same mistakes
- Generate more robust solutions
- Consider edge cases that were missed

**Fix Requirements:**
- Minimal, surgical changes only
- Preserve existing code style
- Add defensive programming where needed
- Include brief inline comments for critical fixes
- Ensure backwards compatibility
- Learn from any provided failure history

**Output Format:**
Provide:
1. Root Cause Analysis (2-3 sentences)
2. Complete fixed code
3. Explanation of changes
4. (On retry) Analysis of why previous attempts failed

Be precise, thorough, and systematic in your debugging approach."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini Fallback Agent.
        
        Args:
            api_key: Google Gemini API key (falls back to env var)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY env variable "
                "or pass it to the constructor."
            )
        
        # Initialize LangChain ChatGoogleGenerativeAI with Gemini 1.5 Pro
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.2,  # Low temperature for focused, deterministic fixes
            google_api_key=self.api_key,
            max_output_tokens=2000
        )
        
        self.model_name = "gemini-1.5-pro"

    async def analyze_error(
        self, 
        error_message: str, 
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
        gpt_failure_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze an error using Gemini 1.5 Pro.
        
        Args:
            error_message: The error/exception message with stack trace
            code_snippet: The code that caused the error
            file_path: Optional file path for context
            additional_context: Optional additional context about the bug
            previous_attempts: List of previous fix attempts that failed
            gpt_failure_context: Information about why GPT-4o failed
            
        Returns:
            Dictionary containing analysis results
        """
        attempt_number = len(previous_attempts) + 1 if previous_attempts else 1
        
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
        
        # Add GPT-4o failure context if this is a fallback scenario
        if gpt_failure_context:
            user_prompt += f"\n**IMPORTANT - PRIMARY AI FAILED:**\n{gpt_failure_context}\n\n"
            user_prompt += "You are the fallback AI. The primary system (GPT-4o) encountered issues.\n"
            user_prompt += "Provide an independent analysis and solution.\n\n"
        
        # Add retry context if this is not the first attempt
        if previous_attempts:
            user_prompt += f"\n**GEMINI RETRY ATTEMPT #{attempt_number}**\n"
            user_prompt += f"**Previous Gemini attempts have failed. Learn from these mistakes:**\n\n"
            
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
            # Call Gemini via LangChain
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.agenerate([messages])
            ai_response = response.generations[0][0].text
            
            # Extract usage metrics for Gemini
            # LangChain Gemini usually puts usage in message.usage_metadata or llm_output
            usage = {}
            if response.llm_output:
                usage = response.llm_output.get("token_usage", {})
            
            # Fallback for some LangChain versions
            if not usage and hasattr(response.generations[0][0].message, "usage_metadata"):
                usage = response.generations[0][0].message.usage_metadata
            
            prompt_tokens = usage.get("prompt_tokens", usage.get("input_token_count", 0))
            completion_tokens = usage.get("completion_tokens", usage.get("output_token_count", 0))
            
            # Calculate estimated cost for Gemini 1.5 Pro
            # Input: $3.50 / 1M tokens, Output: $10.50 / 1M tokens
            estimated_cost = (prompt_tokens * 0.0000035) + (completion_tokens * 0.0000105)
            
            # Parse the AI response
            result = self._parse_ai_response(ai_response, code_snippet)
            
            return {
                "ai_agent": "gemini-1.5-pro",
                "fallback_agent": True,
                "root_cause": result["root_cause"],
                "fixed_code": result["fixed_code"],
                "explanation": result["explanation"],
                "confidence": result["confidence"],
                "original_error": error_message,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": attempt_number,
                "retry_analysis": result.get("retry_analysis", ""),
                "gpt_failed": gpt_failure_context is not None,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "estimated_cost": estimated_cost,
                    "model": "gemini-1.5-pro"
                }
            }
            
        except Exception as e:
            # If Gemini also fails, return error info
            return {
                "ai_agent": "gemini-1.5-pro",
                "fallback_agent": True,
                "error": f"Gemini analysis failed: {str(e)}",
                "root_cause": "Gemini analysis failed",
                "fixed_code": code_snippet,
                "explanation": f"Error during Gemini analysis: {str(e)}",
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": attempt_number,
                "gemini_failed": True
            }

    def _parse_ai_response(self, ai_response: str, original_code: str) -> Dict[str, Any]:
        """
        Parse Gemini's response to extract structured components.
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
        confidence = 0.8 if fixed_code.strip() and root_cause else 0.5
        
        return {
            "root_cause": root_cause or "Analysis completed by Gemini",
            "fixed_code": fixed_code.strip(),
            "explanation": explanation or "Code has been fixed by Gemini",
            "confidence": confidence,
            "retry_analysis": retry_analysis
        }


def is_gemini_enabled() -> bool:
    """Check if Gemini fallback is enabled via environment variable."""
    return os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() == "true"


def is_gemini_available() -> bool:
    """Check if Gemini API key is configured."""
    return bool(os.getenv("GEMINI_API_KEY"))
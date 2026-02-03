"""
core/ollama_provider.py - Ollama Local LLM Provider for Bug Exorcist

This provider allows connecting to local LLMs via Ollama (e.g., llama3, mistral).
It enables offline capabilities and enhanced privacy for bug analysis.
"""

import os
from datetime import datetime
from typing import Dict, Optional, Any, List
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage


class OllamaProvider:
    """
    Ollama-powered local LLM provider.
    
    Features:
    - Connects to local models (llama3, mistral, etc.)
    - Supports host.docker.internal for Docker-to-Host networking
    - Same interface as BugExorcistAgent for seamless integration
    """

    SYSTEM_PROMPT = """You are the Ollama Bug Analyst, a local AI debugging specialist.

Your mission is to analyze runtime errors and generate production-ready fixes.
As a local model, you prioritize privacy and offline efficiency.

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
- New errors that occurred
- Attempt history

Use this information to avoid repeating mistakes and generate more robust solutions.

**Fix Requirements:**
- Minimal, surgical changes only
- Preserve existing code style
- Add defensive programming where needed
- Include brief inline comments for critical fixes
- Ensure backwards compatibility

**Output Format:**
Provide:
1. Root Cause Analysis (2-3 sentences)
2. Complete fixed code (ready to deploy)
3. Explanation of changes
4. (On retry) Analysis of why previous attempts failed

Be systematic, thorough, and precise."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Ollama Provider.
        
        Args:
            model: Ollama model name (defaults to OLLAMA_MODEL env var or 'llama3')
            base_url: Ollama API base URL (defaults to OLLAMA_BASE_URL env var or 'http://localhost:11434')
        """
        self.model_name = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Initialize LangChain ChatOllama
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.2,
        )

    async def analyze_error(
        self, 
        error_message: str, 
        code_snippet: str,
        file_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze an error using a local Ollama model.
        
        Args:
            error_message: The error/exception message with stack trace
            code_snippet: The code that caused the error
            file_path: Optional file path for context
            additional_context: Optional additional context about the bug
            previous_attempts: List of previous fix attempts that failed
            
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
        
        # Add retry context if this is not the first attempt
        if previous_attempts:
            user_prompt += f"\n**OLLAMA RETRY ATTEMPT #{attempt_number}**\n"
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
"""
        
        user_prompt += """
Please provide:
1. Root Cause Analysis
2. The complete fixed code
3. Explanation of your changes
"""
        
        if previous_attempts:
            user_prompt += "4. Analysis of previous failures\n"
        
        try:
            # Call Ollama via LangChain
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            ai_response = response.content
            
            # Parse the AI response
            result = self._parse_ai_response(ai_response, code_snippet)
            
            return {
                "ai_agent": f"ollama/{self.model_name}",
                "root_cause": result["root_cause"],
                "fixed_code": result["fixed_code"],
                "explanation": result["explanation"],
                "confidence": result["confidence"],
                "original_error": error_message,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": attempt_number,
                "usage": {
                    "model": self.model_name,
                    "local": True
                }
            }
            
        except Exception as e:
            return {
                "ai_agent": f"ollama/{self.model_name}",
                "error": f"Ollama analysis failed: {str(e)}",
                "root_cause": "Local model analysis failed",
                "fixed_code": code_snippet,
                "explanation": f"Error during Ollama analysis: {str(e)}",
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat(),
                "attempt_number": attempt_number
            }

    def _parse_ai_response(self, ai_response: str, original_code: str) -> Dict[str, Any]:
        """
        Parse Ollama's response to extract structured components.
        """
        lines = ai_response.split('\n')
        
        root_cause = ""
        fixed_code = ""
        explanation = ""
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
        
        # Fallback: if no code found, use original
        if not fixed_code.strip():
            fixed_code = original_code
        
        # Estimate confidence based on response quality
        confidence = 0.7 if fixed_code.strip() and root_cause else 0.4
        
        return {
            "root_cause": root_cause or "Analysis completed by Ollama",
            "fixed_code": fixed_code.strip(),
            "explanation": explanation or "Code has been fixed by local model",
            "confidence": confidence
        }


def is_ollama_available() -> bool:
    """Check if Ollama is accessible."""
    import requests
    import os
    
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        # Check if Ollama is running by calling its API
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

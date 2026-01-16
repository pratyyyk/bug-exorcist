"""
core/fallback.py - Graceful Fallback Handler for Bug Exorcist

Provides hardcoded fallback responses when AI analysis fails after all retry attempts.
This ensures users always receive actionable feedback even when the AI cannot fix the bug.
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime


class FallbackHandler:
    """
    Handles graceful fallback when AI-powered bug fixing fails.
    
    Provides:
    - User-friendly error messages
    - Common bug pattern suggestions
    - Manual debugging guidance
    - Resource links
    """
    
    def __init__(self):
        """Initialize the fallback handler."""
        self.enabled = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"
        
        # Common error patterns and their manual fix suggestions
        self.error_patterns = {
            "ZeroDivisionError": {
                "title": "Division by Zero Detected",
                "description": "Your code is attempting to divide by zero, which is mathematically undefined.",
                "common_fixes": [
                    "Add a check: `if denominator != 0:` before division",
                    "Use a try-except block to catch ZeroDivisionError",
                    "Set a default return value for zero division cases",
                    "Validate input before performing division operations"
                ],
                "example_fix": """def divide(a, b):
    if b == 0:
        return 0  # or raise ValueError("Cannot divide by zero")
    return a / b"""
            },
            
            "IndexError": {
                "title": "List Index Out of Range",
                "description": "Your code is trying to access a list index that doesn't exist.",
                "common_fixes": [
                    "Check list length before accessing: `if len(list) > index:`",
                    "Use try-except to catch IndexError",
                    "Use list.get() for dictionaries or safe access patterns",
                    "Validate indices are within valid range [0, len(list)-1]"
                ],
                "example_fix": """def get_item(items, index):
    if index < 0 or index >= len(items):
        return None  # or raise appropriate error
    return items[index]"""
            },
            
            "KeyError": {
                "title": "Dictionary Key Not Found",
                "description": "Your code is accessing a dictionary key that doesn't exist.",
                "common_fixes": [
                    "Use dict.get(key, default) instead of dict[key]",
                    "Check if key exists: `if key in dictionary:`",
                    "Use try-except to catch KeyError",
                    "Use defaultdict from collections module"
                ],
                "example_fix": """def get_value(data, key):
    return data.get(key, None)  # Returns None if key doesn't exist
    # or
    if key in data:
        return data[key]"""
            },
            
            "TypeError": {
                "title": "Type Mismatch Error",
                "description": "Your code is performing an operation on incompatible data types.",
                "common_fixes": [
                    "Add type conversion: int(), str(), float(), etc.",
                    "Validate types before operations: isinstance(var, type)",
                    "Use type hints and static type checking",
                    "Handle None values explicitly"
                ],
                "example_fix": """def add_values(a, b):
    # Convert to integers before adding
    return int(a) + int(b)
    # or validate types
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both arguments must be integers")"""
            },
            
            "AttributeError": {
                "title": "Attribute or Method Not Found",
                "description": "Your code is trying to access an attribute or method that doesn't exist on the object.",
                "common_fixes": [
                    "Check if attribute exists: hasattr(obj, 'attr')",
                    "Validate object is not None before accessing attributes",
                    "Use getattr(obj, 'attr', default) for safe access",
                    "Verify object type matches expected class"
                ],
                "example_fix": """def process(obj):
    if obj is None:
        return None
    if hasattr(obj, 'process'):
        return obj.process()
    return default_process(obj)"""
            },
            
            "ValueError": {
                "title": "Invalid Value Error",
                "description": "Your code received a value that's the right type but inappropriate for the operation.",
                "common_fixes": [
                    "Add input validation before operations",
                    "Use try-except to catch ValueError",
                    "Provide clear error messages for invalid inputs",
                    "Use regex or validation libraries for complex validation"
                ],
                "example_fix": """def parse_number(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Cannot convert '{value}' to integer")"""
            },
            
            "NameError": {
                "title": "Undefined Variable or Name",
                "description": "Your code references a variable or name that hasn't been defined.",
                "common_fixes": [
                    "Check for typos in variable names",
                    "Ensure variables are defined before use",
                    "Check variable scope (local vs global)",
                    "Import required modules and functions"
                ],
                "example_fix": """# Define variable before use
result = None  # Initialize
if condition:
    result = calculate()
return result"""
            },
            
            "ImportError": {
                "title": "Module Import Failed",
                "description": "Your code cannot import a required module or package.",
                "common_fixes": [
                    "Install missing package: pip install <package>",
                    "Check package name spelling",
                    "Verify package is in requirements.txt",
                    "Check Python path and virtual environment"
                ],
                "example_fix": """# Add to requirements.txt
# package-name==version
# Then run: pip install -r requirements.txt"""
            }
        }
    
    def is_enabled(self) -> bool:
        """Check if fallback is enabled."""
        return self.enabled
    
    def identify_error_type(self, error_message: str) -> Optional[str]:
        """
        Identify the error type from the error message.
        
        Args:
            error_message: The error message string
            
        Returns:
            Error type key if found, None otherwise
        """
        for error_type in self.error_patterns.keys():
            if error_type in error_message:
                return error_type
        return None
    
    def generate_fallback_response(
        self,
        error_message: str,
        code_snippet: str,
        bug_id: str,
        total_attempts: int,
        all_attempts: list
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive fallback response when AI fails.
        
        Args:
            error_message: The original error message
            code_snippet: The problematic code
            bug_id: Bug identifier
            total_attempts: Number of attempts made
            all_attempts: List of all attempt records
            
        Returns:
            Structured fallback response with guidance
        """
        error_type = self.identify_error_type(error_message)
        
        # Base fallback response
        response = {
            "bug_id": bug_id,
            "status": "ai_analysis_failed",
            "fallback_enabled": True,
            "total_attempts": total_attempts,
            "timestamp": datetime.now().isoformat(),
            
            "error_summary": {
                "original_error": error_message,
                "error_type": error_type or "Unknown",
                "code_snippet": code_snippet[:500] + "..." if len(code_snippet) > 500 else code_snippet
            },
            
            "ai_failure_notice": {
                "title": "AI Analysis Unavailable",
                "message": f"The AI was unable to generate a verified fix after {total_attempts} attempts.",
                "reason": "All automatic fix attempts failed verification in the sandbox environment.",
                "impact": "You will need to apply manual debugging to resolve this issue."
            }
        }
        
        # Add pattern-specific guidance if available
        if error_type and error_type in self.error_patterns:
            pattern = self.error_patterns[error_type]
            response["manual_guidance"] = {
                "title": pattern["title"],
                "description": pattern["description"],
                "suggested_fixes": pattern["common_fixes"],
                "example_solution": pattern["example_fix"]
            }
        else:
            # Generic guidance for unknown errors
            response["manual_guidance"] = {
                "title": "Unknown Error Type",
                "description": "The error type couldn't be automatically identified. Manual debugging is required.",
                "suggested_fixes": [
                    "Read the error message carefully to understand what went wrong",
                    "Check the line number mentioned in the stack trace",
                    "Review recent code changes that might have introduced the bug",
                    "Add print statements or use a debugger to trace execution",
                    "Search for the error message online for similar cases",
                    "Consult documentation for the libraries or frameworks involved"
                ],
                "example_solution": "# Add debugging\nprint(f'Debug: variable = {variable}')\nprint(f'Debug: type = {type(variable)}')"
            }
        
        # Add debugging steps
        response["debugging_steps"] = [
            {
                "step": 1,
                "action": "Understand the Error",
                "description": "Read the error message and identify the exact line causing the issue"
            },
            {
                "step": 2,
                "action": "Reproduce Locally",
                "description": "Try to reproduce the error in your development environment"
            },
            {
                "step": 3,
                "action": "Add Logging",
                "description": "Insert print statements or logging to inspect variable values"
            },
            {
                "step": 4,
                "action": "Test Incrementally",
                "description": "Make small changes and test after each modification"
            },
            {
                "step": 5,
                "action": "Seek Help",
                "description": "If stuck, consult documentation, Stack Overflow, or team members"
            }
        ]
        
        # Add resource links
        response["helpful_resources"] = {
            "documentation": [
                {
                    "name": "Python Official Documentation",
                    "url": "https://docs.python.org/3/",
                    "description": "Comprehensive Python language reference"
                },
                {
                    "name": "Stack Overflow",
                    "url": f"https://stackoverflow.com/search?q={error_type or 'python error'}",
                    "description": "Community-driven Q&A for programming issues"
                }
            ],
            "debugging_tools": [
                {
                    "name": "Python Debugger (pdb)",
                    "description": "Built-in interactive debugger for Python",
                    "usage": "import pdb; pdb.set_trace()"
                },
                {
                    "name": "Print Debugging",
                    "description": "Simple but effective debugging with print statements",
                    "usage": "print(f'Debug: {variable=}')"
                }
            ]
        }
        
        # Add attempt summary
        response["attempt_summary"] = {
            "attempts": [
                {
                    "attempt_number": attempt["attempt_number"],
                    "result": attempt["verification_result"],
                    "error": attempt.get("new_error", "Unknown")[:200] if attempt.get("new_error") else None
                }
                for attempt in all_attempts
            ],
            "conclusion": f"None of the {total_attempts} AI-generated fixes passed verification."
        }
        
        # Add next steps recommendation
        response["recommended_next_steps"] = [
            "Review the manual guidance provided above",
            "Try the example solution as a starting point",
            "Use the debugging steps to investigate further",
            "Consult the helpful resources for more information",
            "If this is a critical bug, escalate to senior developers"
        ]
        
        return response
    
    def generate_api_failure_response(
        self,
        error_message: str,
        bug_id: str,
        api_error: str
    ) -> Dict[str, Any]:
        """
        Generate fallback response for API/connection failures.
        
        Args:
            error_message: The original error message
            bug_id: Bug identifier
            api_error: The API error that occurred
            
        Returns:
            Structured fallback response for API failures
        """
        return {
            "bug_id": bug_id,
            "status": "api_connection_failed",
            "fallback_enabled": True,
            "timestamp": datetime.now().isoformat(),
            
            "error_summary": {
                "original_error": error_message,
                "api_error": api_error
            },
            
            "service_notice": {
                "title": "AI Service Unavailable",
                "message": "The AI debugging service is currently unavailable.",
                "reason": "Could not connect to the OpenAI API or the connection timed out.",
                "impact": "Automatic bug fixing is temporarily disabled."
            },
            
            "troubleshooting": {
                "possible_causes": [
                    "OpenAI API key is invalid or missing",
                    "Network connectivity issues",
                    "OpenAI service is experiencing downtime",
                    "API rate limits exceeded",
                    "Firewall or proxy blocking the connection"
                ],
                "solutions": [
                    "Check OPENAI_API_KEY in .env file",
                    "Verify internet connection",
                    "Check OpenAI status at https://status.openai.com",
                    "Wait a few minutes and try again",
                    "Contact system administrator if problem persists"
                ]
            },
            
            "manual_debugging": {
                "message": "While the AI service is unavailable, you can debug manually:",
                "steps": [
                    "Read the error message carefully",
                    "Identify the line number in the stack trace",
                    "Add print/logging statements to inspect variables",
                    "Test your code with different inputs",
                    "Consult documentation and online resources"
                ]
            },
            
            "recommended_actions": [
                "Try the manual debugging steps above",
                "Check system health at /api/agent/health",
                "Retry the request in a few minutes",
                "Contact support if the issue persists"
            ]
        }


# Singleton instance
_fallback_handler = None

def get_fallback_handler() -> FallbackHandler:
    """Get the singleton fallback handler instance."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()
    return _fallback_handler
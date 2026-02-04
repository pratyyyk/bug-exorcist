"""
core/gemini_agent.py - Gemini AI Fallback Agent for Bug Exorcist

This module provides factory functions for Google's Gemini LLM.
It serves as an alternative AI perspective for bug analysis.
"""

import os
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI


class GeminiFallbackAgent:
    """
    Gemini-powered agent that provides access to Gemini 1.5 Pro.
    
    This class now primarily serves as a wrapper for the LangChain LLM object
    to maintain compatibility with the BugExorcistAgent's initialization.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini Agent.
        
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


def is_gemini_enabled() -> bool:
    """Check if Gemini fallback is enabled via environment variable."""
    return os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() == "true"


def is_gemini_available() -> bool:
    """Check if Gemini API key is configured."""
    return bool(os.getenv("GEMINI_API_KEY"))

"""
core/ollama_provider.py - Ollama Local LLM Provider for Bug Exorcist

This module provides factory functions and health checks for Ollama local LLMs.
It enables offline capabilities and enhanced privacy for bug analysis.
"""

import os
import logging
import requests
from typing import Optional
from langchain_ollama import ChatOllama

# Setup logger
logger = logging.getLogger(__name__)


def get_ollama_llm(model: Optional[str] = None, base_url: Optional[str] = None) -> ChatOllama:
    """
    Factory function to create a LangChain ChatOllama instance.
    
    Args:
        model: Ollama model name (defaults to OLLAMA_MODEL env var or 'llama3')
        base_url: Ollama API base URL (defaults to OLLAMA_BASE_URL env var or 'http://localhost:11434')
        
    Returns:
        Configured ChatOllama instance
    """
    model_name = model or os.getenv("OLLAMA_MODEL", "llama3")
    base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.2,
    )


def is_ollama_available() -> bool:
    """
    Check if Ollama is accessible.
    
    Returns:
        True if Ollama is running and responsive, False otherwise.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        # Check if Ollama is running by calling its API
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.warning(f"Ollama availability check failed at {base_url}: {str(e)}")
        return False

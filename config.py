"""
Configuration de l'agent UAM
Définit les enums, constantes et configurations
"""
from enum import Enum


class LLMProvider(Enum):
    """Providers LLM supportés"""
    OPENAI = "openai"
    CLAUDE = "claude"
    LLAMA_OLLAMA = "llama_ollama"
    LLAMA_GROQ = "llama_groq"
    OPENROUTER = "openrouter"


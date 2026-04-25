"""
Configuration de l'agent UAM
"""
from enum import Enum


class LLMProvider(Enum):
    """Provider LLM utilisé"""
    OPENROUTER = "openrouter"

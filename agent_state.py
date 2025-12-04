"""
État de l'agent conversationnel
"""
from typing import Annotated, TypedDict, Sequence, Dict, Any
from operator import add
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """État de l'agent conversationnel avec gestion moderne des messages"""
    # Utilisation d'Annotated pour la réduction automatique des messages
    messages: Annotated[Sequence[BaseMessage], add]
    question: str
    is_relevant: bool
    context: str
    response: str
    need_clarification: bool
    user_id: str  # ID utilisateur pour la mémoire à long terme
    user_preferences: Dict[str, Any]  # Préférences utilisateur



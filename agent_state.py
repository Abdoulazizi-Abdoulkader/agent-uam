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
    user_id: str
    user_preferences: Dict[str, Any]
    tool_iterations: int
    # Routage : défini par route_and_store, lu par l'arête conditionnelle et handle_special_case
    routing_hint: str     # destination : "agent" | "reject_query" | "handle_special_case"
    routing_context: str  # sous-type pour handle_special_case : "FAREWELL" | "THANKS" | "FRUSTRATION" | "CONFUSION" | "REPETITION"
    # Profil détecté une seule fois par route_and_store, réutilisé par call_model
    user_profile: str     # ex : "BACHELIER" | "CANDIDAT_MASTER" | "INCONNU" | …



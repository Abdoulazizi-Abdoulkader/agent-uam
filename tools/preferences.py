"""Outils de mémoire utilisateur : préférences attachées à la session."""
import json

from langchain_core.tools import tool

from memory import _user_memory

from ._session import _get_session_user_id


@tool
def save_user_preference(preference_key: str, preference_value: str) -> str:
    """
    Sauvegarde une préférence utilisateur pour la mémoire à long terme.
    L'identifiant de session est géré côté serveur — ne pas fournir de user_id.

    Args:
        preference_key: Clé de la préférence (ex: 'faculte_interesse', 'niveau_etude')
        preference_value: Valeur de la préférence

    Returns:
        Confirmation de sauvegarde
    """
    uid = _get_session_user_id()
    if not uid:
        return "Session non initialisée — préférence non sauvegardée."
    _user_memory.save_user_preference(uid, preference_key, preference_value)
    return f"Préférence '{preference_key}' sauvegardée avec succès : {preference_value}"


@tool
def get_user_preferences() -> str:
    """
    Récupère les préférences sauvegardées de la session courante.
    L'identifiant de session est géré côté serveur.

    Returns:
        Préférences de l'utilisateur au format JSON
    """
    uid = _get_session_user_id()
    if not uid:
        return "Session non initialisée — aucune préférence disponible."
    preferences = _user_memory.get_user_preferences(uid)
    if not preferences:
        return "Aucune préférence sauvegardée pour cette session."
    return json.dumps(preferences, ensure_ascii=False, indent=2)

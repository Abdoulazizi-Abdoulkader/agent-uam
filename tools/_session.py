"""Identifiant de session propagé aux outils.

Un ContextVar et non un threading.local : le ToolNode exécute les outils dans
un pool de threads, qui héritent du contexte mais pas du stockage par thread.
"""
import contextvars

# user_id de session, isolé par contexte d'exécution pour éviter les collisions
# inter-sessions. Un ContextVar (et non un threading.local) est nécessaire car le
# ToolNode exécute les outils dans un pool de threads : ces threads héritent du
# contexte de l'appelant, ce qu'un stockage par thread ne permet pas.
# Appelez set_session_user_id() au début de chaque requête ou session.
_session_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "uam_session_user_id", default=None
)


def set_session_user_id(user_id: str) -> None:
    """Fixe l'identifiant de session pour le contexte d'exécution courant."""
    _session_user_id.set(user_id)


def _get_session_user_id() -> str | None:
    return _session_user_id.get()

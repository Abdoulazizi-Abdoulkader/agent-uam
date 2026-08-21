"""Recherche RAG partagée : interrogation du vectorstore et formatage unifié."""
from context_tracker import push_context
from logger_config import get_logger

from ._vectorstore import get_vectorstore

try:
    import grounding_capture as _gc
    _GROUNDING_AVAILABLE = True
except ImportError:
    # `_gc = None` : recherche.py importe ce nom au chargement, alors que
    # tools.py le résolvait paresseusement. Il n'est jamais déréférencé sans
    # `_GROUNDING_AVAILABLE`, qui court-circuite la condition.
    _gc = None
    _GROUNDING_AVAILABLE = False

logger = get_logger(__name__)


def _rag_search(query: str, k: int = 5) -> list:
    """Effectue une recherche FAISS et enregistre le contexte pour RAGAS.

    En mode grounding (run gelé), utilise similarity_search_with_score
    et journalise les chunks+scores via grounding_capture.
    """
    if get_vectorstore() is None:
        return []
    if _GROUNDING_AVAILABLE and _gc.is_enabled():
        docs_scores = get_vectorstore().similarity_search_with_score(query, k=k)
        _gc.log_retrieval(query, docs_scores)
        docs = [d for d, _ in docs_scores]
    else:
        docs = get_vectorstore().similarity_search(query, k=k)
    push_context([d.page_content for d in docs])
    return docs


def _rag_response(query: str, not_found_msg: str = "Aucune information trouvée.", k: int = 5) -> str:
    """Recherche RAG + formatage unifié. Utilisé par tous les outils de recherche simples."""
    if get_vectorstore() is None:
        return "Erreur: Base de connaissances non initialisée"
    docs = _rag_search(query, k=k)
    logger.debug(f"_rag_response — requête: '{query[:80]}' → {len(docs)} doc(s)")
    if not docs:
        return not_found_msg
    return "\n\n---\n\n".join(doc.page_content[:800] for doc in docs)

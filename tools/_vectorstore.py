"""État global du vectorstore FAISS, partagé par les modules d'outils.

Ce module est le seul à porter la variable `_vectorstore` : `set_vectorstore()`
rebinde le nom dans ce namespace-ci. Un lecteur situé dans un autre module qui
ferait `from ._vectorstore import _vectorstore` capturerait la valeur None au
moment de l'import et ne verrait jamais l'affectation — il doit donc appeler
`get_vectorstore()`. Seules les fonctions définies ici lisent le nom nu.
"""
import threading
from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langsmith import traceable

# Vectorstore global avec protection thread-safe
_vectorstore = None
_vectorstore_lock = threading.Lock()


@traceable
def set_vectorstore(vectorstore: FAISS):
    """Définit le vectorstore global pour les outils (thread-safe)"""
    global _vectorstore
    with _vectorstore_lock:
        _vectorstore = vectorstore
        _cached_similarity_search.cache_clear()


def get_vectorstore():
    """Retourne le vectorstore global courant.

    Point d'accès obligatoire pour tout lecteur extérieur à ce module.
    """
    return _vectorstore


@lru_cache(maxsize=256)
def _cached_similarity_search(query_normalized: str, k: int) -> tuple:
    """Recherche FAISS avec mise en cache LRU intra-session.

    Appelle directement le vectorstore (sans push_context) pour éviter le double
    enregistrement de contexte quand search_uam_knowledge appelle push_context après.
    Non utilisé en mode grounding (bypassed dans search_uam_knowledge).
    """
    if _vectorstore is None:
        return ()
    docs = _vectorstore.similarity_search(query_normalized, k=k)
    return tuple(doc.page_content for doc in docs)

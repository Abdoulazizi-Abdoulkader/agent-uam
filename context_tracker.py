"""
Tracker thread-safe des contextes RAG réellement utilisés par l'agent
pendant une invocation. Permet à evaluate.py de fournir à RAGAS le vrai
contexte (et non un retrieval a posteriori).
"""
import threading
from typing import List

_buffer = threading.local()


def push_context(chunks: List[str]) -> None:
    """Ajoute des chunks au buffer de la requête en cours."""
    if not hasattr(_buffer, "chunks"):
        _buffer.chunks = []
    _buffer.chunks.extend(c for c in chunks if c)


def push_text(text: str) -> None:
    """Ajoute un bloc de texte unique (pour outils retournant des strings)."""
    if text:
        push_context([text])


def flush_context() -> List[str]:
    """Récupère et vide le buffer. À appeler après chaque invocation d'agent."""
    chunks = getattr(_buffer, "chunks", [])
    _buffer.chunks = []
    return chunks


def reset() -> None:
    """Vide le buffer sans rien retourner (pour init avant requête)."""
    _buffer.chunks = []

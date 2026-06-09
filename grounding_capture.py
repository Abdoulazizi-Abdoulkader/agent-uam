"""
Module de capture des chunks RAG pour l'audit d'ancrage (Option A).

Usage EXCLUSIF dans run_grounding_capture.py (run gelé).
Ne pas importer en production — utiliser context_tracker à la place.

Séquence :
    grounding_capture.enable()
    grounding_capture.set_current_question("Q01", "...", "inscription_premiere")
    # → l'agent tourne → log_retrieval est appelé automatiquement depuis tools.py
    grounding_capture.dump("grounding_log.json")
"""
import json
import threading
import datetime
from pathlib import Path
from typing import List, Tuple, Any

# ── État interne ───────────────────────────────────────────────────────────────

_LOG: List[dict] = []
_ctx = threading.local()      # question courante par thread
_enabled: bool = False        # activé uniquement pendant le run gelé


# ── Activation / désactivation ─────────────────────────────────────────────────

def enable() -> None:
    """Active la capture. Vide le log précédent."""
    global _enabled, _LOG
    _enabled = True
    _LOG = []


def disable() -> None:
    global _enabled
    _enabled = False


def is_enabled() -> bool:
    return _enabled


# ── Marquage de la question courante ──────────────────────────────────────────

def set_current_question(qid: str, question: str, categorie: str) -> None:
    """Enregistre la question en cours (thread-local) avant l'invocation de l'agent."""
    _ctx.qid = qid
    _ctx.question = question
    _ctx.categorie = categorie


# ── Journalisation d'un appel de récupération ─────────────────────────────────

def log_retrieval(query_used: str, docs_with_scores: List[Tuple[Any, float]]) -> None:
    """
    Journalise un appel FAISS avec les chunks et scores retournés.

    query_used      : requête réellement envoyée au vectorstore
                      (peut différer de la question si l'agent la reformule)
    docs_with_scores : liste de tuples (Document, score) retournée par
                      similarity_search_with_score
    """
    if not _enabled:
        return
    _LOG.append({
        "question_id": getattr(_ctx, "qid", None),
        "question":    getattr(_ctx, "question", None),
        "categorie":   getattr(_ctx, "categorie", None),
        "query_used":  query_used,
        "timestamp":   datetime.datetime.now().isoformat(),
        "chunks": [
            {
                "rang":     i + 1,
                "score":    float(score),
                "source":   doc.metadata.get("source", "?"),
                "chunk_id": doc.metadata.get("chunk_id",
                            doc.metadata.get("seq", str(i))),
                "texte":    doc.page_content,
            }
            for i, (doc, score) in enumerate(docs_with_scores)
        ],
    })


# ── Sauvegarde du log ─────────────────────────────────────────────────────────

def dump(path: str = "grounding_log.json") -> None:
    """Écrit le log complet en JSON UTF-8. À appeler après le run gelé."""
    Path(path).write_text(
        json.dumps(_LOG, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(_LOG)} appels de récupération journalisés → {path}")


# ── Statistiques rapides (vérification post-run) ──────────────────────────────

def verify(expected_count: int = 74) -> None:
    """Affiche un résumé de cohérence du log. À lancer après dump()."""
    import collections
    par_q: dict = collections.defaultdict(list)
    for entry in _LOG:
        qid = entry.get("question_id")
        if qid:
            par_q[qid].append(entry)

    print(f"\n── Vérification grounding log ──")
    print(f"Questions avec ≥1 récupération : {len(par_q)} / {expected_count}")

    multi = {q: len(v) for q, v in par_q.items() if len(v) > 1}
    if multi:
        print(f"Questions à récupérations multiples (ReAct loops) : {multi}")
    else:
        print("Aucune récupération multiple.")

    attendues = {f"Q{n:02d}" for n in range(1, expected_count + 1)}
    sans_recup = sorted(attendues - set(par_q.keys()))
    if sans_recup:
        print(f"Questions SANS récupération : {sans_recup}")
        print("  → À marquer 'Aucune récupération' dans le classeur évaluateur.")
    else:
        print("Toutes les questions ont au moins une récupération.")
    print()

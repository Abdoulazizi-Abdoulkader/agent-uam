"""
Couche de service de l'agent UAM — partagée par le site web et WhatsApp.

Factorise la logique jusqu'ici dupliquée dans app_streamlit.py, chatbot.py et
evaluate.py : construction du state, invocation du graphe, extraction de la réponse.

L'agent (LLM + vectorstore + graphe) est construit une seule fois par processus :
le modèle d'embeddings HuggingFace pèse ~1 Go en mémoire et met 5 à 12 s à charger.
"""
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Le projet est organisé à plat à la racine : on l'ajoute au path pour permettre
# `uvicorn api.main:app` depuis n'importe quel répertoire.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage  # noqa: E402

from agent_graph import create_agent_graph  # noqa: E402
from app_config import LLMProvider, get_config  # noqa: E402
from document_loader import load_and_index_documents  # noqa: E402
from llm_utils import initialize_llm  # noqa: E402
from logger_config import get_logger  # noqa: E402
from memory import _user_memory  # noqa: E402
from metrics import record_question, record_system_metrics  # noqa: E402
from tools import set_session_user_id  # noqa: E402

logger = get_logger(__name__)

# Le graphe est synchrone et bloquant : on borne le nombre d'exécutions simultanées
# pour ne pas saturer le pool de threads ni le quota OpenRouter.
_MAX_CONCURRENT_RUNS = 4
_run_semaphore = threading.Semaphore(_MAX_CONCURRENT_RUNS)

_agent = None
_vectorstore = None
_init_lock = threading.Lock()


@dataclass
class AnswerResult:
    """Résultat d'une question posée à l'agent."""
    response: str
    elapsed_ms: int
    sources: List[Dict[str, str]] = field(default_factory=list)
    error: Optional[str] = None


def get_agent():
    """Retourne le graphe LangGraph compilé, en le construisant au premier appel.

    Double-checked locking, comme app_config.get_config().
    """
    global _agent, _vectorstore

    if _agent is not None:
        return _agent

    with _init_lock:
        if _agent is not None:
            return _agent

        config = get_config()
        logger.info("Initialisation de l'agent UAM (LLM + vectorstore + graphe)…")
        start = time.perf_counter()

        llm = initialize_llm(LLMProvider.OPENROUTER)
        _vectorstore = load_and_index_documents(
            config.documents_directory, LLMProvider.OPENROUTER
        )
        _agent = create_agent_graph(_vectorstore, llm)

        logger.info(
            f"Agent UAM prêt en {time.perf_counter() - start:.1f}s "
            f"(modèle : {config.llm.model_name})"
        )
        return _agent


def get_vectorstore():
    """Retourne le vectorstore FAISS (utilisé pour afficher les sources)."""
    if _vectorstore is None:
        get_agent()
    return _vectorstore


def _extract_response(result: Dict[str, Any]) -> str:
    """Extrait le texte de réponse du state retourné par le graphe.

    `result["response"]` n'est rempli que par les nœuds reject_query et
    handle_special_case. Sur le chemin LLM normal (call_model), il reste vide :
    il faut alors remonter les messages et prendre le dernier message porteur de
    contenu qui ne soit pas un appel d'outil.
    """
    text = result.get("response", "")
    if text:
        return text

    for message in reversed(result.get("messages", [])):
        content = getattr(message, "content", None)
        if content and not getattr(message, "tool_calls", None):
            return content

    return ""


def _collect_sources(question: str, limit: int) -> List[Dict[str, str]]:
    """Recherche les extraits de documents ayant pu fonder la réponse."""
    try:
        docs = get_vectorstore().similarity_search(question, k=limit)
    except Exception as exc:  # la recherche de sources ne doit jamais casser la réponse
        logger.warning(f"Recherche de sources impossible : {exc}")
        return []

    return [
        {
            "source": os.path.basename(doc.metadata.get("source", "document")),
            "content": doc.page_content[:400],
        }
        for doc in docs
    ]


def _humanize_error(exc: Exception) -> str:
    """Traduit une exception technique en message affichable."""
    detail = str(exc)
    if "401" in detail or "User not found" in detail:
        return (
            "La clé API du service de génération est invalide ou expirée. "
            "Merci de réessayer plus tard."
        )
    if "Connection refused" in detail or "connect" in detail.lower():
        return (
            "Le service de génération est momentanément injoignable. "
            "Merci de réessayer dans quelques instants."
        )
    if "timeout" in detail.lower():
        return "La réponse a mis trop de temps à arriver. Merci de reformuler votre question."
    logger.error(f"Erreur lors du traitement de la question : {detail}", exc_info=True)
    return "Une erreur est survenue lors du traitement de votre question."


def _prepare_run(question: str, session_id: str):
    """Prépare l'état initial et la configuration d'un appel au graphe.

    Partagé par answer() et answer_stream() : les deux doivent envoyer exactement
    le même état au graphe, sans quoi les réponses différeraient selon le canal.
    """
    config = get_config()

    if len(question) > config.max_input_length:
        question = question[: config.max_input_length]

    run_config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": config.max_tool_iterations * 3 + 10,
    }

    try:
        user_preferences = _user_memory.get_user_preferences(session_id)
    except Exception:
        user_preferences = {}

    state = {
        "messages": [HumanMessage(content=question)],
        "question": question,
        "is_relevant": False,
        "context": "",
        "response": "",
        "need_clarification": False,
        "user_id": session_id,
        "user_preferences": user_preferences,
        "tool_iterations": 0,
        # routing_hint volontairement absent (BUG-14) : ce champ n'a pas de
        # réducteur Annotated dans AgentState, donc pour LangGraph toute clé
        # présente dans l'entrée d'invoke()/stream() écrase la valeur persistée
        # par le checkpointer, même à "" — avant même que route_and_store ne
        # s'exécute pour ce tour. route_and_store lit routing_hint du tour
        # précédent (mémoire d'un tour, tâche 20/BUG-10 cause 1) : l'omettre ici
        # laisse le checkpointer le restituer. Sans routing_hint persisté (tout
        # premier tour d'un thread_id), state.get("routing_hint") vaut None,
        # traité comme "pas agent" par route_and_store — sans risque.
        # routing_context et user_profile restent réinitialisés à chaque tour :
        # route_and_store les réécrit intégralement dans tous ses embranchements
        # (voir _result()), donc aucun code ne lit jamais leur valeur du tour
        # précédent avant que route_and_store ne les recalcule pour le tour en
        # cours — contrairement à routing_hint, les persister n'aurait aucun
        # effet observable aujourd'hui (mesuré, voir task-20-report.md).
        "routing_context": "",
        "user_profile": "",
    }
    return question, state, run_config


def _record(session_id: str, question: str, response_text: str, is_relevant, elapsed_ms: int):
    """Métriques et historique — best effort, ne doit jamais casser une réponse.

    `record_system_metrics()` a son propre bloc protégé, séparé de celui des
    deux appels préexistants (`record_question`, `add_conversation`) : une
    panne de la collecte système (base verrouillée, disque plein) ne doit
    pas faire sauter silencieusement l'enregistrement de l'historique de
    conversation, qui n'a rien à voir avec elle. Une protection dédiée est
    préférée à un simple déplacement en fin de bloc partagé : elle reste
    correcte même si un futur appel s'ajoute après elle, ce qu'un
    réordonnancement ne garantirait pas.
    """
    try:
        record_question(session_id, question, is_relevant, elapsed_ms)
        _user_memory.add_conversation(session_id, question, response_text)
    except Exception as exc:
        logger.warning(f"Enregistrement des métriques impossible : {exc}")

    try:
        record_system_metrics()
    except Exception as exc:
        logger.warning(f"Collecte des métriques système impossible : {exc}")


def answer(
    question: str,
    session_id: str,
    with_sources: bool = True,
) -> AnswerResult:
    """Pose une question à l'agent et retourne sa réponse.

    Args:
        question: question de l'utilisateur
        session_id: identifiant de conversation (thread_id LangGraph) — un UUID
            pour le web, "whatsapp:<numéro>" pour WhatsApp
        with_sources: joindre les extraits de documents utilisés

    Returns:
        AnswerResult(response, elapsed_ms, sources, error)
    """
    config = get_config()

    question = (question or "").strip()
    if not question:
        return AnswerResult(response="Merci de saisir une question.", elapsed_ms=0)

    agent = get_agent()
    start = time.perf_counter()
    question, state, run_config = _prepare_run(question, session_id)

    with _run_semaphore:
        try:
            set_session_user_id(session_id)
            result = agent.invoke(state, run_config)
        except Exception as exc:
            return AnswerResult(
                response=_humanize_error(exc),
                elapsed_ms=int((time.perf_counter() - start) * 1000),
                error=str(exc),
            )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response_text = _extract_response(result) or (
        "Je n'ai pas trouvé d'information sur ce point. "
        "Pouvez-vous reformuler votre question ?"
    )

    sources = (
        _collect_sources(question, config.vectorstore.similarity_search_k)
        if with_sources
        else []
    )

    _record(session_id, question, response_text, result.get("is_relevant", True), elapsed_ms)

    return AnswerResult(response=response_text, elapsed_ms=elapsed_ms, sources=sources)


# Libellés des étapes affichés pendant l'attente, par nœud du graphe
_LIBELLES_ETAPES = {
    "router": "analyse de la question…",
    "agent": "rédaction de la réponse…",
    "tools": "recherche dans les documents…",
    "handle_special_case": "préparation de la réponse…",
    "reject_query": "vérification du sujet…",
}


def answer_stream(question: str, session_id: str):
    """Version streamée d'`answer()` : génère des événements au fil de la réponse.

    Émet des dictionnaires :
      {"type": "etape",  "libelle": "recherche dans les documents…"}
      {"type": "token",  "texte": "fragment"}
      {"type": "fin",    "response": "...", "sources": [...], "elapsed_ms": 1234}
      {"type": "erreur", "message": "..."}

    Générateur **synchrone** : le graphe est bloquant, l'appelant doit l'itérer
    hors de la boucle d'événements (FastAPI le fait via son pool de threads).
    """
    config = get_config()

    question = (question or "").strip()
    if not question:
        yield {"type": "erreur", "message": "Merci de saisir une question."}
        return

    agent = get_agent()
    start = time.perf_counter()
    question, state, run_config = _prepare_run(question, session_id)

    morceaux: List[str] = []
    is_relevant = True

    with _run_semaphore:
        try:
            set_session_user_id(session_id)
            for mode, payload in agent.stream(
                state, run_config, stream_mode=["updates", "messages"]
            ):
                if mode == "updates":
                    for noeud, maj in (payload or {}).items():
                        libelle = _LIBELLES_ETAPES.get(noeud)
                        if libelle:
                            yield {"type": "etape", "libelle": libelle}
                        # Les nœuds sans LLM (reject_query, handle_special_case)
                        # posent directement leur texte : il ne passera pas en tokens.
                        if isinstance(maj, dict) and maj.get("response"):
                            morceaux.append(maj["response"])
                            is_relevant = maj.get("is_relevant", is_relevant)
                            yield {"type": "token", "texte": maj["response"]}

                elif mode == "messages":
                    chunk, meta = payload if isinstance(payload, tuple) else (payload, {})

                    # Ne diffuser que ce que le nœud « agent » rédige pour l'utilisateur.
                    # Sans ce filtre, les ToolMessage (résultats bruts de recherche
                    # documentaire) seraient envoyés tels quels au navigateur.
                    if (meta or {}).get("langgraph_node") != "agent":
                        continue
                    if not isinstance(chunk, (AIMessage, AIMessageChunk)):
                        continue
                    if getattr(chunk, "tool_calls", None) or getattr(
                        chunk, "tool_call_chunks", None
                    ):
                        continue

                    texte = chunk.content
                    if isinstance(texte, list):  # certains modèles renvoient des blocs
                        texte = "".join(
                            b.get("text", "") for b in texte if isinstance(b, dict)
                        )
                    if texte:
                        morceaux.append(texte)
                        yield {"type": "token", "texte": texte}

        except Exception as exc:
            logger.error(f"answer_stream — échec : {exc}", exc_info=True)
            yield {"type": "erreur", "message": _humanize_error(exc)}
            return

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response_text = "".join(morceaux).strip() or (
        "Je n'ai pas trouvé d'information sur ce point. "
        "Pouvez-vous reformuler votre question ?"
    )

    yield {
        "type": "fin",
        "response": response_text,
        "sources": _collect_sources(question, config.vectorstore.similarity_search_k),
        "elapsed_ms": elapsed_ms,
    }

    _record(session_id, question, response_text, is_relevant, elapsed_ms)

"""
Baseline RAG séquentielle : retrieve → generate, sans graphe LangGraph,
sans ReAct, sans outils spécialisés. Sert de point de comparaison pour
isoler la contribution du graphe d'états dans les métriques d'évaluation.
"""
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from logger_config import get_logger

logger = get_logger(__name__)


BASELINE_SYSTEM_PROMPT = """Tu es un assistant pour l'Université Abdou Moumouni
de Niamey (UAM). Réponds en 60 à 120 mots maximum, uniquement à partir du
contexte fourni ci-dessous.

Règles :
- Pas de salutation, pas de formule de courtoisie.
- Va directement à l'information demandée.
- Si l'information n'est pas dans le contexte, dis exactement :
  « Cette information précise n'apparaît pas dans ma base de connaissances.
   Contactez le service compétent pour la confirmer. »
- N'invente aucun détail.
"""


def run_baseline_query(
    question: str,
    vectorstore: Any,
    llm: Any,
    k: int = 4,
) -> Dict[str, Any]:
    """
    Exécute une requête en mode baseline RAG séquentielle.

    Returns:
        dict avec keys: response, retrieved_docs, is_relevant
    """
    try:
        docs = vectorstore.similarity_search(question, k=k)
        retrieved_docs = [d.page_content for d in docs]
    except Exception as e:
        logger.error(f"Erreur retrieval baseline : {e}")
        return {
            "response": "",
            "retrieved_docs": [],
            "is_relevant": False,
        }

    context = "\n\n---\n\n".join(retrieved_docs)
    prompt = (
        f"{BASELINE_SYSTEM_PROMPT}\n\n"
        f"CONTEXTE :\n{context}\n\n"
        f"QUESTION : {question}"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=question),
        ])
        return {
            "response": response.content,
            "retrieved_docs": retrieved_docs,
            "is_relevant": True,
        }
    except Exception as e:
        logger.error(f"Erreur génération baseline : {e}")
        return {
            "response": "",
            "retrieved_docs": retrieved_docs,
            "is_relevant": False,
        }

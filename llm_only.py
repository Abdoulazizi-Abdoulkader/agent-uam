"""
Approche LLM seul : génération directe sans retrieval ni outils.

Le LLM répond uniquement à partir de ses connaissances générales et d'un
prompt système décrivant l'UAM. Aucun document n'est récupéré.

Sert de baseline minimale pour quantifier la contribution du RAG :
  LLM seul → RAG séquentielle → Agent LangGraph (ReAct)
"""
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from logger_config import get_logger

logger = get_logger(__name__)


LLM_ONLY_SYSTEM_PROMPT = """Tu es un assistant virtuel de l'Université Abdou Moumouni
de Niamey (UAM), Niger. Tu réponds UNIQUEMENT aux questions concernant l'UAM :
inscriptions, formations, facultés, frais, contacts, procédures administratives.

Instructions :
1. Si la question concerne l'UAM, réponds en 60 à 120 mots, directement et
   sans formule de courtoisie.
2. Si tu ne disposes pas d'une information précise, dis-le clairement et suggère
   de contacter le service compétent.
3. Si la question est sans rapport avec l'UAM, commence ta réponse par
   "HORS_SUJET:" suivi d'une courte explication polie.
4. N'invente aucun chiffre, date ou procédure que tu n'es pas certain de connaître.
"""


def run_llm_only_query(
    question: str,
    llm: Any,
) -> Dict[str, Any]:
    """
    Exécute une requête en mode LLM seul (sans retrieval).

    Returns:
        dict avec keys: response, retrieved_docs (toujours []), is_relevant
    """
    try:
        response = llm.invoke([
            SystemMessage(content=LLM_ONLY_SYSTEM_PROMPT),
            HumanMessage(content=question),
        ])
        content: str = response.content if hasattr(response, "content") else str(response)
        is_relevant = not content.strip().startswith("HORS_SUJET:")
        return {
            "response": content,
            "retrieved_docs": [],
            "is_relevant": is_relevant,
        }
    except Exception as e:
        logger.error(f"Erreur génération LLM seul : {e}")
        return {
            "response": "",
            "retrieved_docs": [],
            "is_relevant": False,
        }

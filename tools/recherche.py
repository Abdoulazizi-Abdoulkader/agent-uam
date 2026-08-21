"""Recherche sémantique généraliste dans la base de connaissances UAM."""
import unicodedata

from langchain_core.tools import tool

from app_config import get_config
from context_tracker import push_context
from logger_config import get_logger
from uam_structures import detect_structure_in_text
from utils import sanitize_input, retry_on_failure

from ._rag import _GROUNDING_AVAILABLE, _gc
from ._vectorstore import _cached_similarity_search, get_vectorstore

logger = get_logger(__name__)


def _normalize_query(query: str) -> str:
    """Normalise une requête pour le cache (minuscules, sans accents superflus, strip)."""
    nfkd = unicodedata.normalize("NFKD", query.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@tool
@retry_on_failure(max_retries=2, delay=0.5, exceptions=(IOError, OSError, TimeoutError))
def search_uam_knowledge(query: str) -> str:
    """
    Recherche des informations dans la base de connaissances de l'UAM.
    Comprend automatiquement les abréviations (ex: FAST, FLSH, ENS, etc.).
    
    Args:
        query: La question ou le terme à rechercher dans les documents UAM.
               Peut contenir des abréviations comme FAST, FLSH, ENS, etc.
        
    Returns:
        Le contexte pertinent trouvé dans les documents
    """
    try:
        # Valider et nettoyer l'entrée
        config = get_config()
        max_length = min(500, config.max_input_length)
        query = sanitize_input(query, max_length=max_length)
        
        if get_vectorstore() is None:
            logger.error("Base de connaissances non initialisée")
            return "Erreur: Base de connaissances non initialisée"
        
        logger.debug(f"Recherche dans la base de connaissances: {query[:100]}...")
        
        # Détecter et remplacer les abréviations par leurs noms complets pour améliorer la recherche
        query_expanded = query
        detected_structures = detect_structure_in_text(query)
        
        if detected_structures:
            # Ajouter les noms complets des structures détectées à la requête
            structure_names = [s["nom_complet"] for s in detected_structures]
            query_expanded = f"{query} {' '.join(structure_names)}"
            logger.debug(f"Structures détectées: {[s['abreviation'] for s in detected_structures]}")
        
        # Recherche sémantique — cache LRU en production, bypass en mode grounding
        query_key = _normalize_query(query_expanded)
        k = config.vectorstore.similarity_search_k
        if _GROUNDING_AVAILABLE and _gc.is_enabled():
            docs_scores = get_vectorstore().similarity_search_with_score(query_key, k=k)
            _gc.log_retrieval(query_key, docs_scores)
            page_contents = tuple(doc.page_content for doc, _ in docs_scores)
        else:
            page_contents = _cached_similarity_search(query_key, k)
        push_context(list(page_contents))

        if not page_contents:
            logger.warning(f"Aucun document trouvé pour la requête: {query[:100]}")
            return "Aucune information trouvée pour cette requête."

        # Combiner les documents
        context = "\n\n---\n\n".join(page_contents)
        
        logger.debug(f"Trouvé {len(page_contents)} document(s) pertinents")
        return context
        
    except ValueError as e:
        logger.error(f"Erreur de validation dans search_uam_knowledge: {e}")
        return f"Erreur: {str(e)}"
    except Exception as e:
        logger.error(f"Erreur inattendue dans search_uam_knowledge: {e}", exc_info=True)
        return "Une erreur s'est produite lors de la recherche. Veuillez réessayer."

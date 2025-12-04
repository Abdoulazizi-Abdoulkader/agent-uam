# Charger les variables d'environnement dès le début
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv n'est pas installé, utiliser les variables d'environnement système

# Import ToolNode avec fallback si non disponible
try:
    from langgraph.prebuilt import ToolNode
except ImportError:
    # Créer une implémentation alternative de ToolNode
    from langchain_core.messages import ToolMessage

    class ToolNode:
        """Implémentation alternative de ToolNode pour exécuter les outils"""
        def __init__(self, tools):
            # Créer un dictionnaire des outils par nom
            self.tools = {}
            for tool in tools:
                if hasattr(tool, 'name'):
                    self.tools[tool.name] = tool
                elif hasattr(tool, '__name__'):
                    self.tools[tool.__name__] = tool

        def invoke(self, state):
            """Exécute les appels d'outils depuis les messages"""
            messages = state.get("messages", [])
            if not messages:
                return {"messages": []}

            last_message = messages[-1]
            tool_messages = []

            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    # Gérer différents formats de tool_call
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        tool_call_id = tool_call.get("id", "")
                    else:
                        # Format objet
                        tool_name = getattr(tool_call, "name", "")
                        tool_args = getattr(tool_call, "args", {})
                        tool_call_id = getattr(tool_call, "id", "")

                    if tool_name in self.tools:
                        try:
                            result = self.tools[tool_name].invoke(tool_args)
                            tool_messages.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call_id
                                )
                            )
                        except Exception as e:
                            tool_messages.append(
                                ToolMessage(
                                    content=f"Erreur lors de l'exécution de {tool_name}: {e}",
                                    tool_call_id=tool_call_id
                                )
                            )

            return {"messages": tool_messages}

        def __call__(self, state):
            """Permet d'utiliser ToolNode comme une fonction"""
            return self.invoke(state)

# Imports depuis les modules refactorisés
from config import LLMProvider
from llm_utils import initialize_llm, initialize_embeddings
from uam_structures import (
    UAM_STRUCTURES,
    get_structure_info,
    detect_structure_in_text,
    list_all_structures_internal
)
from document_loader import load_and_index_documents
from memory import UserMemory, _user_memory
from agent_state import AgentState
from tools import (
    set_vectorstore,
    get_tools,
    search_uam_knowledge,
    detect_greeting,
    check_question_relevance,
    calculate_fees,
    search_formations,
    get_faculty_info,
    get_structure_by_abbreviation,
    list_all_structures,
    save_user_preference,
    get_user_preferences,
    search_prerequisites,
    search_competences_requises,
    search_cycles_et_duree,
    search_chronogramme,
    search_coefficients,
    search_professeurs,
    search_debouches,
    search_reglement_interieur,
    search_organisation_corps_professoral,
    search_organisation_corps_estudiantin,
    search_reclamations,
    search_avantages_universite,
    search_latest_news,
    get_schedules_from_db
)
# Importer _vectorstore depuis tools pour compatibilité avec multi_agents.py
# Créer une référence initiale qui sera mise à jour par set_vectorstore
import tools
_vectorstore = tools._vectorstore
from graph_nodes import (
    route_question,
    search_knowledge,
    should_continue,
    call_model,
    generate_response,
    reject_query
)
from agent_graph import create_agent_graph
from chatbot import run_chatbot

# Réexporter ToolNode pour compatibilité
__all__ = [
    # Configuration
    "LLMProvider",
    "ToolNode",
    
    # LLM et embeddings
    "initialize_llm",
    "initialize_embeddings",
    
    # Structures UAM
    "UAM_STRUCTURES",
    "get_structure_info",
    "detect_structure_in_text",
    "list_all_structures_internal",
    
    # Documents
    "load_and_index_documents",
    
    # Mémoire
    "UserMemory",
    "_user_memory",
    
    # État
    "AgentState",
    
    # Outils
    "set_vectorstore",
    "_vectorstore",
    "get_tools",
    "search_uam_knowledge",
    "detect_greeting",
    "check_question_relevance",
    "calculate_fees",
    "search_formations",
    "get_faculty_info",
    "get_structure_by_abbreviation",
    "list_all_structures",
    "save_user_preference",
    "get_user_preferences",
    "search_prerequisites",
    "search_competences_requises",
    "search_cycles_et_duree",
    "search_chronogramme",
    "search_coefficients",
    "search_professeurs",
    "search_debouches",
    "search_reglement_interieur",
    "search_organisation_corps_professoral",
    "search_organisation_corps_estudiantin",
    "search_reclamations",
    "search_avantages_universite",
    "search_latest_news",
    "get_schedules_from_db",
    
    # Nœuds du graphe
    "route_question",
    "search_knowledge",
    "should_continue",
    "call_model",
    "generate_response",
    "reject_query",
    
    # Graphe
    "create_agent_graph",
    
    # Interface utilisateur
    "run_chatbot",
]

# Point d'entrée pour compatibilité avec le script original
if __name__ == "__main__":
    import os
    from pathlib import Path
    
    # Charger les variables d'environnement depuis .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(" Variables d'environnement chargées depuis .env")
    except ImportError:
        print("  python-dotenv non installé. Utilisez: pip install python-dotenv")
        print("   Ou définissez GROQ_API_KEY manuellement")
    
    print()
    
    # CONFIGURATION
    PDF_DIRECTORY = "./documents_uam"
    
    # Configuration pour Groq (Llama) - RECOMMANDÉ
    PROVIDER = LLMProvider.LLAMA_GROQ
    MODEL_NAME = "llama-3.3-70b-versatile"
    
    # Vérifier que le dossier existe
    if not os.path.exists(PDF_DIRECTORY):
        print(f" Erreur: Le dossier '{PDF_DIRECTORY}' n'existe pas.")
        print()
        print("Solutions :")
        print(f"  1. Créez le dossier : mkdir {PDF_DIRECTORY}")
        print(f"  2. Créez des documents d'exemple : python create_sample_docs.py")
        print(f"  3. Ajoutez vos propres documents PDF/TXT dans {PDF_DIRECTORY}/")
        print()
    else:
        # Vérifier s'il y a des documents
        docs_path = Path(PDF_DIRECTORY)
        doc_count = len(list(docs_path.glob("**/*.pdf"))) + len(list(docs_path.glob("**/*.txt")))
        
        if doc_count == 0:
            print(f"  Le dossier '{PDF_DIRECTORY}' est vide.")
            print()
            print("Pour créer des documents d'exemple :")
            print("  python create_sample_docs.py")
            print()
        else:
            run_chatbot(PDF_DIRECTORY, PROVIDER, MODEL_NAME)

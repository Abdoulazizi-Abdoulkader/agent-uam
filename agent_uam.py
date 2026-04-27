# Charger les variables d'environnement dès le début
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv n'est pas installé, utiliser les variables d'environnement système

from tool_node import ToolNode

# Imports depuis les modules refactorisés
from app_config import LLMProvider
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
    detect_user_profile,
    detect_frustration_or_confusion,
    get_agent_capabilities,
    check_question_relevance,
    calculate_fees,
    search_formations,
    search_admission_requirements,
    search_required_documents,
    search_registration_procedure,
    search_registration_calendar,
    search_student_card,
    search_transfer_equivalence,
    search_housing_and_services,
    search_scholarships,
    search_contacts_services,
    search_international_equivalence,
    search_late_reenrollment,
    search_internship_info,
    search_double_degree,
    generate_registration_checklist,
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
    search_external_student_master,
    search_phd_admission,
    search_foreign_student_procedures,
    search_recognition_prior_learning,
    search_master_thesis_supervision,
    search_academic_partnership,
    search_latest_news,
    get_schedules_from_db,
)
from graph_nodes import (
    route_and_store,
    search_knowledge,
    should_continue,
    call_model,
    generate_response,
    reject_query,
    handle_special_case,
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
    
    # Outils de détection conversationnelle
    "detect_greeting",
    "detect_user_profile",
    "detect_frustration_or_confusion",
    "get_agent_capabilities",
    "check_question_relevance",

    # Outils principaux
    "set_vectorstore",
    "get_tools",
    "search_uam_knowledge",
    "get_faculty_info",
    "get_structure_by_abbreviation",
    "list_all_structures",

    # Formations et filières
    "search_formations",
    "search_prerequisites",
    "search_competences_requises",
    "search_cycles_et_duree",
    "search_chronogramme",
    "search_coefficients",
    "search_debouches",
    "search_avantages_universite",

    # Inscription / admission
    "calculate_fees",
    "search_admission_requirements",
    "search_required_documents",
    "search_registration_procedure",
    "search_registration_calendar",
    "search_student_card",
    "search_transfer_equivalence",
    "search_international_equivalence",
    "search_late_reenrollment",
    "search_internship_info",
    "search_double_degree",
    "generate_registration_checklist",

    # Étudiants externes / étrangers / master / doctorat
    "search_external_student_master",
    "search_phd_admission",
    "search_foreign_student_procedures",
    "search_recognition_prior_learning",
    "search_master_thesis_supervision",
    "search_academic_partnership",

    # Services et contacts
    "search_housing_and_services",
    "search_scholarships",
    "search_contacts_services",
    "search_reclamations",

    # Corps universitaire
    "search_professeurs",
    "search_organisation_corps_professoral",
    "search_organisation_corps_estudiantin",
    "search_reglement_interieur",

    # Mémoire utilisateur
    "save_user_preference",
    "get_user_preferences",

    # Base de données
    "search_latest_news",
    "get_schedules_from_db",

    # Nœuds du graphe
    "route_and_store",
    "search_knowledge",
    "should_continue",
    "call_model",
    "generate_response",
    "reject_query",
    "handle_special_case",
    
    # Graphe
    "create_agent_graph",
    
    # Interface utilisateur
    "run_chatbot",
]

# Point d'entrée pour compatibilité avec le script original
if __name__ == "__main__":
    import os
    from pathlib import Path

    # .env déjà chargé au début du module — pas besoin de recharger ici
    print()
    
    # CONFIGURATION
    PDF_DIRECTORY = "./documents_uam"

    PROVIDER = LLMProvider.OPENROUTER
    MODEL_NAME = os.getenv("UAM_LLM_MODEL", "openai/gpt-4o-mini")
    
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

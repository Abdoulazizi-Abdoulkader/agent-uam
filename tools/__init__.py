"""Outils exposés au LLM, regroupés par domaine.

L'API publique est identique à celle de l'ancien module tools.py : les modules
appelants continuent d'écrire `from tools import get_tools, set_vectorstore`.
"""
from langsmith import traceable

# ── Ordre d'import : historiquement non commutable, désormais indifférent
# (BUG-08, corrigé tâche 12) ───────────────────────────────────────────────
# memory.py appelle get_config() au niveau module, ce qui mémoïse la
# configuration pour tout le process ; database_connector chargeait .env à
# l'import, seul module à le faire. L'ancien tools.py importait memory
# (ligne 28) avant database_connector (ligne 92), donc `preferences` (qui
# importe memory) restait devant `_db` ici pour la même raison : importer
# `_db` en premier aurait avancé load_dotenv() avant le gel de la
# configuration et fait basculer `_db_available` de False à True dans un
# process qui n'avait pas chargé .env lui-même — c'était le cas de la suite
# pytest. Depuis la correction de BUG-08, `app_config.get_config()` charge
# .env lui-même (au tout premier appel, quel qu'il soit) : l'ordre de ces
# deux imports n'a donc plus d'effet sur `_db_available`. Il n'est pas
# réordonné pour autant — aucun bénéfice à le faire, et un réordonnancement
# non motivé serait un changement gratuit dans un fichier déjà revu ligne à
# ligne (tâche 11).
from .preferences import get_user_preferences, save_user_preference
from ._db import _db_available

from ._rag import _rag_response
from ._session import set_session_user_id
# La *valeur* `_vectorstore` n'est délibérément pas réexportée : le nom de la
# variable et celui du sous-module sont identiques, et `from ._vectorstore
# import _vectorstore` remplacerait ici la référence au sous-module par None,
# rendant inopérant tout patch visant l'état réel.
from ._vectorstore import get_vectorstore, set_vectorstore

from .base_donnees import (
    get_schedules_from_db, search_latest_news, search_statistics_uam,
    search_student_record,
)
from .conversation import (
    _sans_accents, check_question_relevance, detect_frustration_or_confusion,
    detect_greeting, detect_user_profile, get_agent_capabilities,
)
from .parcours import (
    search_academic_partnership, search_external_student_master,
    search_foreign_student_procedures, search_master_thesis_supervision,
    search_phd_admission, search_recognition_prior_learning,
)
from .programmes import (
    search_avantages_universite, search_chronogramme, search_coefficients,
    search_competences_requises, search_cycles_et_duree, search_debouches,
    search_organisation_corps_estudiantin, search_organisation_corps_professoral,
    search_prerequisites, search_professeurs, search_reclamations,
    search_reglement_interieur,
)
from .recherche import search_uam_knowledge
from .scolarite import (
    calculate_fees, generate_registration_checklist,
    search_admission_requirements, search_contacts_services, search_double_degree,
    search_formations, search_housing_and_services, search_international_equivalence,
    search_internship_info, search_late_reenrollment, search_registration_calendar,
    search_registration_procedure, search_required_documents, search_scholarships,
    search_student_card, search_transfer_equivalence,
)
from .structures import (
    get_faculty_info, get_structure_by_abbreviation, list_all_structures,
)


@traceable
def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    tools = [
        # Détection et profiling conversationnel
        detect_greeting,
        detect_user_profile,
        detect_frustration_or_confusion,
        get_agent_capabilities,
        check_question_relevance,

        # Recherche générale
        search_uam_knowledge,
        get_faculty_info,
        get_structure_by_abbreviation,
        list_all_structures,

        # Formations et filières
        search_formations,
        search_prerequisites,
        search_competences_requises,
        search_cycles_et_duree,
        search_chronogramme,
        search_coefficients,
        search_debouches,
        search_avantages_universite,

        # Admission et inscription
        search_admission_requirements,
        search_required_documents,
        search_registration_procedure,
        search_registration_calendar,
        search_late_reenrollment,
        generate_registration_checklist,
        calculate_fees,

        # Étudiants externes / étrangers / master / doctorat
        search_external_student_master,
        search_phd_admission,
        search_foreign_student_procedures,
        search_recognition_prior_learning,
        search_master_thesis_supervision,
        search_academic_partnership,
        search_international_equivalence,
        search_transfer_equivalence,

        # Documents et démarches
        search_student_card,
        search_internship_info,
        search_double_degree,
        search_reclamations,

        # Services et vie étudiante
        search_housing_and_services,
        search_scholarships,
        search_contacts_services,

        # Corps universitaire
        search_professeurs,
        search_organisation_corps_professoral,
        search_organisation_corps_estudiantin,
        search_reglement_interieur,

        # Mémoire utilisateur
        save_user_preference,
        get_user_preferences,
    ]

    # Ajouter les outils de base de données si disponible
    if _db_available:
        tools.extend([
            search_latest_news,
            get_schedules_from_db,
            search_student_record,
            search_statistics_uam,
        ])
    
    return tools

# tests/test_inventaire_outils.py
"""Inventaire des outils exposés au LLM.

Ce test est le garde-fou du découpage de tools.py en package : il doit passer
à l'identique avant et après, sans qu'une seule ligne en soit modifiée.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

NOMS_OUTILS_INCONDITIONNELS = frozenset({
    "detect_greeting", "detect_user_profile", "detect_frustration_or_confusion",
    "get_agent_capabilities", "check_question_relevance",
    "search_uam_knowledge", "get_faculty_info", "get_structure_by_abbreviation",
    "list_all_structures",
    "search_formations", "search_prerequisites", "search_competences_requises",
    "search_cycles_et_duree", "search_chronogramme", "search_coefficients",
    "search_debouches", "search_avantages_universite",
    "search_admission_requirements", "search_required_documents",
    "search_registration_procedure", "search_registration_calendar",
    "search_late_reenrollment", "generate_registration_checklist", "calculate_fees",
    "search_external_student_master", "search_phd_admission",
    "search_foreign_student_procedures", "search_recognition_prior_learning",
    "search_master_thesis_supervision", "search_academic_partnership",
    "search_international_equivalence", "search_transfer_equivalence",
    "search_student_card", "search_internship_info", "search_double_degree",
    "search_reclamations",
    "search_housing_and_services", "search_scholarships", "search_contacts_services",
    "search_professeurs", "search_organisation_corps_professoral",
    "search_organisation_corps_estudiantin", "search_reglement_interieur",
    "save_user_preference", "get_user_preferences",
})

NOMS_OUTILS_BASE = frozenset({
    "search_latest_news", "get_schedules_from_db",
    "search_student_record", "search_statistics_uam",
})


class TestInventaireOutils:

    def test_quarante_cinq_outils_inconditionnels(self):
        assert len(NOMS_OUTILS_INCONDITIONNELS) == 45

    def test_quatre_outils_conditionnels(self):
        assert len(NOMS_OUTILS_BASE) == 4

    def test_aucun_chevauchement_entre_les_deux_groupes(self):
        assert not (NOMS_OUTILS_INCONDITIONNELS & NOMS_OUTILS_BASE)

    def test_tous_les_outils_exposes_quand_la_base_est_disponible(self):
        import tools
        with patch.object(tools, "_db_available", True):
            noms = {t.name for t in tools.get_tools()}
        assert noms == NOMS_OUTILS_INCONDITIONNELS | NOMS_OUTILS_BASE
        assert len(noms) == 49

    def test_seuls_les_inconditionnels_quand_la_base_est_absente(self):
        import tools
        with patch.object(tools, "_db_available", False):
            noms = {t.name for t in tools.get_tools()}
        assert noms == NOMS_OUTILS_INCONDITIONNELS
        assert len(noms) == 45

    def test_aucun_doublon_dans_la_liste(self):
        import tools
        with patch.object(tools, "_db_available", True):
            noms = [t.name for t in tools.get_tools()]
        assert len(noms) == len(set(noms))

    def test_chaque_outil_a_une_description_non_vide(self):
        import tools
        with patch.object(tools, "_db_available", True):
            for t in tools.get_tools():
                assert t.description and t.description.strip(), f"{t.name} sans description"

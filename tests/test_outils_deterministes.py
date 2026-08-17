"""Caractérisation des outils sans dépendance externe.

Ces tests figent le comportement ACTUEL, pas le comportement idéal. Un
comportement jugé fautif ne figure pas ici : il part dans la liste des bugs
(docs/superpowers/audit/2026-08-16-audit.md, section 5).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDetectGreeting:

    @pytest.mark.parametrize("message,attendu", [
        ("Bonjour", "GREETING"),
        ("Salut", "GREETING"),
        ("Au revoir", "FAREWELL"),
        ("Merci beaucoup", "THANKS"),
    ])
    def test_categories_principales(self, message, attendu):
        from tools import detect_greeting
        assert detect_greeting.func(message=message) == attendu

    def test_question_sans_salutation(self):
        from tools import detect_greeting
        resultat = detect_greeting.func(message="Quels sont les frais d'inscription ?")
        assert resultat not in ("GREETING", "FAREWELL", "THANKS")


class TestDetectUserProfile:

    @pytest.mark.parametrize("message,attendu", [
        ("Je viens d'une autre université et je veux faire un master", "CANDIDAT_MASTER"),
        ("Je souhaite faire une thèse de doctorat", "CANDIDAT_DOCTORAT"),
    ])
    def test_profils_speciaux(self, message, attendu):
        from tools import detect_user_profile
        assert detect_user_profile.func(message=message) == attendu

    def test_message_neutre_donne_inconnu(self):
        from tools import detect_user_profile
        assert detect_user_profile.func(message="Bonjour") == "INCONNU"


class TestCheckQuestionRelevance:

    def test_question_uam_pertinente(self):
        from tools import check_question_relevance
        assert check_question_relevance.func(
            question="Quels sont les frais d'inscription en licence à l'UAM ?"
        ) == "PERTINENT"

    def test_question_hors_sujet(self):
        from tools import check_question_relevance
        assert check_question_relevance.func(
            question="Quelle est la recette du couscous ?"
        ) == "HORS_SUJET"


class TestStructures:

    def test_abreviation_connue(self):
        from tools import get_structure_by_abbreviation
        resultat = get_structure_by_abbreviation.func(abbreviation="FAST")
        assert "FAST" in resultat or "Sciences" in resultat

    def test_abreviation_inconnue_ne_leve_pas(self):
        from tools import get_structure_by_abbreviation
        resultat = get_structure_by_abbreviation.func(abbreviation="ZZZZ")
        assert isinstance(resultat, str) and resultat

    def test_liste_des_structures_non_vide(self):
        from tools import list_all_structures
        resultat = list_all_structures.func()
        assert "FAST" in resultat

    def test_info_faculte(self):
        from tools import get_faculty_info
        resultat = get_faculty_info.func(faculty_name="FAST")
        assert isinstance(resultat, str) and len(resultat) > 20


class TestCalculateFees:

    def test_licence_retourne_un_montant(self):
        from tools import calculate_fees
        resultat = calculate_fees.func(level="licence")
        assert isinstance(resultat, str) and resultat.strip()

    def test_niveau_inconnu_ne_leve_pas(self):
        from tools import calculate_fees
        resultat = calculate_fees.func(level="niveau_inexistant")
        assert isinstance(resultat, str) and resultat.strip()

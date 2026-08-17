"""BUG-05 : les questions tapées sans accents sont rejetées.

Les mots-clés de keywords_uam sont accentués et la comparaison est littérale.
La saisie sans accents est courante sur téléphone et clavier QWERTY.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PAIRES = [
    ("Comment se réinscrire ?", "Comment se reinscrire ?"),
    ("Quelles sont les filières ?", "Quelles sont les filieres ?"),
    ("Où est la faculté ?", "Ou est la faculte ?"),
    ("Quel diplôme obtient-on ?", "Quel diplome obtient-on ?"),
    ("Comment obtenir mon relevé de notes ?", "Comment obtenir mon releve de notes ?"),
    ("Quelle est la procédure de préinscription ?", "Quelle est la procedure de preinscription ?"),
    ("Y a-t-il une cité universitaire ?", "Y a-t-il une cite universitaire ?"),
]


class TestInsensibiliteAuxAccents:

    @pytest.mark.parametrize("avec,sans", PAIRES)
    def test_les_deux_formes_sont_classees_pareil(self, avec, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == \
               check_question_relevance.func(question=avec)

    @pytest.mark.parametrize("_,sans", PAIRES)
    def test_la_forme_sans_accents_est_pertinente(self, _, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == "PERTINENT"


class TestPasDeRegression:
    """La normalisation ne doit pas rouvrir les faux positifs de BUG-03 et BUG-04."""

    @pytest.mark.parametrize("question", [
        "Il fait frais ce matin",
        "Comment faire une omelette ?",
        "Ma famille habite à Zinder",
        "Je pense que c'est une bonne idée",
        "Le facteur est passé",
        "Quelle est la recette du couscous ?",
    ])
    def test_les_phrases_hors_sujet_le_restent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        "Que propose la FA ?",
        "Comment intégrer l'ENS ?",
        "Quels sont les frais ?",
        "Quelles filières à la FAST ?",
    ])
    def test_les_acquis_des_taches_precedentes_tiennent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestHelperSansAccents:

    @pytest.mark.parametrize("entree,attendu", [
        ("réinscrire", "reinscrire"),
        ("filière", "filiere"),
        ("diplôme", "diplome"),
        ("où", "ou"),
        ("cité universitaire", "cite universitaire"),
        ("sans accent", "sans accent"),
        ("", ""),
    ])
    def test_normalisation(self, entree, attendu):
        from tools import _sans_accents
        assert _sans_accents(entree) == attendu

    def test_la_casse_n_est_pas_modifiee(self):
        """Le helper normalise les accents, pas la casse : les deux
        responsabilités restent séparées."""
        from tools import _sans_accents
        assert _sans_accents("FACULTÉ") == "FACULTE"


class TestRoutage:

    @pytest.mark.parametrize("question", [
        "Ou est la faculte ?",
        "Comment se reinscrire ?",
        "Quelles sont les filieres ?",
    ])
    def test_les_questions_sans_accents_atteignent_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"

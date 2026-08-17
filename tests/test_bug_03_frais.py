# tests/test_bug_03_frais.py
"""BUG-03 : les questions sur les frais sont rejetées comme hors sujet.

Seule la phrase exacte « frais d'inscription » était reconnue. Les formulations
naturelles — « quels sont les frais ? », « le montant des frais » — partaient en
reject_query, et l'agent répondait qu'il ne traite que les questions UAM.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestQuestionsSurLesFrais:
    """Les formulations naturelles doivent être reconnues comme pertinentes."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais ?",
        "Quel est le montant des frais ?",
        "Je veux connaitre les frais",
        "Les frais sont de combien ?",
        "Combien coûtent les frais ?",
        "Quels sont les frais de scolarité ?",
        "Je voudrais connaître les frais universitaires",
    ])
    def test_formulations_naturelles_sont_pertinentes(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"

    @pytest.mark.parametrize("question", [
        "Quels sont les frais d'inscription ?",
        "Combien coûte une inscription ?",
    ])
    def test_les_formulations_deja_reconnues_le_restent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestPasDeFauxPositifs:
    """« frais » est aussi un adjectif : ces phrases ne parlent pas de l'UAM."""

    @pytest.mark.parametrize("question", [
        "Il fait frais ce matin",
        "J'aime les produits frais du marché",
        "Où trouver du poisson frais à Niamey ?",
    ])
    def test_adjectif_frais_reste_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestBug04AbreviationsEnMotEntier:
    """« fa » et « ens » ne doivent plus matcher à l'intérieur d'un mot."""

    @pytest.mark.parametrize("question", [
        "Il fait beau aujourd'hui",
        "Je suis fatigué",
        "Comment fabriquer du savon ?",
        "Le facteur est passé",
        "Ma famille habite à Zinder",
        "Comment faire une omelette ?",
        "Je pense que c'est une bonne idée",
        "Je voudrais un renseignement",
    ])
    def test_mots_contenant_fa_ou_ens_restent_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        "Que propose la FA ?",
        "Quelles filières à la FAST ?",
        "Comment intégrer l'ENS ?",
        "Je veux m'inscrire à l'UAM",
        "Quelles formations à l'IRI ?",
    ])
    def test_les_abreviations_restent_reconnues(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestRoutageDeBoutEnBout:
    """Le routage est ce que l'utilisateur subit réellement."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais ?",
        "Quel est le montant des frais ?",
        "Je veux connaitre les frais",
    ])
    def test_les_questions_sur_les_frais_atteignent_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"

    def test_une_question_hors_sujet_reste_rejetee(self):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content="Il fait frais ce matin")]})
        assert resultat["routing_hint"] == "reject_query"

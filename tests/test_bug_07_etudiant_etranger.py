# tests/test_bug_07_etudiant_etranger.py
"""BUG-07 : un candidat qui se décrit comme venant d'une université étrangère
part en reject_query au lieu d'être traité par l'agent.

`_OFF_TOPIC_RE` (tools/conversation.py) porte un motif conçu pour rejeter les
questions dont une université étrangère est le *sujet* (ex. « Quels sont les
frais à l'université française ? »). Il est vérifié en tout premier dans
`check_question_relevance` et collisionne avec la tournure où le candidat se
décrit lui-même comme venant d'une université étrangère pour demander à
s'inscrire à l'UAM — exactement le cas que le profil `ETUDIANT_ETRANGER` est
censé absorber dans `route_and_store`.

Manifestation consignée dans docs/superpowers/audit/2026-08-16-audit.md,
section 5 (table) et « Reproductions détaillées ».
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCandidatEtrangerRedevientPertinent:
    """Un candidat qui se décrit lui-même comme venant d'une université
    étrangère doit être classé PERTINENT, pas HORS_SUJET."""

    @pytest.mark.parametrize("question", [
        "Je suis étudiant d'une université étrangère, comment m'inscrire à l'UAM ?",
        "Je viens d'une université étrangère et je veux m'inscrire",
        "Mon diplôme vient d'une université étrangère, est-il reconnu ?",
    ])
    def test_formulations_de_l_audit_sont_pertinentes(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestNonRegressionUniversiteEtrangereCommeSujet:
    """`_OFF_TOPIC_RE` protège légitimement les questions où une université
    étrangère est le *sujet*, sans rapport avec l'origine du locuteur — ce
    motif ne doit pas être desserré."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais à l'université française ?",
        "Quels sont les frais à l'université européenne ?",
        "Quels sont les frais à l'université canadienne ?",
        "Quels sont les frais à l'université américaine ?",
    ])
    def test_universite_etrangere_comme_sujet_reste_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    def test_mention_generique_sans_auto_description_reste_hors_sujet(self):
        """Sans marqueur de première personne (« je suis », « je viens »,
        « mon diplôme »), une simple mention d'université étrangère reste
        hors sujet — le correctif ne doit pas desserrer au-delà du cas
        décrit par l'audit."""
        from tools import check_question_relevance
        question = "Comment fonctionne une université étrangère typique ?"
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestRoutageDeBoutEnBout:
    """Le routage est ce que l'utilisateur subit réellement : route_and_store
    doit envoyer ces messages vers l'agent, pas vers reject_query."""

    @pytest.mark.parametrize("question", [
        "Je suis étudiant d'une université étrangère, comment m'inscrire à l'UAM ?",
        "Je viens d'une université étrangère et je veux m'inscrire",
    ])
    def test_candidat_etranger_atteint_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"
        assert resultat["user_profile"] == "ETUDIANT_ETRANGER"

    def test_question_hors_sujet_sur_universite_etrangere_reste_rejetee(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(
            {"messages": [HumanMessage(content="Quels sont les frais à l'université française ?")]}
        )
        assert resultat["routing_hint"] == "reject_query"

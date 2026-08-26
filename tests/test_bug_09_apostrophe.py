# tests/test_bug_09_apostrophe.py
"""BUG-09 : apostrophe typographique (U+2019) non reconnue par les motifs
ASCII de tools/conversation.py.

Les ~24 motifs répartis sur les 4 fonctions de routage (`detect_greeting`,
`check_question_relevance`, `detect_user_profile`,
`detect_frustration_or_confusion`) sont écrits avec la classe de caractères
`[''']`/`['']`, qui ne contient que l'apostrophe droite ASCII (U+0027,
dupliquée sans variante). Les claviers iOS et Android insèrent par
autocorrection l'apostrophe typographique (`’`, U+2019) : la même phrase,
tapée sur mobile, ne matche plus aucun de ces motifs alors que les deux
caractères ne se distinguent qu'à l'œil.

Cas le plus grave, mesuré en tâche 12 (task-12-report.md, section BUG-09) :
le garde-fou `_SELF_ETUDIANT_ETRANGER_RE`, ajouté pour corriger BUG-07,
est lui-même vulnérable — la version mobile de la phrase retombe dans
`_OFF_TOPIC_RE` et réintroduit BUG-07, sans qu'aucun rattrapage par
`\buam\b` ne soit atteint (le court-circuit de `_OFF_TOPIC_RE` intervient
avant). Les messages courts d'adieu, de remerciement, de confusion et de
répétition basculent en `reject_query` sans aucun rattrapage possible.

Reproductions consignées dans docs/superpowers/audit/2026-08-16-audit.md,
section 5 (table, entrée BUG-09) et « Reproductions détaillées ».
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

APOSTROPHE_TYPOGRAPHIQUE = "’"  # '


class TestCheckQuestionRelevanceReintroductionBug07:
    """Le marqueur ajouté pour BUG-07 (`_SELF_ETUDIANT_ETRANGER_RE`) ne
    matchait que l'apostrophe droite ASCII : une phrase tapée sur mobile
    avec l'apostrophe typographique retombait dans `_OFF_TOPIC_RE` et
    réintroduisait BUG-07 (task-12-report.md, section BUG-09). Phrase
    reprise telle quelle depuis la mesure de la tâche 12."""

    QUESTION_DROITE = "J'étudie dans une université étrangère, comment transférer à l'UAM ?"
    QUESTION_TYPOGRAPHIQUE = "J’étudie dans une université étrangère, comment transférer à l’UAM ?"

    def test_apostrophe_droite_est_deja_pertinente(self):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=self.QUESTION_DROITE) == "PERTINENT"

    def test_apostrophe_typographique_devient_pertinente(self):
        """C'est la réintroduction de BUG-07 mesurée en tâche 12 : avant
        correctif, cette phrase retombait en HORS_SUJET."""
        from tools import check_question_relevance
        assert check_question_relevance.func(question=self.QUESTION_TYPOGRAPHIQUE) == "PERTINENT"


class TestDetectGreetingApostropheTypographique:
    """« C'est bon » (FAREWELL) doit être reconnu quelle que soit
    l'apostrophe — phrase reprise de la mesure de la tâche 12."""

    def test_apostrophe_droite_est_deja_farewell(self):
        from tools import detect_greeting
        assert detect_greeting.func(message="C'est bon") == "FAREWELL"

    def test_apostrophe_typographique_devient_farewell(self):
        from tools import detect_greeting
        assert detect_greeting.func(message="C’est bon") == "FAREWELL"


class TestDetectUserProfileApostropheTypographique:
    """`detect_user_profile` bascule de `ETUDIANT_ETRANGER` à `INCONNU`
    avec l'apostrophe typographique (mesure de la tâche 12)."""

    QUESTION_DROITE = "Je suis d'Espagne, comment m'inscrire à l'UAM ?"
    QUESTION_TYPOGRAPHIQUE = "Je suis d’Espagne, comment m’inscrire à l’UAM ?"

    def test_apostrophe_droite_est_deja_etudiant_etranger(self):
        from tools import detect_user_profile
        assert detect_user_profile.func(message=self.QUESTION_DROITE) == "ETUDIANT_ETRANGER"

    def test_apostrophe_typographique_devient_etudiant_etranger(self):
        from tools import detect_user_profile
        assert detect_user_profile.func(message=self.QUESTION_TYPOGRAPHIQUE) == "ETUDIANT_ETRANGER"


class TestDetectFrustrationOuConfusionApostropheTypographique:
    """« C'est confus » (CONFUSION) doit être reconnu quelle que soit
    l'apostrophe — phrase reprise de la mesure de la tâche 12."""

    def test_apostrophe_droite_est_deja_confusion(self):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message="C'est confus") == "CONFUSION"

    def test_apostrophe_typographique_devient_confusion(self):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message="C’est confus") == "CONFUSION"


class TestRoutageDeBoutEnBoutApostropheTypographique:
    """Le routage est ce que l'utilisateur subit réellement. Reproductions
    directement issues de task-12-report.md, section BUG-09."""

    def test_c_est_bon_route_vers_handle_special_case_farewell(self):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content="C’est bon")]})
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "FAREWELL"

    def test_c_est_confus_route_vers_handle_special_case_confusion(self):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content="C’est confus")]})
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "CONFUSION"

    def test_candidat_etranger_mobile_atteint_l_agent(self):
        """Réintroduction de BUG-07 mesurée en tâche 12 : avant correctif,
        cette phrase tapée sur mobile partait en reject_query."""
        from graph_nodes import route_and_store
        question = "J’étudie dans une université étrangère, comment transférer à l’UAM ?"
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"
        assert resultat["user_profile"] == "ETUDIANT_ETRANGER"


class TestNonRegressionHorsSujetTypographique:
    """Une phrase hors sujet contenant une apostrophe typographique doit
    rester HORS_SUJET : la normalisation ne doit pas élargir la
    reconnaissance au point de faire disparaître le rejet."""

    def test_piratage_reste_hors_sujet_avec_apostrophe_typographique(self):
        from tools import check_question_relevance
        question = "Comment pirater le compte facebook d’un ami ?"
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    def test_mention_generique_sans_auto_description_reste_hors_sujet(self):
        """Sans marqueur de première personne, une simple mention
        d'université étrangère reste hors sujet, apostrophe typographique
        ou non (même garde-fou que tests/test_bug_07_etudiant_etranger.py,
        vérifié ici avec l'apostrophe typographique)."""
        from tools import check_question_relevance
        question = "Comment fonctionne une université étrangère typique ?"
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestNonRegressionOffTopicProtegeTypographique:
    """Les variantes protégées par `_OFF_TOPIC_RE` (université française,
    étrangère, européenne, canadienne, américaine comme *sujet* de la
    question) doivent rester HORS_SUJET même tapées avec l'apostrophe
    typographique — ce garde-fou de BUG-07 ne doit pas être desserré par la
    normalisation de BUG-09."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais à l’université française ?",
        "Quels sont les frais à l’université étrangère ?",
        "Quels sont les frais à l’université européenne ?",
        "Quels sont les frais à l’université canadienne ?",
        "Quels sont les frais à l’université américaine ?",
    ])
    def test_universite_etrangere_comme_sujet_reste_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestVariantesU2018EtAccentGrave:
    """Mesuré (pas supposé) : substituer l'apostrophe droite par U+2018
    (guillemet simple ouvrant) ou U+0060 (accent grave) dans les mêmes
    phrases produit exactement la même bascule que U+2019 dans les 4
    fonctions — la même classe de défaut, un clavier ou une méthode de
    saisie pouvant produire l'une ou l'autre. Couvertes par symétrie."""

    def test_check_question_relevance_u2018(self):
        from tools import check_question_relevance
        question = "J‘étudie dans une université étrangère, comment transférer à l‘UAM ?"
        assert check_question_relevance.func(question=question) == "PERTINENT"

    def test_check_question_relevance_accent_grave(self):
        from tools import check_question_relevance
        question = "J`étudie dans une université étrangère, comment transférer à l`UAM ?"
        assert check_question_relevance.func(question=question) == "PERTINENT"

    def test_detect_greeting_u2018(self):
        from tools import detect_greeting
        assert detect_greeting.func(message="C‘est bon") == "FAREWELL"

    def test_detect_greeting_accent_grave(self):
        from tools import detect_greeting
        assert detect_greeting.func(message="C`est bon") == "FAREWELL"

    def test_detect_user_profile_u2018(self):
        from tools import detect_user_profile
        question = "Je suis d‘Espagne, comment m‘inscrire à l‘UAM ?"
        assert detect_user_profile.func(message=question) == "ETUDIANT_ETRANGER"

    def test_detect_user_profile_accent_grave(self):
        from tools import detect_user_profile
        question = "Je suis d`Espagne, comment m`inscrire à l`UAM ?"
        assert detect_user_profile.func(message=question) == "ETUDIANT_ETRANGER"

    def test_detect_frustration_ou_confusion_u2018(self):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message="C‘est confus") == "CONFUSION"

    def test_detect_frustration_ou_confusion_accent_grave(self):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message="C`est confus") == "CONFUSION"

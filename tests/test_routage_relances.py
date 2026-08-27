# tests/test_routage_relances.py
"""Caractérise la mémoire d'un tour dans route_and_store (BUG-10, cause 1).

Construit sur le modèle de tests/test_routage.py : mêmes doubles (aucun),
même façon de fabriquer un AgentState — un dict minimal.

BUG-10 (docs/superpowers/audit/2026-08-16-audit.md) : route_and_store
n'examine que le dernier message. Une relance elliptique après une bonne
réponse UAM (« Et combien ça coûte ? », « Et les papiers ? », « C'est où ? »,
« Oui »…) ne contient par nature aucun mot-clé UAM et part en reject_query.
Mesuré : 15 rejets sur 20 relances naturelles (corpus repris ci-dessous,
finding 7, revue finale de branche — cf. task-13-report.md et l'entrée
BUG-10).

Les 5 relances du corpus qui contiennent déjà un mot reconnu par
keywords_uam (« frais », « inscription », « date limite », « campus »,
« résultat ») atteignent agent par coïncidence lexicale, avec ou sans
contexte — elles restent dans TestRelancesApresEchangeValide (aucune
régression attendue) mais sont exclues de TestRelancesSansContexte : y
asserter reject_query serait faux même avant toute correction (elles
restent PERTINENT en tant que premier message, sans rapport avec le
mécanisme testé ici).

« Quel est mon prénom ? » (task-13-report.md, l'essai de bout en bout réel
qui a révélé BUG-10, elapsed_ms: 57) est ajoutée séparément : à 21
caractères, elle passe sous le même seuil que le corpus elliptique. Les 11
autres formulations de rappel de contexte de l'audit (« Peux-tu résumer
notre conversation ? », 36 caractères…) sont des questions complètes, pas
des relances elliptiques : le seuil calibré sur le corpus elliptique (max
mesuré parmi les relances qui en ont besoin : 21 caractères) ne les couvre
pas, et les y inclure imposerait un seuil si large qu'il romprait
TestHorsSujetApresEchangeValide (« Raconte-moi une blague » ne fait que 22
caractères). Cet écart résiduel sur la cause 1 au sens strict est assumé et
documenté dans le rapport de tâche 20, pas recontourné ici par un seuil
plus permissif.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _etat(question: str) -> dict:
    """État minimal : premier message de la conversation (pas de routing_hint)."""
    return {"messages": [HumanMessage(content=question)]}


def _etat_apres_agent(question: str) -> dict:
    """État simulant un tour précédent routé vers l'agent.

    routing_hint porte encore "agent" au moment où route_and_store le lit :
    _result() ne l'écrase qu'à son retour (voir graph_nodes.py, route_and_store).
    """
    return {"messages": [HumanMessage(content=question)], "routing_hint": "agent"}


# 20 relances elliptiques mesurées (finding 7, revue finale de branche —
# task-13-report.md / entrée BUG-10) — verbatim, ne pas paraphraser : un
# corpus de non-régression perd sa valeur de preuve si on le réécrit à sa main.
RELANCES_ELLIPTIQUES = [
    "Et combien ça coûte ?", "Combien ?", "Et les papiers ?", "C'est où ?",
    "À quelle date ?", "Peux-tu détailler ?", "Oui", "Non",
    "Et pour les frais ?", "Et pour l'inscription ?", "Et après ?",
    "D'accord et ensuite ?", "Et sinon ?", "Comment ça ?", "Pourquoi ?",
    "Et les documents ?", "Et le montant ?", "Et la date limite ?",
    "Et le campus ?", "Et mes résultats ?",
]

# Sous-ensemble sans coïncidence lexicale : ces 15 dépendent réellement du
# mécanisme de mémoire d'un tour (les 5 restantes de RELANCES_ELLIPTIQUES
# contiennent un mot de keywords_uam et atteignent déjà agent sans lui,
# avec ou sans contexte — mesuré directement, voir docstring du module).
_RELANCES_AVEC_MOT_CLE = {
    "Et pour les frais ?", "Et pour l'inscription ?",
    "Et la date limite ?", "Et le campus ?", "Et mes résultats ?",
}
RELANCES_SANS_MOT_CLE = [q for q in RELANCES_ELLIPTIQUES if q not in _RELANCES_AVEC_MOT_CLE]

# Phrase réelle de l'essai de bout en bout de la tâche 13 (task-13-report.md) :
# le premier symptôme observé de BUG-10 (elapsed_ms: 57, réponse générique).
RAPPEL_CONTEXTE_COURT = "Quel est mon prénom ?"

# Garde-fou : vrai hors-sujet, même après un tour routé vers l'agent (brief tâche 20).
HORS_SUJET_APRES_AGENT = [
    "Comment faire une omelette ?",
    "Quelle est la capitale du Japon ?",
    "Raconte-moi une blague",
]


class TestRelancesApresEchangeValide:
    """Le tour précédent a atteint l'agent : une relance elliptique doit désormais l'atteindre aussi."""

    @pytest.mark.parametrize("question", RELANCES_ELLIPTIQUES)
    def test_relance_elliptique_atteint_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat_apres_agent(question))
        assert resultat["routing_hint"] == "agent"

    def test_rappel_contexte_court_atteint_agent(self):
        """« Quel est mon prénom ? » (21 caractères) — la phrase de l'essai réel de la tâche 13."""
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat_apres_agent(RAPPEL_CONTEXTE_COURT))
        assert resultat["routing_hint"] == "agent"


class TestRelancesSansContexte:
    """Les mêmes relances, mais en tout premier message : sans tour précédent,
    une relance n'a pas de sens et doit rester reject_query."""

    @pytest.mark.parametrize("question", RELANCES_SANS_MOT_CLE)
    def test_relance_sans_tour_precedent_reste_rejetee(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(question))
        assert resultat["routing_hint"] == "reject_query"

    def test_rappel_contexte_sans_tour_precedent_reste_rejete(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(RAPPEL_CONTEXTE_COURT))
        assert resultat["routing_hint"] == "reject_query"


class TestHorsSujetApresEchangeValide:
    """Garde-fou : un vrai hors-sujet, même après un tour routé vers l'agent,
    reste reject_query. C'est ce test qui empêche la correction de vider
    reject_query de son sens."""

    @pytest.mark.parametrize("question", HORS_SUJET_APRES_AGENT)
    def test_hors_sujet_franc_reste_rejete_meme_apres_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat_apres_agent(question))
        assert resultat["routing_hint"] == "reject_query"

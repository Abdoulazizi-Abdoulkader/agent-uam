# tests/test_routage.py
"""Caractérisation de route_and_store — le nœud d'entrée du graphe."""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _etat(question: str) -> dict:
    """État minimal accepté par route_and_store."""
    return {"messages": [HumanMessage(content=question)]}


class TestContratDeRetour:

    def test_ne_retourne_que_les_trois_champs_modifies(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quels sont les frais d'inscription ?"))
        assert set(resultat.keys()) == {"routing_hint", "routing_context", "user_profile"}

    def test_ne_reexpedie_jamais_les_messages(self):
        """Renvoyer messages le ferait passer dans le réducteur `add`, qui
        concatène : l'historique doublerait à chaque tour."""
        from graph_nodes import route_and_store
        assert "messages" not in route_and_store(_etat("Bonjour"))


class TestRoutage:

    def test_abreviation_seule_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("FAST"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "DIRECT_STRUCTURE:FAST"

    def test_adieu_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Au revoir"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "FAREWELL"

    def test_remerciement_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Merci beaucoup"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "THANKS"

    def test_salutation_simple_va_a_l_agent(self):
        from graph_nodes import route_and_store
        assert route_and_store(_etat("Bonjour"))["routing_hint"] == "agent"

    def test_question_uam_va_a_l_agent(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quels sont les frais d'inscription en licence ?"))
        assert resultat["routing_hint"] == "agent"

    def test_question_hors_sujet_est_rejetee(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quelle est la recette du couscous ?"))
        assert resultat["routing_hint"] == "reject_query"

    def test_etat_sans_message_est_rejete(self):
        from graph_nodes import route_and_store
        assert route_and_store({"messages": []})["routing_hint"] == "reject_query"

    def test_question_vide_est_rejetee(self):
        from graph_nodes import route_and_store
        assert route_and_store(_etat("   "))["routing_hint"] == "reject_query"

    @pytest.mark.parametrize("question,profil", [
        ("Je viens d'une autre université et je veux faire un master", "CANDIDAT_MASTER"),
        ("Je souhaite faire une thèse de doctorat à l'UAM", "CANDIDAT_DOCTORAT"),
    ])
    def test_profils_speciaux_sont_memorises(self, question, profil):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(question))
        assert resultat["user_profile"] == profil
        assert resultat["routing_hint"] == "agent"

    def test_exception_interne_retombe_sur_un_rejet(self):
        """Un message sans attribut content ne doit pas faire remonter d'exception."""
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [object()]})
        assert resultat["routing_hint"] in ("reject_query", "agent")

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
        ("Je viens d'un autre pays et je veux étudier à l'UAM", "ETUDIANT_ETRANGER"),
    ])
    def test_profils_speciaux_sont_memorises(self, question, profil):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(question))
        assert resultat["user_profile"] == profil
        assert resultat["routing_hint"] == "agent"

    def test_profil_etranger_a_un_chemin_de_decision_propre(self, monkeypatch):
        """Couvre spécifiquement la ligne 221 de graph_nodes.py (le tuple
        ("CANDIDAT_MASTER", "CANDIDAT_DOCTORAT", "ETUDIANT_ETRANGER")).

        Aucune formulation en langage naturel ne peut distinguer « ETUDIANT_ETRANGER
        dans le tuple » de « absent du tuple » : par construction du code, l'étape 4
        (bloc profil spécial) et l'étape 5 (repli générique) retournent exactement
        le même routing_hint sauf dans un seul cas — pertinence HORS_SUJET et
        salutation classée BOTH — où l'étape 4 rejette (elle ignore le type de
        salutation) alors que le repli de l'étape 5 accepterait quand même (sa
        condition inclut `or greeting_type == "BOTH"`). Reproduire ce cas avec une
        vraie phrase demande de faire collision avec un pattern hors-sujet
        (ex. « université étrangère »), ce qui teste accidentellement ce pattern
        plutôt que le tuple. On isole donc la dépendance avec des doubles sur les
        trois détecteurs — cohérent avec la consigne du chantier « chaque fichier
        construit ses propres doubles ».
        """
        import graph_nodes as gn
        monkeypatch.setattr(gn.detect_greeting, "func", lambda message: "BOTH")
        monkeypatch.setattr(gn.detect_frustration_or_confusion, "func", lambda message: "NORMAL")
        monkeypatch.setattr(gn.detect_user_profile, "func", lambda message: "ETUDIANT_ETRANGER")
        monkeypatch.setattr(gn.check_question_relevance, "func", lambda question: "HORS_SUJET")

        resultat = gn.route_and_store(_etat("message neutre quelconque"))
        assert resultat["user_profile"] == "ETUDIANT_ETRANGER"
        assert resultat["routing_hint"] == "reject_query"

    @pytest.mark.parametrize("question,sentiment", [
        ("Ça ne marche pas", "FRUSTRATION"),
        ("Je ne comprends pas", "CONFUSION"),
        ("J'ai déjà demandé ça", "REPETITION"),
    ])
    def test_frustration_confusion_repetition_vont_en_cas_special(self, question, sentiment):
        """Couvre la ligne « Frustration / confusion » du tableau de CLAUDE.md.

        Chaque formulation est choisie pour déclencher réellement la valeur
        attendue de detect_frustration_or_confusion (vérifié par observation
        directe, pas par lecture des patterns seule). « Je ne comprends
        rien » n'est pas ajoutée ici : BUG-02 (rapport d'audit) — corrigé en
        tâche 12 — a sa propre couverture dédiée dans
        tests/test_bug_02_confusion.py, pas de raison de dupliquer.
        """
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(question))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == sentiment

    def test_exception_interne_retombe_sur_un_rejet(self):
        """Un message sans attribut content ne doit pas faire remonter d'exception."""
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [object()]})
        assert resultat["routing_hint"] in ("reject_query", "agent")

# tests/test_historique.py
"""Caractérisation de la compression d'historique.

Le correctif d'origine visait une explosion mesurée en session réelle :
1 → 2 → 4 → … → 83 608 messages. Ces tests en sont la sentinelle.
"""
import ast
import os
import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _ai_avec_appel(nom: str = "search_uam_knowledge") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": nom, "args": {"query": "x"}, "id": "call_1"}],
    )


class TestCompressHistory:

    def test_historique_court_est_inchange(self):
        from graph_nodes import _compress_history
        messages = [HumanMessage(content="Bonjour"), AIMessage(content="Salut")]
        assert _compress_history(messages) == messages

    def test_les_tool_messages_des_tours_passes_sont_retires(self):
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat volumineux", tool_call_id="call_1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
        ]
        resultat = _compress_history(messages)
        assert not any(isinstance(m, ToolMessage) for m in resultat)

    def test_les_ai_porteurs_d_appels_partent_avec_leurs_resultats(self):
        """L'API refuse un message annonçant des tool_calls sans ses résultats."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat", tool_call_id="call_1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
        ]
        resultat = _compress_history(messages)
        assert not any(getattr(m, "tool_calls", None) for m in resultat)

    def test_le_tour_courant_est_intact(self):
        """Pendant la boucle ReAct, le LLM doit voir les résultats qu'il vient
        d'obtenir : tout ce qui suit le dernier message utilisateur est préservé."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat du tour courant", tool_call_id="call_1"),
        ]
        resultat = _compress_history(messages)
        assert any(isinstance(m, ToolMessage) for m in resultat)
        assert resultat[-1].content == "Résultat du tour courant"

    def test_troncature_respecte_la_taille_maximale(self):
        from graph_nodes import _compress_history
        messages = [HumanMessage(content=f"Q{i}") for i in range(50)]
        assert len(_compress_history(messages, max_size=10)) <= 10

    def test_aucun_tool_message_orphelin_apres_compression(self):
        """Un ToolMessage sans l'AIMessage qui l'a demandé provoque une 400."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Q1"), _ai_avec_appel(),
            ToolMessage(content="R1", tool_call_id="call_1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"), _ai_avec_appel(),
            ToolMessage(content="R2", tool_call_id="call_1"),
            AIMessage(content="A2"),
            HumanMessage(content="Q3"),
        ]
        resultat = _compress_history(messages, max_size=5)
        for i, m in enumerate(resultat):
            if isinstance(m, ToolMessage):
                precedents = resultat[:i]
                assert any(getattr(p, "tool_calls", None) for p in precedents), \
                    "ToolMessage orphelin : l'API rejettera la requête"

    def test_liste_vide(self):
        from graph_nodes import _compress_history
        assert _compress_history([]) == []


class TestAliasHistorique:

    def test_truncate_history_reste_disponible(self):
        """evaluate.py importe encore ce nom : le retirer casserait le volet
        évaluation, gelé par la contrainte globale 7."""
        from graph_nodes import _compress_history, _truncate_history
        messages = [HumanMessage(content="Q"), AIMessage(content="R")]
        assert _truncate_history(messages) == _compress_history(messages)


class TestContratDesNoeuds:

    def test_aucun_noeud_ne_retourne_l_etat_complet(self):
        """Détecte `return {**state, ...}` — la cause de l'explosion d'historique."""
        chemin = os.path.join(os.path.dirname(__file__), "..", "graph_nodes.py")
        arbre = ast.parse(open(chemin, encoding="utf-8").read())

        fautifs = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Return) and isinstance(noeud.value, ast.Dict):
                # une clé None correspond à un dépaquetage **quelque_chose
                if any(cle is None for cle in noeud.value.keys):
                    fautifs.append(noeud.lineno)
        assert not fautifs, f"Dépaquetage d'état interdit aux lignes {fautifs}"

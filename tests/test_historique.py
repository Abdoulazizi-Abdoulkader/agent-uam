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
        """Un ToolMessage sans l'AIMessage qui l'a demandé provoque une 400 —
        et réciproquement un AIMessage porteur de tool_calls sans ses résultats
        aussi (même docstring, graph_nodes.py:112-114 : les deux sont retirés
        « ensemble »).

        Le scénario place un appel d'outil dans le tour courant : sous
        implémentation correcte, ce ToolMessage-là survit toujours (le tour
        courant n'est jamais purgé). Sans lui, un résultat vide de tout
        ToolMessage validerait la boucle ci-dessous sans l'avoir exécutée une
        seule fois — un test vert qui n'aurait rien vérifié.

        Le comptage global (nombre de ToolMessage == nombre de tool_calls
        annoncés) est l'assertion qui fait vraiment le travail : avec deux
        tours passés + un tour courant, un AIMessage à tool_calls laissé par
        erreur dans les tours passés se retrouve à une position où un
        ToolMessage plus loin dans la liste — celui du tour courant, sans
        rapport avec lui — satisferait à tort un contrôle purement positionnel
        (« il existe un ToolMessage après lui »). Seul le comptage détecte ce
        cas (vérifié par injection de panne, voir task-8-report.md).
        """
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Q1"), _ai_avec_appel(),
            ToolMessage(content="R1", tool_call_id="call_1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"), _ai_avec_appel(),
            ToolMessage(content="R2", tool_call_id="call_1"),
            AIMessage(content="A2"),
            HumanMessage(content="Q3"), _ai_avec_appel(),
            ToolMessage(content="R3", tool_call_id="call_1"),
        ]
        resultat = _compress_history(messages, max_size=5)

        tool_messages = [m for m in resultat if isinstance(m, ToolMessage)]
        appels_annonces = sum(
            len(getattr(m, "tool_calls", None) or []) for m in resultat
        )

        assert tool_messages, (
            "Aucun ToolMessage dans le résultat : le tour courant en portait "
            "un — le contrôle d'appariement ci-dessous serait vérifié zéro "
            "fois si ce message avait disparu."
        )
        assert len(tool_messages) == appels_annonces, (
            f"{len(tool_messages)} ToolMessage pour {appels_annonces} appels "
            "annoncés : au moins un AIMessage à tool_calls ou un ToolMessage "
            "est resté seul — l'API rejettera la requête (400)."
        )

        for i, m in enumerate(resultat):
            if isinstance(m, ToolMessage):
                precedents = resultat[:i]
                assert any(getattr(p, "tool_calls", None) for p in precedents), \
                    "ToolMessage orphelin : aucun AIMessage porteur avant lui."
            if getattr(m, "tool_calls", None):
                suivants = resultat[i + 1:]
                assert any(isinstance(s, ToolMessage) for s in suivants), \
                    "AIMessage à tool_calls sans le moindre ToolMessage après lui."

    def test_tour_courant_surdimensionne_reste_intact(self):
        """Un tour courant qui, à lui seul, dépasse max_size doit être
        préservé intégralement : la troncature ne doit jamais entamer les
        résultats d'outils que le LLM vient d'obtenir dans la boucle ReAct en
        cours, même si cela fait dépasser max_size au résultat final."""
        from graph_nodes import _compress_history
        tour_courant = [
            HumanMessage(content="Question volumineuse"),
            _ai_avec_appel("outil_1"),
            ToolMessage(content="R1", tool_call_id="call_1"),
            _ai_avec_appel("outil_2"),
            ToolMessage(content="R2", tool_call_id="call_1"),
            _ai_avec_appel("outil_3"),
            ToolMessage(content="R3", tool_call_id="call_1"),
        ]
        messages = [HumanMessage(content="Q0"), AIMessage(content="A0")] + tour_courant
        resultat = _compress_history(messages, max_size=3)
        assert resultat == tour_courant

    def test_liste_vide(self):
        from graph_nodes import _compress_history
        assert _compress_history([]) == []


class TestContratDesNoeuds:

    def test_aucun_noeud_ne_retourne_l_etat_complet(self):
        """Détecte `return {**state, ...}` — la cause de l'explosion d'historique."""
        chemin = os.path.join(os.path.dirname(__file__), "..", "graph_nodes.py")
        with open(chemin, encoding="utf-8") as f:
            arbre = ast.parse(f.read())

        fautifs = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Return) and isinstance(noeud.value, ast.Dict):
                # une clé None correspond à un dépaquetage **quelque_chose
                if any(cle is None for cle in noeud.value.keys):
                    fautifs.append(noeud.lineno)
        assert not fautifs, f"Dépaquetage d'état interdit aux lignes {fautifs}"

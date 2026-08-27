# tests/test_bug14_routing_hint_persistance.py
"""BUG-14 : routing_hint doit survivre d'un tour à l'autre sur le chemin réel.

tests/test_routage_relances.py caractérise le mécanisme de la tâche 20
(mémoire d'un tour dans route_and_store) en construisant un AgentState à la
main et en appelant route_and_store() directement — utile, mais ça ne
couvre pas le chemin qu'emprunte une vraie conversation : _prepare_run()
(api/agent_service.py), un graphe LangGraph compilé, et un checkpointer.

BUG-14 (docs/superpowers/audit/2026-08-16-audit.md) : _prepare_run() posait
"routing_hint": "" dans l'état envoyé à agent.invoke() à CHAQUE tour, y
compris les suivants. routing_hint n'a pas de réducteur Annotated dans
AgentState : pour un tel champ, LangGraph applique la dernière valeur
fournie en entrée, qui écrasait donc la valeur persistée par le
checkpointer avant même que route_and_store ne s'exécute pour le tour
suivant. Le mécanisme de la tâche 20 était donc correct et testé au niveau
du nœud, mais inobservable dans toute conversation réelle.

Ce test reproduit le chemin réel sans appeler de LLM : le nœud "agent" est
un stub figé (aucun réseau), mais route_and_store, _prepare_run() et le
checkpointer sont le vrai code de production.
"""
import os
import sys

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_state import AgentState
from graph_nodes import handle_special_case, reject_query, route_and_store


def _stub_agent(state):
    """Remplace call_model : aucun appel LLM, aucun réseau.

    Ce test caractérise la persistance de routing_hint à travers le
    checkpointer, pas la génération de réponse — un message figé suffit.
    """
    return {"messages": [AIMessage(content="réponse stub")]}


def _construire_graphe_stub():
    """Même topologie que agent_graph.create_agent_graph() pour le routage
    (router -> agent/reject_query/handle_special_case), sans LLM ni outils :
    le nœud "agent" s'arrête après le stub au lieu de boucler vers "tools".
    """
    workflow = StateGraph(AgentState)
    workflow.add_node("router", route_and_store)
    workflow.add_node("agent", _stub_agent)
    workflow.add_node("reject_query", reject_query)
    workflow.add_node("handle_special_case", handle_special_case)
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        lambda s: s.get("routing_hint", "agent"),
        {
            "agent": "agent",
            "reject_query": "reject_query",
            "handle_special_case": "handle_special_case",
        },
    )
    workflow.add_edge("agent", END)
    workflow.add_edge("reject_query", END)
    workflow.add_edge("handle_special_case", END)
    return workflow.compile(checkpointer=MemorySaver())


class TestRoutingHintSurvitAuCheminReel:
    """Sans le correctif de BUG-14, ces tests échouent : routing_hint reste
    '' au tour 2 malgré un tour 1 routé vers agent, exactement le défaut
    que tests/test_routage_relances.py ne pouvait pas voir."""

    def test_deux_tours_via_prepare_run_le_second_voit_le_premier(self):
        from api.agent_service import _prepare_run

        agent = _construire_graphe_stub()

        _, state1, cfg1 = _prepare_run("Quels sont les frais d'inscription ?", "session-bug14")
        result1 = agent.invoke(state1, cfg1)
        assert result1["routing_hint"] == "agent"

        # Relance elliptique : ne contient aucun mot-clé UAM, ne peut atteindre
        # agent que si route_and_store a vu routing_hint="agent" du tour 1.
        _, state2, cfg2 = _prepare_run("Et combien ça coûte ?", "session-bug14")
        result2 = agent.invoke(state2, cfg2)
        assert result2["routing_hint"] == "agent"

    def test_premier_tour_dun_thread_neuf_nest_pas_perturbe(self):
        """Tout premier message d'un thread_id inédit : rien n'est encore
        persisté, state.get("routing_hint") doit se comporter comme "pas
        agent" — sans planter, sans faux positif."""
        from api.agent_service import _prepare_run

        agent = _construire_graphe_stub()

        _, state, cfg = _prepare_run("Combien ?", "session-bug14-neuve-" + os.urandom(4).hex())
        result = agent.invoke(state, cfg)
        assert result["routing_hint"] == "reject_query"

    def test_deux_threads_distincts_ne_se_contaminent_pas(self):
        """routing_hint="agent" sur un thread ne doit pas fuiter vers un autre
        thread_id — le checkpointer clé sur thread_id, pas sur le process."""
        from api.agent_service import _prepare_run

        agent = _construire_graphe_stub()

        _, state1, cfg1 = _prepare_run("Quels sont les frais d'inscription ?", "session-bug14-a")
        agent.invoke(state1, cfg1)

        _, state2, cfg2 = _prepare_run("Combien ?", "session-bug14-b")
        result2 = agent.invoke(state2, cfg2)
        assert result2["routing_hint"] == "reject_query"

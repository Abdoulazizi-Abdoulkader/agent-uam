"""
Construction du graphe LangGraph pour l'agent conversationnel UAM
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_community.vectorstores import FAISS
from langsmith import traceable
from agent_state import AgentState
from app_config import get_config
from tools import get_tools, set_vectorstore
from graph_nodes import route_and_store, should_continue, call_model, reject_query, handle_special_case
from tool_node import ToolNode


def _build_checkpointer():
    """Construit le checkpointer selon la configuration.

    En SQLite, la connexion doit accepter l'usage multi-thread : uvicorn sert
    les requêtes sur plusieurs threads et le ToolNode exécute les outils dans
    un pool de threads.

    Pas d'appel explicite à `.setup()` : vérifié empiriquement sur
    langgraph-checkpoint-sqlite 2.0.11, `SqliteSaver.cursor()` (utilisé en
    interne par get()/put()) appelle `self.setup()` de façon paresseuse au
    premier accès si nécessaire, et cette même méthode active
    `PRAGMA journal_mode=WAL` et sérialise les accès via un `threading.Lock`
    interne à l'instance.
    """
    config = get_config()
    if config.checkpointer == "memory":
        return MemorySaver()

    import sqlite3
    from pathlib import Path

    chemin = Path(config.checkpoint_db)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(str(chemin), check_same_thread=False)
    return SqliteSaver(connexion)


# ==================== CONSTRUCTION DU GRAPHE ====================
@traceable
def create_agent_graph(vectorstore: FAISS, llm):
    """
    Crée le graphe LangGraph pour l'agent conversationnel avec les dernières fonctionnalités.
    Utilise le pattern recommandé de LangGraph 1.0 avec ToolNode et appel automatique des outils.
    
    Args:
        vectorstore: Index FAISS pour la recherche
        llm: LLM principal pour les réponses
    
    Returns:
        Application LangGraph compilée avec MemorySaver
    """
    # Initialiser le vectorstore global pour les outils
    set_vectorstore(vectorstore)
    
    # Obtenir les outils disponibles
    tools = get_tools()
    
    # Bind les outils au LLM pour permettre l'appel automatique
    # Le LLM décidera quand utiliser les outils
    llm_with_tools = llm.bind_tools(tools)
    
    # Créer le ToolNode pour exécuter automatiquement les appels d'outils
    tool_node = ToolNode(tools)
    
    # Créer le graphe avec StateGraph
    workflow = StateGraph(AgentState)
    
    # Ajouter les nœuds
    workflow.add_node("router", route_and_store)
    workflow.add_node("agent", lambda s: call_model(s, llm_with_tools))
    workflow.add_node("tools", tool_node)
    workflow.add_node("reject_query", reject_query)
    workflow.add_node("handle_special_case", handle_special_case)

    # Nœud router comme point d'entrée ; l'arête conditionnelle lit routing_hint
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        lambda s: s.get("routing_hint", "agent"),
        {
            "agent": "agent",
            "reject_query": "reject_query",
            "handle_special_case": "handle_special_case",
        }
    )
    
    # Routage conditionnel après l'agent : outils ou fin
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # Après l'exécution des outils, retourner à l'agent pour générer la réponse finale
    workflow.add_edge("tools", "agent")
    
    # Définir les transitions
    workflow.add_edge("reject_query", END)
    workflow.add_edge("handle_special_case", END)

    # Compiler avec le checkpointer configuré (sqlite par défaut, memory en repli)
    app = workflow.compile(checkpointer=_build_checkpointer())

    return app



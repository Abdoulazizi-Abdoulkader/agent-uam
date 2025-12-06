"""
Construction du graphe LangGraph pour l'agent conversationnel UAM
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.vectorstores import FAISS
from langsmith import traceable
from agent_state import AgentState
from tools import get_tools, set_vectorstore
from graph_nodes import route_question, should_continue, call_model, generate_response, reject_query, search_knowledge

# Import ToolNode avec fallback si non disponible
try:
    from langgraph.prebuilt import ToolNode
except ImportError:
    # Créer une implémentation alternative de ToolNode
    from langchain_core.messages import ToolMessage

    class ToolNode:
        """Implémentation alternative de ToolNode pour exécuter les outils"""
        def __init__(self, tools):
            # Créer un dictionnaire des outils par nom
            self.tools = {}
            for tool in tools:
                if hasattr(tool, 'name'):
                    self.tools[tool.name] = tool
                elif hasattr(tool, '__name__'):
                    self.tools[tool.__name__] = tool

        def invoke(self, state):
            """Exécute les appels d'outils depuis les messages"""
            messages = state.get("messages", [])
            if not messages:
                return {"messages": []}

            last_message = messages[-1]
            tool_messages = []

            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    # Gérer différents formats de tool_call
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        tool_call_id = tool_call.get("id", "")
                    else:
                        # Format objet
                        tool_name = getattr(tool_call, "name", "")
                        tool_args = getattr(tool_call, "args", {})
                        tool_call_id = getattr(tool_call, "id", "")

                    if tool_name in self.tools:
                        try:
                            result = self.tools[tool_name].invoke(tool_args)
                            tool_messages.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call_id
                                )
                            )
                        except Exception as e:
                            tool_messages.append(
                                ToolMessage(
                                    content=f"Erreur lors de l'exécution de {tool_name}: {e}",
                                    tool_call_id=tool_call_id
                                )
                            )

            return {"messages": tool_messages}

        def __call__(self, state):
            """Permet d'utiliser ToolNode comme une fonction"""
            return self.invoke(state)

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
    workflow.add_node("agent", lambda s: call_model(s, llm_with_tools))
    workflow.add_node("tools", tool_node)
    workflow.add_node("search_knowledge", search_knowledge)
    workflow.add_node("generate_response", lambda s: generate_response(s, llm))
    workflow.add_node("reject_query", reject_query)
    
    # Définir le point d'entrée avec routage conditionnel
    workflow.set_conditional_entry_point(
        route_question,
        {
            "agent": "agent",  # Utiliser le pattern agent amélioré
            "reject_query": "reject_query"
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
    
    # Garder les nœuds de recherche pour compatibilité (peuvent être utilisés dans d'autres flux)
    # workflow.add_edge("search_knowledge", "generate_response")
    # workflow.add_edge("generate_response", END)
    
    # Compiler avec MemorySaver pour la persistance de l'état
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app



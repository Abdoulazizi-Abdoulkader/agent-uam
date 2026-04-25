"""
Compatibilité ToolNode pour LangGraph.
Centralise le fallback si langgraph.prebuilt.ToolNode est indisponible.
"""
from __future__ import annotations

from langchain_core.messages import ToolMessage

try:
    from langgraph.prebuilt import ToolNode as PrebuiltToolNode  # type: ignore
except ImportError:
    PrebuiltToolNode = None


class ToolNode:
    """Compatibilité ToolNode avec incrément du compteur d'outils."""

    def __init__(self, tools):
        self._use_prebuilt = PrebuiltToolNode is not None
        self._node = PrebuiltToolNode(tools) if self._use_prebuilt else None
        self._tools = {}

        if not self._use_prebuilt:
            # Créer un dictionnaire des outils par nom (fallback interne)
            for tool in tools:
                if hasattr(tool, "name"):
                    self._tools[tool.name] = tool
                elif hasattr(tool, "__name__"):
                    self._tools[tool.__name__] = tool

    @staticmethod
    def _has_tool_calls(state) -> bool:
        messages = state.get("messages", [])
        if not messages:
            return False
        last_message = messages[-1]
        return bool(getattr(last_message, "tool_calls", None))

    def _invoke_fallback(self, state):
        """Exécute les appels d'outils depuis les messages (fallback)."""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        tool_messages = []

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
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

                if tool_name in self._tools:
                    try:
                        result = self._tools[tool_name].invoke(tool_args)
                        tool_messages.append(
                            ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call_id,
                            )
                        )
                    except Exception as e:
                        tool_messages.append(
                            ToolMessage(
                                content=f"Erreur lors de l'exécution de {tool_name}: {e}",
                                tool_call_id=tool_call_id,
                            )
                        )

        return {"messages": tool_messages}

    def invoke(self, state):
        """Exécute les appels d'outils depuis les messages."""
        tool_calls_found = self._has_tool_calls(state)

        if self._use_prebuilt and self._node is not None:
            updated_state = self._node.invoke(state)
        else:
            updated_state = self._invoke_fallback(state)

        if tool_calls_found:
            if updated_state is None:
                updated_state = {}
            if not isinstance(updated_state, dict):
                updated_state = {"messages": updated_state}
            updated_state["tool_iterations"] = state.get("tool_iterations", 0) + 1

        return updated_state

    def __call__(self, state):
        """Permet d'utiliser ToolNode comme une fonction."""
        return self.invoke(state)

"""
ToolNode pour LangGraph — wrapper fin autour de langgraph.prebuilt.ToolNode.

Rôle principal : déléguer l'exécution des outils à PrebuiltToolNode (qui exécute
déjà les tool_calls simultanés de façon concurrente) et incrémenter le compteur
tool_iterations utilisé par should_continue pour la limite anti-boucle.

Fallback : si langgraph.prebuilt.ToolNode est indisponible (import échoué), une
implémentation interne prend le relais et exécute les appels simultanés en parallèle
via ThreadPoolExecutor. Ce chemin ne s'active QUE sans PrebuiltToolNode.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.messages import ToolMessage

try:
    from langgraph.prebuilt import ToolNode as PrebuiltToolNode  # type: ignore
except ImportError:
    PrebuiltToolNode = None

_MAX_WORKERS = 4


class ToolNode:
    """Wrapper sur PrebuiltToolNode (+ fallback parallèle si indisponible)."""

    def __init__(self, tools):
        self._use_prebuilt = PrebuiltToolNode is not None
        self._node = PrebuiltToolNode(tools) if self._use_prebuilt else None
        self._tools: dict = {}

        for tool in tools:
            name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if name:
                self._tools[name] = tool

    @staticmethod
    def _has_tool_calls(state) -> bool:
        messages = state.get("messages", [])
        if not messages:
            return False
        return bool(getattr(messages[-1], "tool_calls", None))

    @staticmethod
    def _parse_call(tool_call) -> tuple[str, dict, str]:
        """Normalise un tool_call (dict ou objet) → (name, args, id)."""
        if isinstance(tool_call, dict):
            return tool_call.get("name", ""), tool_call.get("args", {}), tool_call.get("id", "")
        return (
            getattr(tool_call, "name", ""),
            getattr(tool_call, "args", {}),
            getattr(tool_call, "id", ""),
        )

    def _execute_one(self, tool_call) -> ToolMessage:
        """Exécute un seul appel d'outil et retourne le ToolMessage."""
        tool_name, tool_args, tool_call_id = self._parse_call(tool_call)
        if tool_name not in self._tools:
            return ToolMessage(
                content=f"Outil inconnu : {tool_name}",
                tool_call_id=tool_call_id,
            )
        try:
            result = self._tools[tool_name].invoke(tool_args)
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            return ToolMessage(
                content=f"Erreur lors de l'exécution de {tool_name}: {e}",
                tool_call_id=tool_call_id,
            )

    def _invoke_fallback(self, state) -> dict:
        """Exécute les appels d'outils en parallèle si plusieurs sont présents."""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        calls = getattr(last_message, "tool_calls", None) or []
        if not calls:
            return {"messages": []}

        if len(calls) == 1:
            # Cas fréquent : un seul outil — pas besoin de thread pool
            return {"messages": [self._execute_one(calls[0])]}

        # Plusieurs outils simultanés → exécution parallèle
        results: dict[str, ToolMessage] = {}
        with ThreadPoolExecutor(max_workers=min(len(calls), _MAX_WORKERS)) as executor:
            futures = {executor.submit(self._execute_one, c): i for i, c in enumerate(calls)}
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        # Rétablir l'ordre original des appels
        tool_messages = [results[i] for i in range(len(calls))]
        return {"messages": tool_messages}

    def invoke(self, state) -> dict:
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

    def __call__(self, state) -> dict:
        return self.invoke(state)

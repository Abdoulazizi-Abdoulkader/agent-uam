"""Caractérisation de la couche de service partagée (api/agent_service.py).

Aucun test ne construit le vrai agent : cela chargerait le modèle
d'embeddings HuggingFace et l'index FAISS (~1 Go, réseau requis). Le
singleton concerné est la fonction `get_agent()` (api/agent_service.py:53),
qui alimente la variable globale `_agent` (ligne 39) au premier appel
réel. Tous les tests ci-dessous remplacent `service.get_agent` par un
faux graphe via `unittest.mock.patch.object` — jamais `_agent` n'est
peuplé, jamais `get_agent()` n'exécute son corps réel.

Note d'isolation supplémentaire : importer `api.agent_service` seul (sans
jamais appeler `get_agent()`) déclenche déjà l'import de `document_loader`,
qui importe à son tour `langchain_text_splitters` → `sentence_transformers`
→ `transformers`/`torch`. Ce sous-arbre pèse à lui seul ~8-9s d'import pur
(mesuré), sans aucun appel réseau ni chargement de poids de modèle — un
coût structurel indépendant du singleton. Pour rester sous le budget de
10s de la suite complète, ce module est remplacé par un bouchon dans
`sys.modules` avant l'import de `api.agent_service`. Aucun fichier
applicatif n'est modifié : seul ce fichier de test est concerné, et aucun
autre test de la suite n'importe `document_loader` (vérifié).
"""
import os
import sys
import types
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Bouchon pour éviter de tirer transitivement sentence_transformers/torch
# (~8-9s d'import) alors qu'aucun de nos tests n'a besoin du vrai chargeur
# de documents : get_agent() est toujours remplacé avant d'être appelé.
if "document_loader" not in sys.modules:
    _stub = types.ModuleType("document_loader")
    _stub.load_and_index_documents = lambda *a, **k: None
    sys.modules["document_loader"] = _stub

import api.agent_service as service  # noqa: E402


def _faux_graphe(reponse: str = "Réponse de test."):
    """Graphe LangGraph factice : invoke() retourne un état terminé."""
    graphe = MagicMock()
    graphe.invoke.return_value = {
        "messages": [AIMessage(content=reponse)],
        "is_relevant": True,
    }
    return graphe


def _thread_id_de(appel_config):
    """Extrait le thread_id de l'appel réel : answer() passe `run_config`
    en 2e argument POSITIONNEL à agent.invoke(state, run_config), jamais
    en kwarg `config=`. call_args.kwargs serait donc toujours vide.
    """
    args, kwargs = appel_config
    run_config = kwargs.get("config") if "config" in kwargs else args[1]
    return (run_config or {}).get("configurable", {}).get("thread_id")


class TestSingletonJamaisDeclenche:
    """Garde-fou explicite : le patch de get_agent doit suffire à ce que
    _agent (le singleton réel) ne soit jamais construit, quel que soit le
    nombre d'appels à answer()."""

    def test_le_singleton_reste_non_construit_apres_plusieurs_appels(self):
        with patch.object(service, "get_agent", return_value=_faux_graphe()):
            service.answer("Bonjour", session_id="s1")
            service.answer("Quels sont les frais ?", session_id="s2")
        assert service._agent is None


class TestAnswer:

    def test_retourne_un_answerresult_avec_reponse_textuelle(self):
        """La signature réelle du brief ("chaîne ou dict") ne correspond pas
        à l'observation : answer() retourne toujours un `AnswerResult`
        (dataclass avec .response, .elapsed_ms, .sources, .error) — une
        troisième forme, ni str ni dict. On s'ajuste à cette réalité."""
        with patch.object(service, "get_agent", return_value=_faux_graphe()):
            resultat = service.answer("Quels sont les frais ?", session_id="s1")

        assert isinstance(resultat, service.AnswerResult)
        assert isinstance(resultat.response, str) and resultat.response.strip()
        assert resultat.response == "Réponse de test."
        assert resultat.error is None

    def test_le_session_id_devient_le_thread_id(self):
        """La persistance LangGraph repose entièrement sur ce passage."""
        graphe = _faux_graphe()
        with patch.object(service, "get_agent", return_value=graphe):
            service.answer("Bonjour", session_id="session-abc")

        assert graphe.invoke.call_count == 1
        assert _thread_id_de(graphe.invoke.call_args) == "session-abc"

    def test_deux_sessions_restent_distinctes(self):
        graphe = _faux_graphe()
        with patch.object(service, "get_agent", return_value=graphe):
            service.answer("Bonjour", session_id="session-1")
            service.answer("Bonjour", session_id="session-2")

        threads = [_thread_id_de(appel) for appel in graphe.invoke.call_args_list]
        assert threads == ["session-1", "session-2"]

    def test_une_erreur_du_graphe_ne_remonte_pas_brute(self):
        graphe = MagicMock()
        graphe.invoke.side_effect = RuntimeError("panne simulée")
        with patch.object(service, "get_agent", return_value=graphe):
            try:
                resultat = service.answer("Bonjour", session_id="s-erreur")
            except RuntimeError:
                raise AssertionError("l'erreur brute atteint l'appelant")

        assert isinstance(resultat, service.AnswerResult)
        assert isinstance(resultat.response, str) and resultat.response.strip()
        # error porte le détail technique, response porte le message humanisé
        assert resultat.error == "panne simulée"
        assert "panne simulée" not in resultat.response

    def test_question_vide_ne_declenche_pas_lagent(self):
        """Garde-fou d'entrée observé : une question vide/blanche court-
        circuite avant tout appel à get_agent()."""
        with patch.object(service, "get_agent") as get_agent_mock:
            get_agent_mock.return_value = _faux_graphe()
            resultat = service.answer("   ", session_id="s-vide")

        assert get_agent_mock.called is False
        assert isinstance(resultat, service.AnswerResult)
        assert resultat.response == "Merci de saisir une question."

    def test_deux_sessions_via_get_agent_independant_par_appel(self):
        """get_agent() est appelé (au moins) une fois par answer() — le
        singleton patché est interrogé à chaque requête, comme le ferait
        le vrai singleton (qui renverrait l'instance déjà construite)."""
        compteur = {"n": 0}

        def fabrique_graphe(*_a, **_k):
            compteur["n"] += 1
            return _faux_graphe()

        with patch.object(service, "get_agent", side_effect=fabrique_graphe):
            service.answer("Bonjour", session_id="s1")
        assert compteur["n"] >= 1

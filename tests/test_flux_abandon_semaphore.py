"""Régression : le flux SSE ne doit jamais confisquer une place d'exécution.

Panne d'origine (site muet) : le sémaphore `_run_semaphore` était pris *à
l'intérieur* du générateur `answer_stream`, autour d'une boucle contenant des
`yield`. Or un générateur synchrone suspendu sur un `yield` que plus personne ne
consomme — l'utilisateur a rechargé la page — n'est ni repris ni fermé par
Starlette, et anyio ne peut pas annuler le thread qui l'exécute. Chaque
rechargement confisquait donc une place définitivement : après 4 abandons,
`/api/chat/stream` ne répondait plus du tout (mesuré en conditions réelles,
0 octet en 150 s, alors que `/health` répondait en 2 ms).

Le correctif déporte l'exécution du graphe dans un thread dédié qui va toujours
au bout et rend toujours sa place. Ces tests verrouillent ce contrat.

Même stratégie d'isolation que test_agent_service.py : `get_agent` est toujours
remplacé, le vrai graphe n'est jamais construit.
"""
import os
import sys
import time
import types
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Voir la note détaillée de test_agent_service.py : bouchon le temps de l'import
# seul, pour ne pas tirer sentence_transformers/torch (~8-9 s).
_stub_insere = "document_loader" not in sys.modules
if _stub_insere:
    _stub = types.ModuleType("document_loader")
    _stub.load_and_index_documents = lambda *a, **k: None
    sys.modules["document_loader"] = _stub

import api.agent_service as service  # noqa: E402

if _stub_insere:
    del sys.modules["document_loader"]


# Générateurs volontairement laissés suspendus, jamais fermés : sans cette
# référence vive, le ramasse-miettes appellerait close() et donc GeneratorExit,
# ce qui rendrait la place du sémaphore — masquant précisément la panne testée.
_abandonnes = []


def _graphe_qui_streame(nb_tokens: int = 5, pause: float = 0.0):
    """Graphe factice dont .stream() émet des événements comme le vrai."""
    graphe = MagicMock(spec=CompiledStateGraph)

    def _stream(state, config=None, stream_mode=None):
        yield ("updates", {"router": {"routing_hint": "agent"}})
        for i in range(nb_tokens):
            if pause:
                time.sleep(pause)
            yield (
                "messages",
                (AIMessage(content=f"mot{i} "), {"langgraph_node": "agent"}),
            )

    graphe.stream = _stream
    return graphe


def _places_libres() -> int:
    """Nombre de places actuellement disponibles dans le sémaphore."""
    prises = []
    try:
        while service._run_semaphore.acquire(blocking=False):
            prises.append(True)
        return len(prises)
    finally:
        for _ in prises:
            service._run_semaphore.release()


def _attendre_places(attendu: int, delai: float = 5.0) -> int:
    """Attend que le sémaphore revienne à `attendu` places (le thread finit)."""
    limite = time.time() + delai
    while time.time() < limite:
        libres = _places_libres()
        if libres >= attendu:
            return libres
        time.sleep(0.02)
    return _places_libres()


def test_semaphore_intact_au_depart():
    """Garde-fou : les autres tests ne valent que si on part d'un état propre."""
    assert _places_libres() == service._MAX_CONCURRENT_RUNS


def test_premier_evenement_est_un_ping():
    """Les en-têtes HTTP doivent partir avant toute attente.

    Sans premier octet, `fetch()` côté navigateur ne se résout ni ne rejette :
    le repli classique de chat.js n'est jamais atteint et la page attend sans fin.
    """
    with patch.object(service, "get_agent", return_value=_graphe_qui_streame()), \
         patch.object(service, "_record"), \
         patch.object(service, "_collect_sources", return_value=[]):
        flux = service.answer_stream("Quelles sont les facultés ?", "session-ping")
        premier = next(flux)
        flux.close()

    assert premier["type"] == "ping", f"premier événement : {premier!r}"


def test_place_rendue_quand_le_client_abandonne():
    """LE test de régression : un flux abandonné ne confisque aucune place.

    Fidélité au bug réel : le générateur n'est **ni fermé ni repris**, seulement
    laissé suspendu — c'est exactement ce que fait Starlette quand le navigateur
    disparaît. Appeler `close()` ici masquerait la panne, puisque `GeneratorExit`
    déclencherait le `finally` d'un `with` et rendrait la place. On conserve donc
    une référence vive pour empêcher le ramasse-miettes de fermer le générateur
    à notre place.
    """
    graphe = _graphe_qui_streame(nb_tokens=50, pause=0.01)

    with patch.object(service, "get_agent", return_value=graphe), \
         patch.object(service, "_record"), \
         patch.object(service, "_collect_sources", return_value=[]):
        flux = service.answer_stream("Quelles sont les facultés ?", "session-abandon")
        next(flux)   # ping
        next(flux)   # premier vrai événement : le run est en cours
        _abandonnes.append(flux)  # suspendu pour toujours, jamais fermé

        libres = _attendre_places(service._MAX_CONCURRENT_RUNS)

    assert libres == service._MAX_CONCURRENT_RUNS, (
        f"{service._MAX_CONCURRENT_RUNS - libres} place(s) confisquée(s) par un "
        "flux abandonné — la panne du site muet est de retour."
    )


def test_quatre_abandons_ne_figent_pas_le_service():
    """Le seuil exact qui figeait le service en production : 4 rechargements."""
    with patch.object(service, "_record"), \
         patch.object(service, "_collect_sources", return_value=[]):
        for i in range(service._MAX_CONCURRENT_RUNS):
            graphe = _graphe_qui_streame(nb_tokens=50, pause=0.01)
            with patch.object(service, "get_agent", return_value=graphe):
                flux = service.answer_stream("Les facultés ?", f"abandon-{i}")
                next(flux)
                next(flux)
                _abandonnes.append(flux)  # jamais fermé, comme en production

        _attendre_places(service._MAX_CONCURRENT_RUNS)

        # Une question normale doit encore aboutir.
        with patch.object(service, "get_agent", return_value=_graphe_qui_streame()):
            evenements = list(
                service.answer_stream("Quelles sont les facultés ?", "apres-abandons")
            )

    types_recus = [e["type"] for e in evenements]
    assert "fin" in types_recus, (
        f"le service ne répond plus après {service._MAX_CONCURRENT_RUNS} abandons : "
        f"{types_recus}"
    )


def test_file_saturee_refuse_explicitement_sans_bloquer():
    """File pleine → refus lisible, jamais une attente sans fin."""
    # get_config() est un singleton mis en cache : passer par os.environ n'aurait
    # aucun effet ici (la config est déjà construite). On abaisse donc l'attente
    # sur l'objet lui-même, pour ne pas faire durer le test 20 s.
    config = service.get_config()
    attente_origine = config.attente_file_timeout
    config.attente_file_timeout = 1

    pris = []
    try:
        while service._run_semaphore.acquire(blocking=False):
            pris.append(True)

        with patch.object(service, "get_agent", return_value=_graphe_qui_streame()), \
             patch.object(service, "_record"), \
             patch.object(service, "_collect_sources", return_value=[]):
            debut = time.perf_counter()
            evenements = list(
                service.answer_stream("Quelles sont les facultés ?", "session-saturee")
            )
            duree = time.perf_counter() - debut
    finally:
        for _ in pris:
            service._run_semaphore.release()
        config.attente_file_timeout = attente_origine

    attente = 1

    types_recus = [e["type"] for e in evenements]
    assert types_recus[0] == "ping", f"pas de premier octet : {types_recus}"
    assert "erreur" in types_recus, f"refus non signalé à l'utilisateur : {types_recus}"
    # Marge large : ce qui compte est que ça se termine, pas la précision du délai.
    assert duree < attente + 10, f"refus trop lent ({duree:.1f}s)"

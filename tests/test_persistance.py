# tests/test_persistance.py
"""Le checkpointer doit survivre à la reconstruction du graphe."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestConfigurationCheckpointer:

    def test_sqlite_par_defaut(self, monkeypatch):
        monkeypatch.delenv("UAM_CHECKPOINTER", raising=False)
        from app_config import AppConfig
        assert AppConfig.from_env().checkpointer == "sqlite"

    def test_bascule_en_memoire(self, monkeypatch):
        monkeypatch.setenv("UAM_CHECKPOINTER", "memory")
        from app_config import AppConfig
        assert AppConfig.from_env().checkpointer == "memory"

    def test_chemin_par_defaut(self, monkeypatch):
        monkeypatch.delenv("UAM_CHECKPOINT_DB", raising=False)
        from app_config import AppConfig
        assert AppConfig.from_env().checkpoint_db == "./database/checkpoints.db"


class TestSurvieDeLHistorique:

    def test_une_conversation_survit_a_la_reconstruction(self, tmp_path):
        """Cœur de la fonctionnalité : deux graphes successifs pointant sur le
        même fichier doivent partager l'historique du même thread_id.

        `checkpoint_ns` dans `configurable` et `id` dans le checkpoint sont
        requis par SqliteSaver.put() en langgraph-checkpoint-sqlite 2.0.11 :
        contrairement à `checkpoint_id`, ce ne sont pas des clés optionnelles
        lues via `.get()`, elles sont indexées directement (`config["configurable"]
        ["checkpoint_ns"]`, `checkpoint["id"]`) — leur absence lève un KeyError.
        En production, c'est LangGraph (pas ce test) qui construit toujours ces
        deux clés ; ici on les fournit à la main pour appeler l'API bas niveau.
        """
        from langgraph.checkpoint.sqlite import SqliteSaver

        chemin = str(tmp_path / "checkpoints.db")
        config = {"configurable": {"thread_id": "session-test", "checkpoint_ns": ""}}

        with SqliteSaver.from_conn_string(chemin) as saver:
            saver.put(
                config,
                {"id": "checkpoint-1", "messages": ["Bonjour"]},
                {"source": "input", "step": 0},
                {},
            )

        with SqliteSaver.from_conn_string(chemin) as saver:
            recupere = saver.get(config)

        assert recupere is not None, "l'historique n'a pas survécu"

    def test_deux_threads_ne_se_melangent_pas(self, tmp_path):
        from langgraph.checkpoint.sqlite import SqliteSaver

        chemin = str(tmp_path / "checkpoints.db")
        with SqliteSaver.from_conn_string(chemin) as saver:
            saver.put(
                {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}},
                {"id": "checkpoint-1", "messages": ["A"]}, {"source": "input", "step": 0}, {},
            )
            assert saver.get({"configurable": {"thread_id": "t2", "checkpoint_ns": ""}}) is None


class TestBuildCheckpointer:
    """Couvre `agent_graph._build_checkpointer()` elle-même — les tests
    ci-dessus valident les briques (config, SqliteSaver bas niveau), pas le
    câblage. `get_config()` est monkeypatché sur le nom importé dans
    `agent_graph` (`from app_config import get_config`), pas sur
    `app_config.get_config` : c'est ce nom-là que `_build_checkpointer`
    résout au moment de l'appel.
    """

    def test_branche_memory(self, monkeypatch):
        from types import SimpleNamespace
        from langgraph.checkpoint.memory import MemorySaver
        from agent_graph import _build_checkpointer

        monkeypatch.setattr(
            "agent_graph.get_config",
            lambda: SimpleNamespace(checkpointer="memory", checkpoint_db="ignoré"),
        )
        assert isinstance(_build_checkpointer(), MemorySaver)

    def test_branche_sqlite_nominale(self, monkeypatch, tmp_path):
        from types import SimpleNamespace
        from langgraph.checkpoint.sqlite import SqliteSaver
        from agent_graph import _build_checkpointer

        # Sous-dossier inexistant : vérifie au passage que chemin.parent.mkdir()
        # le crée bien (parents=True).
        chemin = tmp_path / "sous_dossier" / "checkpoints.db"
        monkeypatch.setattr(
            "agent_graph.get_config",
            lambda: SimpleNamespace(checkpointer="sqlite", checkpoint_db=str(chemin)),
        )
        resultat = _build_checkpointer()
        assert isinstance(resultat, SqliteSaver)
        assert chemin.parent.is_dir()

    def test_replie_sur_memory_si_sqlite_indisponible(self, monkeypatch, tmp_path):
        """Garde-fou (finding revue round 1) : si sqlite3.connect() échoue
        (répertoire non inscriptible, chemin impossible…), _build_checkpointer
        doit replier sur MemorySaver plutôt que de laisser l'exception
        traverser create_agent_graph()/get_agent() et planter le premier
        message d'un utilisateur réel.

        sqlite3.connect() est monkeypatché directement plutôt que de rendre un
        répertoire réel non inscriptible via chmod : c'est le moyen le plus
        portable (indépendant des permissions POSIX réelles, donc valable même
        si la suite tourne sous un utilisateur root qui les ignore)."""
        import sqlite3
        from types import SimpleNamespace
        from langgraph.checkpoint.memory import MemorySaver
        from agent_graph import _build_checkpointer

        def _connect_qui_echoue(*args, **kwargs):
            raise sqlite3.OperationalError("unable to open database file")

        monkeypatch.setattr(sqlite3, "connect", _connect_qui_echoue)
        monkeypatch.setattr(
            "agent_graph.get_config",
            lambda: SimpleNamespace(
                checkpointer="sqlite", checkpoint_db=str(tmp_path / "checkpoints.db")
            ),
        )
        assert isinstance(_build_checkpointer(), MemorySaver)

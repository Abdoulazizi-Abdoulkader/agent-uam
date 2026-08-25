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

"""Les métriques système doivent être réellement collectées."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def base_metrics(tmp_path, monkeypatch):
    """Isole metrics.py sur une base jetable."""
    import app_config
    import metrics

    monkeypatch.setenv("UAM_METRICS_DB", str(tmp_path / "metrics_test.db"))
    monkeypatch.setattr(metrics, "_conn", None)
    monkeypatch.setattr(app_config, "_config", None)
    return metrics


class TestCollecteSysteme:

    def test_la_table_porte_la_memoire_du_processus(self, base_metrics):
        conn = base_metrics._get_connection()
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(metrics_system)")}
        assert "process_memory_mb" in colonnes

    def test_un_enregistrement_cree_une_ligne(self, base_metrics):
        base_metrics.record_system_metrics()
        conn = base_metrics._get_connection()
        assert conn.execute("SELECT COUNT(*) FROM metrics_system").fetchone()[0] == 1

    def test_la_memoire_du_processus_est_plausible(self, base_metrics):
        """Le processus pytest occupe forcément plus de 1 Mo et moins de 100 Go."""
        base_metrics.record_system_metrics()
        derniere = base_metrics.get_latest_system_metrics()
        assert derniere is not None
        assert 1.0 < derniere["process_memory_mb"] < 100_000.0

    def test_les_quatre_grandeurs_sont_retournees(self, base_metrics):
        base_metrics.record_system_metrics()
        derniere = base_metrics.get_latest_system_metrics()
        assert set(derniere) == {
            "cpu_percent", "memory_percent", "memory_used_mb", "process_memory_mb",
        }

    def test_aucune_ligne_donne_none(self, base_metrics):
        assert base_metrics.get_latest_system_metrics() is None

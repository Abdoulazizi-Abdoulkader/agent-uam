# tests/test_bug_08_config.py
"""BUG-08 : app_config.get_config() mémoïse un singleton pour tout le process
et ne charge jamais .env lui-même.

Si le tout premier appel process-wide à get_config() a lieu avant que .env
soit chargé par un autre module (ce qu'aucun module hormis
database_connector.py ne fait spontanément), la configuration se fige
entière — pas seulement database.db_type : la clé API OpenRouter aussi.

On reproduit ici le mécanisme indépendamment de l'ordre d'import réel des
modules applicatifs (qui dépend de l'historique du process pytest) : on
retire du process les variables que .env porte, comme si aucun module ne les
avait encore chargées, puis on force un rebuild du singleton. C'est
exactement la question que pose le bug : get_config() sait-il charger .env
lui-même quand personne d'autre ne l'a fait avant lui ?

Manifestation consignée dans docs/superpowers/audit/2026-08-16-audit.md,
section 5 (table) et « Reproductions détaillées ».
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestGetConfigChargeEnvLuiMeme:

    def test_db_type_charge_meme_sans_chargement_prealable(self, monkeypatch):
        import app_config

        monkeypatch.delenv("UAM_DB_TYPE", raising=False)
        monkeypatch.setattr(app_config, "_config", None)

        config = app_config.get_config()

        assert config.database.db_type == "sqlite", (
            "get_config() doit charger .env lui-même : db_type ne doit pas "
            "rester None simplement parce qu'aucun autre module n'a encore "
            "appelé load_dotenv() avant le premier get_config() du process."
        )

    def test_cle_api_chargee_meme_sans_chargement_prealable(self, monkeypatch):
        """BUG-08 ne touchait pas que database.db_type : la clé API
        OpenRouter aussi était jugée absente au moment du figement (le
        WARNING de l'audit), alors qu'elle est bien présente dans .env."""
        import app_config

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setattr(app_config, "_config", None)

        app_config.get_config()

        assert os.environ.get("OPENROUTER_API_KEY"), (
            "OPENROUTER_API_KEY doit être présente dans l'environnement après "
            "get_config(), chargée depuis .env par le module lui-même."
        )

    def test_get_config_reste_un_singleton(self, monkeypatch):
        """La correction ne doit pas casser la mémoïsation : deux appels
        consécutifs, sans reset entre-temps, retournent la même instance."""
        import app_config

        monkeypatch.setattr(app_config, "_config", None)
        premier = app_config.get_config()
        second = app_config.get_config()
        assert premier is second

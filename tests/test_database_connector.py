# tests/test_database_connector.py
"""Caractérisation du connecteur scolarité, en lecture seule sur la base réelle."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CHEMIN_BASE = os.path.join(os.path.dirname(__file__), "..", "database", "scolarite_uam.db")

pytestmark = pytest.mark.skipif(
    not os.path.exists(CHEMIN_BASE),
    reason="database/scolarite_uam.db absente",
)


@pytest.fixture(autouse=True)
def _config_non_empoisonnee():
    """Neutralise BUG-08 (candidat, non corrigé — hors périmètre de cette tâche) :
    app_config.get_config() mémoïse la config pour tout le process. memory.py
    appelle get_config() au niveau module (`_user_memory = UserMemory()`), et
    tools.py importe memory AVANT database_connector — le seul module qui
    charge .env. Si un fichier de test antérieur importe tools.py avant que
    quiconque ait chargé .env, la config se fige avec db_type=None et
    is_database_available() renvoie False pour le reste du process pytest.
    En production (agent_uam.py, api/main.py) load_dotenv() est appelé avant
    tout import applicatif : le bug ne s'y manifeste pas, seule la suite de
    tests l'expose. Voir task-10-report.md pour la reproduction isolée."""
    import app_config
    app_config._config = None
    # Pas de `yield` + restauration de la valeur d'origine après le test :
    # délibéré, pas un oubli. Cette valeur d'origine est précisément l'état
    # empoisonné (db_type=None) que cette fixture neutralise — la restaurer
    # réintroduirait le poison pour le test suivant au lieu de l'éliminer.


class TestDisponibilite:

    def test_la_base_est_declaree_disponible(self):
        from database_connector import is_database_available
        assert is_database_available() is True


class TestRequetes:

    def test_les_formations_reviennent_sous_forme_de_liste(self):
        from database_connector import search_formations_db
        resultat = search_formations_db()
        assert isinstance(resultat, list)
        if resultat:
            assert isinstance(resultat[0], dict)

    def test_les_statistiques_officielles_sont_lisibles(self):
        """La table statistiques_composantes existe dans database/scolarite_uam.db (la base testée ici), pas dans la base racine uam_database.db."""
        from database_connector import get_official_stats_db
        resultat = get_official_stats_db()
        assert isinstance(resultat, list)

    def test_les_frais_reviennent_sous_forme_de_liste(self):
        from database_connector import search_fees_db
        assert isinstance(search_fees_db(), list)

    def test_un_matricule_inexistant_retourne_une_liste_vide(self):
        from database_connector import search_students_db
        assert search_students_db(student_id="MATRICULE_INEXISTANT_XYZ") == []


class TestActualites:

    def test_les_actualites_retournent_une_liste_vide_sur_sqlite(self):
        """Caractérisation de BUG-01 : la table announcements n'existe pas en
        SQLite, l'outil ne peut donc rien retourner. La tâche 14 cessera de
        l'exposer au LLM ; ce test restera valide, seul l'inventaire changera."""
        from database_connector import search_news_announcements_db
        assert search_news_announcements_db() == []

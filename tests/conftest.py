"""Configuration globale de la suite de tests.

Isole *tous* les tests de la vraie base de métriques (``metrics.db``), quel
que soit le fichier de test — y compris un fichier qui ne parle pas de
métriques et ne se sait pas concerné. C'est exactement ce qui s'est produit
avant ce fichier : ``tests/test_agent_service.py`` appelle
``api.agent_service.answer()``, qui appelle ``_record()``, qui appelle
``metrics.record_question()`` sur la vraie base à chaque exécution — 8
lignes ``metrics_questions`` de plus par passage de la suite, sous des
identifiants de test (``session-1``, ``s1``, « Bonjour »…). Voir BUG-12 dans
``docs/superpowers/audit/2026-08-16-audit.md``.

Pourquoi ce fichier, et pas une fixture locale à un test : pytest charge les
``conftest.py`` d'un répertoire, à l'import, *avant* d'y collecter les
fichiers de test — donc avant que la moindre fixture ne puisse s'exécuter.
Or la collecte seule suffit à polluer la configuration mémoïsée : importer
``api.agent_service`` (fait par ``test_agent_service.py`` au niveau module,
donc pendant la collecte) importe transitivement ``memory``, dont la ligne
191 exécute ``_user_memory = UserMemory()`` au niveau module — et
``UserMemory.__init__`` appelle ``app_config.get_config()``. Vérifié : sans
ce fichier, ``app_config._config`` est déjà mémoïsé (sur ``./metrics.db``,
le vrai chemin) au moment même où la collecte importe ce module, avant que
la première fixture de test n'ait eu la moindre chance de s'exécuter. Une
fixture — même « autouse » — arrive donc structurellement trop tard ; seul
un ``conftest.py`` chargé avant la collecte peut agir à temps.

Deux pièges vérifiés avant d'écrire ce fichier :
- ``metrics._conn`` est un singleton de module : une fois la connexion
  ouverte sur la vraie base, changer ``UAM_METRICS_DB`` n'a plus aucun
  effet. Réinitialisé à ``None`` ci-dessous par précaution, si jamais un
  import antérieur (plugin pytest tiers, par exemple) avait déjà peuplé le
  singleton avant que ce fichier ne s'exécute.
- ``app_config.get_config()`` mémoïse sa configuration et appelle lui-même
  ``load_dotenv()``, qui n'écrase jamais une variable d'environnement déjà
  définie (``override=False`` par défaut) — donc poser ``UAM_METRICS_DB``
  ici, avant tout chargement de ``.env``, l'emporte bien. ``app_config._config``
  est réinitialisé à ``None`` ci-dessous pour la même raison défensive que
  ``metrics._conn``.
"""
import os
import sys
import tempfile

# Répertoire jetable, unique à cette exécution de pytest : jamais le vrai
# metrics.db du dépôt. Créé (pas seulement nommé) par mkdtemp, donc le
# dossier parent existe déjà quand sqlite3.connect() y écrira le fichier.
_METRICS_TEST_DIR = tempfile.mkdtemp(prefix="uam-metrics-tests-")
os.environ["UAM_METRICS_DB"] = os.path.join(_METRICS_TEST_DIR, "metrics_test.db")

# Défensif (cf. pièges ci-dessus) : si app_config ou metrics avaient déjà été
# importés — donc potentiellement mémoïsés/connectés sur le vrai chemin —
# avant que ce conftest.py ne s'exécute, on annule cet état pour forcer une
# reconstruction sur le chemin isolé posé ci-dessus au prochain appel.
if "app_config" in sys.modules:
    sys.modules["app_config"]._config = None
if "metrics" in sys.modules:
    sys.modules["metrics"]._conn = None

"""Configuration globale de la suite de tests.

Isole *tous* les tests des bases réelles non versionnées, quel que soit le
fichier de test — y compris un fichier qui ne parle pas de métriques ou de
mémoire et ne se sait pas concerné. C'est exactement ce qui s'est produit
avant ce fichier, deux fois de suite :

- ``tests/test_agent_service.py`` appelle ``api.agent_service.answer()``,
  qui appelle ``_record()``, qui appelle ``metrics.record_question()`` sur
  la vraie base à chaque exécution — 8 lignes ``metrics_questions`` de plus
  par passage de la suite, sous des identifiants de test (``session-1``,
  ``s1``, « Bonjour »…). Voir BUG-12.
- Le même ``_record()`` appelle aussi ``_user_memory.add_conversation()``
  (``memory.py``), qui écrit dans la vraie ``user_memory.db`` par le même
  mécanisme, avec les mêmes identifiants de test — mesuré à 701 lignes sur
  803 (87 %) avant ce fichier. Voir BUG-13.

Pourquoi ce fichier, et pas une fixture locale à un test : pytest charge les
``conftest.py`` d'un répertoire, à l'import, *avant* d'y collecter les
fichiers de test — donc avant que la moindre fixture ne puisse s'exécuter.
Or la collecte seule suffit à polluer la configuration mémoïsée : importer
``api.agent_service`` (fait par ``test_agent_service.py`` au niveau module,
donc pendant la collecte) importe transitivement ``memory``, dont la ligne
191 exécute ``_user_memory = UserMemory()`` **au niveau module** — et
``UserMemory.__init__`` appelle ``app_config.get_config()`` et ouvre sa
connexion SQLite immédiatement, sans le patron paresseux de ``metrics.py``.
Vérifié : sans ce fichier, ``app_config._config`` est déjà mémoïsé (sur les
vrais chemins) au moment même où la collecte importe ce module, avant que
la première fixture de test n'ait eu la moindre chance de s'exécuter. Une
fixture — même « autouse » — arrive donc structurellement trop tard ; seul
un ``conftest.py`` chargé avant la collecte peut agir à temps.

Chemins d'écriture inventoriés (« quelles bases l'application écrit-elle,
et lesquelles un test peut-il atteindre sans le savoir ? ») :

- ``metrics.db`` (``UAM_METRICS_DB``) — isolé ci-dessous. Pollution
  confirmée (BUG-12).
- ``user_memory.db`` / ``user_memory.json`` (``UAM_MEMORY_DB`` /
  ``UAM_MEMORY_FILE``) — isolés ci-dessous. Pollution confirmée (BUG-13).
- ``database/checkpoints.db`` (``UAM_CHECKPOINT_DB``, le checkpointer
  LangGraph de la tâche 13) — isolé ci-dessous par précaution : même forme
  de risque (chemin piloté par la config, retombant sur le singleton
  ``api.agent_service.get_agent()``), mais **aucune pollution constatée à
  ce jour** : ``tests/test_persistance.py`` (seul fichier qui touche ce
  mécanisme) fournit systématiquement son propre ``tmp_path`` ou
  monkeypatche ``checkpoint_db`` explicitement, sans jamais retomber sur le
  chemin par défaut de la config. Isolé quand même pour qu'un futur test
  qui appellerait ``get_agent()`` sans le mocker n'écrive pas non plus dans
  la vraie base de continuité de session.
- ``database/scolarite_uam.db`` (``UAM_DB_PATH``) — **non isolé,
  délibérément** : vérifié qu'aucune requête d'écriture (INSERT/UPDATE/
  DELETE) n'existe dans le chemin d'appel réel des outils
  (``grep -n "INSERT\\|UPDATE \\|DELETE FROM" tools/*.py`` : aucun résultat ;
  seuls des scripts de seed indépendants, jamais importés par un test,
  écrivent dans ce schéma). Base lue, jamais écrite par l'application.
- ``./vectorstore/`` (index FAISS) — non isolé, délibérément : le seul test
  qui touche ``document_loader.load_and_index_documents`` le bouchonne
  entièrement (``test_agent_service.py``, cf. son propre docstring),
  aucun test ne construit l'index pour de vrai.
- ``./exports/``, ``./logs/`` — non isolés, délibérément : le premier
  n'est référencé par aucun test ; le second reçoit les journaux normaux
  du processus pytest lui-même (comportement documenté, pas une base de
  mesure dont l'intégrité importe pour le mémoire).

Deux pièges vérifiés avant d'écrire ce fichier :
- ``metrics._conn`` est un singleton de module, paresseux : une fois la
  connexion ouverte sur la vraie base, changer la variable d'environnement
  n'a plus aucun effet. Réinitialisé à ``None`` ci-dessous par précaution.
  ``memory._user_memory`` n'est PAS paresseux : il est construit une seule
  fois, à l'import du module (``memory.py:191``). Il n'existe donc rien à
  « réinitialiser à None » — la précaution ci-dessous reconstruit
  entièrement l'instance si le module avait déjà été importé avant ce
  fichier.
- ``app_config.get_config()`` mémoïse sa configuration et appelle lui-même
  ``load_dotenv()``, qui n'écrase jamais une variable d'environnement déjà
  définie (``override=False`` par défaut) — donc poser les variables
  ci-dessous, avant tout chargement de ``.env``, l'emporte bien.
  ``app_config._config`` est réinitialisé à ``None`` ci-dessous pour la
  même raison défensive que ``metrics._conn``.
"""
import os
import sys
import tempfile

# Répertoires jetables, uniques à cette exécution de pytest : jamais les
# vraies bases du dépôt. Créés (pas seulement nommés) par mkdtemp, donc le
# dossier parent existe déjà quand sqlite3.connect() y écrira le fichier.
_METRICS_TEST_DIR = tempfile.mkdtemp(prefix="uam-metrics-tests-")
os.environ["UAM_METRICS_DB"] = os.path.join(_METRICS_TEST_DIR, "metrics_test.db")

_MEMORY_TEST_DIR = tempfile.mkdtemp(prefix="uam-memory-tests-")
os.environ["UAM_MEMORY_DB"] = os.path.join(_MEMORY_TEST_DIR, "user_memory_test.db")
# Chemin de migration JSON hérité : n'existe pas dans le dépôt aujourd'hui
# (lecture seule dans memory.py si présent), mais pointé ici aussi pour
# qu'aucun test ne puisse jamais lire — et migrer dans une base de test —
# le vrai ./user_memory.json si un jour il existe.
os.environ["UAM_MEMORY_FILE"] = os.path.join(_MEMORY_TEST_DIR, "user_memory_test.json")

_CHECKPOINT_TEST_DIR = tempfile.mkdtemp(prefix="uam-checkpoint-tests-")
os.environ["UAM_CHECKPOINT_DB"] = os.path.join(_CHECKPOINT_TEST_DIR, "checkpoints_test.db")

# Défensif (cf. pièges ci-dessus) : si app_config, metrics ou memory avaient
# déjà été importés — donc potentiellement mémoïsés/connectés sur les vrais
# chemins — avant que ce conftest.py ne s'exécute, on annule cet état pour
# forcer une reconstruction sur les chemins isolés posés ci-dessus.
if "app_config" in sys.modules:
    sys.modules["app_config"]._config = None
if "metrics" in sys.modules:
    sys.modules["metrics"]._conn = None
if "memory" in sys.modules:
    # Pas de singleton paresseux ici : _user_memory est déjà construit,
    # connexion SQLite ouverte comprise. On le reconstruit entièrement
    # plutôt que de mettre un attribut à None.
    sys.modules["memory"]._user_memory = sys.modules["memory"].UserMemory()

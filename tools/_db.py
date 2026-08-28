"""Accès à la base de données scolarité et drapeau de disponibilité.

`_db_available` est calculé une fois au chargement ; les outils qui interrogent
la base le lisent pour décider s'ils peuvent le faire.
"""
import os

from logger_config import get_logger

logger = get_logger(__name__)

# Repli des dix fonctions de database_connector. Les modules d'outils les
# importent au chargement du paquet, là où tools.py les résolvait paresseusement
# dans ses globales : sans ces liaisons, un database_connector absent ou cassé
# rendrait `import tools` impossible alors que tools.py se contentait de
# désactiver la base. Aucune n'est jamais appelée dans ce cas, chaque usage
# étant gardé par `_db_available`.
is_database_available = None
search_formations_db = None
search_students_db = None
search_schedules_db = None
search_fees_db = None
search_news_announcements_db = None
get_statistics_db = None
get_official_stats_db = None
search_student_courses_db = None
verify_student_birthdate = None

try:
    from database_connector import (
        is_database_available,
        search_formations_db,
        search_students_db,
        search_schedules_db,
        search_fees_db,
        search_news_announcements_db,
        get_statistics_db,
        get_official_stats_db,
        search_student_courses_db,
        verify_student_birthdate,
    )
    _db_available = is_database_available()
except ImportError:
    _db_available = False
    logger.warning("Module database_connector non disponible")
except Exception as e:
    _db_available = False
    logger.error(f"Erreur lors de l'initialisation de la base de données : {e}")

# La table `announcements` n'existe que sur les backends documentaires
# (MongoDB). En SQLite, search_news_announcements_db retourne toujours [] :
# exposer l'outil ferait perdre un tour de boucle au LLM pour rien.
_db_backend_supporte_actualites = bool(_db_available) and (
    (os.getenv("UAM_DB_TYPE") or "").lower() == "mongodb"
)

# La table `horaires` n'existe dans aucun schéma SQL actuel (schema_scolarite_uam.sql,
# repris tel quel par database/simulation_scolarite.py — dont le docstring dit
# explicitement le schéma « compatible MySQL », donc partagé par SQLite/MySQL/
# PostgreSQL). Elle appartenait à un schéma antérieur abandonné
# (setup_database.py, qui cible un fichier différent, uam_database.db, non
# utilisé en production) et n'a jamais été reprise lors de la refonte du
# schéma réel. Sur les backends SQL, search_schedules_db exécute donc
# `SELECT * FROM horaires` contre une table absente : sqlite3.OperationalError
# loguée en ERROR à chaque appel (database_connector.py), en plus de l'outil
# systématiquement vide (BUG-11) — seul MongoDB interroge une collection
# `schedules` indépendante de ce schéma SQL.
_db_backend_supporte_horaires = bool(_db_available) and (
    (os.getenv("UAM_DB_TYPE") or "").lower() == "mongodb"
)

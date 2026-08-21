"""Accès à la base de données scolarité et drapeau de disponibilité.

`_db_available` est calculé une fois au chargement ; les outils qui interrogent
la base le lisent pour décider s'ils peuvent le faire.
"""
from logger_config import get_logger

logger = get_logger(__name__)

# Repli des neuf fonctions de database_connector. Les modules d'outils les
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
    )
    _db_available = is_database_available()
except ImportError:
    _db_available = False
    logger.warning("Module database_connector non disponible")
except Exception as e:
    _db_available = False
    logger.error(f"Erreur lors de l'initialisation de la base de données : {e}")

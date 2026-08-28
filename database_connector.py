"""
Module de connexion à la base de données UAM
Permet d'interroger une base de données pour obtenir des informations à jour
"""

import re
import threading
from typing import Optional, Dict, List, Any
from app_config import get_config
from logger_config import get_logger

# Charger les variables d'environnement
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = get_logger(__name__)

# Variable globale pour la connexion (protégée par un verrou)
_db_connection = None
_db_type = None
_db_lock = threading.Lock()


class DatabaseType:
    """Types de bases de données supportés"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"  # Pour les bases NoSQL


def get_db_connection():
    """
    Obtient une connexion à la base de données selon la configuration
    
    Returns:
        Objet de connexion à la base de données ou None si non configuré
    """
    global _db_connection, _db_type
    
    if _db_connection is not None:
        return _db_connection
    
    config = get_config()
    # Détecter le type de base de données depuis la configuration
    db_type = (config.database.db_type or "").lower()
    
    if not db_type:
        # Pas de base de données configurée
        return None
    
    try:
        if db_type == DatabaseType.POSTGRESQL:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            _db_connection = psycopg2.connect(
                host=config.database.db_host,
                port=config.database.db_port,
                database=config.database.db_name,
                user=config.database.db_user,
                password=config.database.db_password,
                cursor_factory=RealDictCursor
            )
            _db_type = DatabaseType.POSTGRESQL
            logger.info("Connexion PostgreSQL établie")
            
        elif db_type == DatabaseType.MYSQL:
            import mysql.connector

            _db_connection = mysql.connector.connect(
                host=config.database.db_host,
                port=int(config.database.db_port or "3306"),
                database=config.database.db_name,
                user=config.database.db_user or "root",
                password=config.database.db_password
            )
            _db_type = DatabaseType.MYSQL
            logger.info("Connexion MySQL établie")
            
        elif db_type == DatabaseType.SQLITE:
            import sqlite3
            
            db_path = config.database.db_path
            _db_connection = sqlite3.connect(db_path, check_same_thread=False)
            _db_connection.row_factory = sqlite3.Row  # Pour obtenir des dictionnaires
            _db_type = DatabaseType.SQLITE
            logger.info(f"Connexion SQLite établie : {db_path}")
            
        elif db_type == DatabaseType.MONGODB:
            from pymongo import MongoClient
            
            connection_string = config.database.connection_string or "mongodb://localhost:27017/"
            client = MongoClient(connection_string)
            db_name = config.database.db_name
            _db_connection = client[db_name]
            _db_type = DatabaseType.MONGODB
            logger.info("Connexion MongoDB établie")
            
        else:
            logger.warning(f"Type de base de données non supporté : {db_type}")
            return None

    except ImportError as e:
        logger.warning(
            f"Bibliothèque de base de données non installée : {e}. "
            "Installez psycopg2-binary (PostgreSQL), mysql-connector-python (MySQL) ou pymongo (MongoDB)."
        )
        return None
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données : {e}", exc_info=True)
        return None
    
    return _db_connection


def _prepare_query(query: str, params: Optional[Dict[str, Any]]):
    """
    Adapte les placeholders SQL selon le type de base de données.
    - SQLite: :name
    - PostgreSQL: %(name)s
    - MySQL: %s (ordre d'apparition)
    """
    if not params:
        return query, params

    if _db_type == DatabaseType.POSTGRESQL:
        query_prepared = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", r"%(\1)s", query)
        return query_prepared, params

    if _db_type == DatabaseType.MYSQL:
        ordered_keys: List[str] = []

        def _replace(match):
            ordered_keys.append(match.group(1))
            return "%s"

        query_prepared = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", _replace, query)
        values = [params[key] for key in ordered_keys]
        return query_prepared, values

    return query, params


def query_database(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Exécute une requête SQL sur la base de données (thread-safe).

    Args:
        query: Requête SQL à exécuter
        params: Paramètres pour la requête (optionnel)

    Returns:
        Liste de dictionnaires contenant les résultats
    """
    global _db_connection, _db_type

    if _db_connection is None:
        _db_connection = get_db_connection()

    if _db_connection is None:
        return []

    with _db_lock:
        try:
            if _db_type == DatabaseType.POSTGRESQL:
                cursor = _db_connection.cursor()
                prepared_query, prepared_params = _prepare_query(query, params)
                if prepared_params:
                    cursor.execute(prepared_query, prepared_params)
                else:
                    cursor.execute(prepared_query)
                results = cursor.fetchall()
                cursor.close()
                return [dict(row) for row in results]

            elif _db_type == DatabaseType.MYSQL:
                cursor = _db_connection.cursor(dictionary=True)
                prepared_query, prepared_params = _prepare_query(query, params)
                if prepared_params:
                    cursor.execute(prepared_query, prepared_params)
                else:
                    cursor.execute(prepared_query)
                results = cursor.fetchall()
                cursor.close()
                return results

            elif _db_type == DatabaseType.SQLITE:
                cursor = _db_connection.cursor()
                prepared_query, prepared_params = _prepare_query(query, params)
                if prepared_params:
                    cursor.execute(prepared_query, prepared_params)
                else:
                    cursor.execute(prepared_query)
                results = cursor.fetchall()
                cursor.close()
                return [dict(row) for row in results]

            elif _db_type == DatabaseType.MONGODB:
                if isinstance(query, dict):
                    collection_name = query.get("collection", "documents")
                    filter_query = query.get("filter", {})
                    projection = query.get("projection", None)
                    limit = query.get("limit", 100)

                    collection = _db_connection[collection_name]
                    results = list(collection.find(filter_query, projection).limit(limit))

                    for result in results:
                        if "_id" in result:
                            result["_id"] = str(result["_id"])

                    return results
                else:
                    logger.warning("Pour MongoDB, la requête doit être un dictionnaire")
                    return []

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la requête : {e}", exc_info=True)
            return []

    return []


def search_formations_db(faculty: Optional[str] = None, level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recherche les formations dans la base de données
    
    Args:
        faculty: Abréviation de la faculté (optionnel)
        level: Niveau d'étude (optionnel)
        
    Returns:
        Liste des formations trouvées
    """
    global _db_type
    
    if _db_type == DatabaseType.MONGODB:
        filter_query = {}
        if faculty:
            filter_query["faculty"] = faculty.upper()
        if level:
            filter_query["level"] = level.lower()
        
        return query_database({
            "collection": "formations",
            "filter": filter_query,
            "limit": 100
        })
    else:
        # SQL — schéma réel : formations → departements → composantes
        query = """
            SELECT
                f.id,
                f.intitule          AS name,
                f.niveau            AS level,
                f.type_formation,
                c.nom_complet       AS structure_nom,
                c.type_composante   AS structure_type,
                c.sigle             AS structure_sigle
            FROM formations f
            JOIN departements d ON f.departement_id = d.id
            JOIN composantes  c ON d.composante_id  = c.id
            WHERE 1=1
        """
        params = {}

        if faculty:
            query += " AND (c.sigle LIKE :faculty_pattern OR c.nom_complet LIKE :faculty_pattern2)"
            params["faculty_pattern"]  = f"%{faculty.upper()}%"
            params["faculty_pattern2"] = f"%{faculty}%"

        if level:
            query += " AND LOWER(f.niveau) = LOWER(:level)"
            params["level"] = level

        query += " ORDER BY c.nom_complet, f.niveau, f.intitule"

        return query_database(query, params)


def search_students_db(student_id: Optional[str] = None, 
                      faculty: Optional[str] = None,
                      level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recherche des étudiants dans la base de données
    
    Args:
        student_id: Numéro d'étudiant (optionnel)
        faculty: Abréviation de la faculté (optionnel)
        level: Niveau d'étude (optionnel)
        
    Returns:
        Liste des étudiants trouvés
    """
    global _db_type
    
    if _db_type == DatabaseType.MONGODB:
        filter_query = {}
        if student_id:
            filter_query["student_id"] = student_id
        if faculty:
            filter_query["faculty"] = faculty.upper()
        if level:
            filter_query["level"] = level.lower()
        
        return query_database({
            "collection": "students",
            "filter": filter_query,
            "limit": 100
        })
    else:
        # SQL — jointure etudiants + inscriptions (schéma scolarite_uam.db)
        # formations → departements → composantes (pas de lien direct formations.composante_id)
        query = """
            SELECT
                e.matricule        AS student_id,
                e.nom              AS last_name,
                e.prenom           AS first_name,
                e.telephone,
                e.email,
                e.type_etudiant,
                f.niveau           AS level,
                c.sigle            AS faculty_abbreviation,
                i.statut           AS inscription_status,
                i.annee_academique,
                i.date_inscription,
                i.numero_recu,
                COALESCE((
                    SELECT SUM(p.montant)
                    FROM paiements p
                    WHERE p.inscription_id = i.id
                ), 0) AS fees_paid
            FROM etudiants e
            LEFT JOIN inscriptions i ON i.etudiant_id = e.id
            LEFT JOIN formations f   ON f.id = i.formation_id
            LEFT JOIN departements d ON d.id = f.departement_id
            LEFT JOIN composantes c  ON c.id = d.composante_id
            WHERE 1=1
        """
        params = {}

        if student_id:
            query += " AND e.matricule = :student_id"
            params["student_id"] = student_id

        if faculty:
            query += " AND c.sigle = :faculty"
            params["faculty"] = faculty.upper()

        if level:
            query += " AND LOWER(f.niveau) = :level"
            params["level"] = level.lower()

        query += " ORDER BY e.nom, e.prenom LIMIT 100"

        return query_database(query, params)


_MOIS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}


def _normaliser_date(valeur: Any) -> Optional[tuple]:
    """Ramène une date écrite de plusieurs façons à un triplet (année, mois, jour).

    L'utilisateur tape sa date de naissance comme il la dit — « 05/05/2003 »,
    « 5 mai 2003 » — pas au format de la base (« 2003-05-05 »). Refuser ces
    formes rendrait le second facteur de `verify_student_birthdate`
    inutilisable en pratique, donc pousserait tôt ou tard à le retirer.

    Retourne None si la saisie n'est reconnue par aucune forme : l'appelant
    traite ce cas comme un échec de vérification, jamais comme un succès.
    """
    if valeur is None:
        return None

    texte = str(valeur).strip().lower()
    if not texte:
        return None

    # Format de la base : AAAA-MM-JJ (éventuellement suivi d'une heure)
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", texte)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Formats usuels : JJ/MM/AAAA, JJ-MM-AAAA, JJ.MM.AAAA (zéro initial facultatif)
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", texte)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))

    # Mois en toutes lettres : « 5 mai 2003 », « 05 mai 2003 »
    m = re.match(r"^(\d{1,2})\s+([a-zéûôà]+)\s+(\d{4})$", texte)
    if m and m.group(2) in _MOIS_FR:
        return (int(m.group(3)), _MOIS_FR[m.group(2)], int(m.group(1)))

    return None


def verify_student_birthdate(student_id: str, date_saisie: str) -> bool:
    """Vérifie la date de naissance d'un étudiant — SEC-01, second facteur.

    Renvoie un **booléen**, jamais la date : c'est délibéré. La valeur ne
    circule donc pas dans les dictionnaires que les outils formatent, et
    aucun outil futur ne peut l'imprimer par inadvertance. Pour la même
    raison, `search_students_db` ne la rapatrie pas.

    Renvoie False dans tous les cas d'échec — matricule inconnu, date
    absente, date illisible, date qui ne correspond pas — sans les
    distinguer : l'appelant ne doit pas pouvoir s'en servir comme oracle
    d'énumération des matricules.

    Args:
        student_id: matricule de l'étudiant
        date_saisie: date de naissance telle que saisie par l'utilisateur

    Returns:
        True si et seulement si la date correspond au dossier
    """
    global _db_type

    attendue_saisie = _normaliser_date(date_saisie)
    if attendue_saisie is None or not student_id:
        return False

    try:
        if _db_type == DatabaseType.MONGODB:
            lignes = query_database({
                "collection": "students",
                "filter": {"student_id": student_id},
                "limit": 1,
            })
            valeur = lignes[0].get("date_naissance") if lignes else None
        else:
            lignes = query_database(
                "SELECT date_naissance FROM etudiants WHERE matricule = :m LIMIT 1",
                {"m": student_id},
            )
            valeur = lignes[0].get("date_naissance") if lignes else None
    except Exception as e:
        # Fail-closed : une erreur de base ne doit pas ouvrir le dossier.
        logger.error(f"Erreur lors de la vérification du second facteur : {e}")
        return False

    enregistree = _normaliser_date(valeur)
    if enregistree is None:
        # Dossier sans date de naissance : pas de second facteur possible,
        # donc pas d'accès. Fail-closed, là encore.
        return False

    return enregistree == attendue_saisie


def search_schedules_db(faculty: Optional[str] = None,
                        filiere: Optional[str] = None,
                        level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recherche les horaires/emplois du temps dans la base de données
    
    Args:
        faculty: Abréviation de la faculté (optionnel)
        filiere: Nom de la filière (optionnel)
        level: Niveau d'étude (optionnel)
        
    Returns:
        Liste des horaires trouvés
    """
    global _db_type
    
    if _db_type == DatabaseType.MONGODB:
        filter_query = {}
        if faculty:
            filter_query["faculty"] = faculty.upper()
        if filiere:
            filter_query["filiere"] = filiere
        if level:
            filter_query["level"] = level.lower()
        
        return query_database({
            "collection": "schedules",
            "filter": filter_query,
            "limit": 100
        })
    else:
        # SQL - Nouveau schéma avec table horaires
        query = "SELECT * FROM horaires WHERE 1=1"
        params = {}
        
        if faculty:
            # Rechercher dans le champ service qui peut contenir le nom de la faculté
            query += " AND (LOWER(service) LIKE :faculty_pattern OR LOWER(notes) LIKE :faculty_pattern2)"
            params["faculty_pattern"] = f"%{faculty.lower()}%"
            params["faculty_pattern2"] = f"%{faculty.lower()}%"
        
        query += " ORDER BY service, heures_ouverture"
        
        results = query_database(query, params)
        
        # Transformer les résultats pour compatibilité
        transformed_results = []
        for row in results:
            transformed = {
                "service": row.get("service", ""),
                "jours": row.get("jours", ""),
                "heures_ouverture": row.get("heures_ouverture", ""),
                "heures_fermeture": row.get("heures_fermeture", ""),
                "notes": row.get("notes", ""),
                "start_time": row.get("heures_ouverture", ""),
                "end_time": row.get("heures_fermeture", ""),
                "day_of_week": row.get("jours", "")
            }
            transformed_results.append(transformed)
        
        return transformed_results


def search_fees_db(level: Optional[str] = None, 
                   faculty: Optional[str] = None,
                   year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Recherche les frais de scolarité dans la base de données
    
    Args:
        level: Niveau d'étude (optionnel)
        faculty: Abréviation de la faculté (optionnel)
        year: Année académique (optionnel)
        
    Returns:
        Liste des frais trouvés
    """
    global _db_type
    
    if _db_type == DatabaseType.MONGODB:
        filter_query = {}
        if level:
            filter_query["level"] = level.lower()
        if faculty:
            filter_query["faculty"] = faculty.upper()
        if year:
            filter_query["academic_year"] = year
        
        return query_database({
            "collection": "fees",
            "filter": filter_query,
            "limit": 50
        })
    else:
        # SQLite : interroger la table frais_formations
        conn = get_db_connection()
        if conn is None:
            return []
        try:
            cur = conn.cursor()
            query = "SELECT * FROM frais_formations WHERE 1=1"
            params: list = []
            if level:
                lvl = level.strip().capitalize()
                # Accepter "licence"/"L1"/"L2"/"L3" → "Licence", "master"/"M1"/"M2" → "Master"
                if lvl.upper() in ("L1", "L2", "L3"):
                    lvl = "Licence"
                elif lvl.upper() in ("M1", "M2"):
                    lvl = "Master"
                query += " AND LOWER(niveau) = LOWER(?)"
                params.append(lvl)
            if faculty:
                query += " AND (composante_sigle = '' OR UPPER(composante_sigle) = UPPER(?))"
                params.append(faculty)
            query += " ORDER BY niveau, type_frais, nationalite"
            cur.execute(query, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            # Renommer les colonnes pour compatibilité avec calculate_fees
            result = []
            for row in rows:
                result.append({
                    "level": row.get("niveau", ""),
                    "type_inscription": row.get("type_frais", ""),
                    "nationalite": row.get("nationalite", "uemoa"),
                    "composante_sigle": row.get("composante_sigle", ""),
                    "frais_inscription": row.get("montant_indicatif") if row.get("type_frais") == "inscription" else None,
                    "frais_scolarite": row.get("montant_indicatif") if row.get("type_frais") == "scolarite" else None,
                    "frais_labo": None,
                    "montant_min": row.get("montant_min"),
                    "montant_max": row.get("montant_max"),
                    "montant_indicatif": row.get("montant_indicatif"),
                    "devise": row.get("devise", "FCFA"),
                    "notes": row.get("notes", ""),
                    "source": row.get("source", "officiel_uam"),
                    "annee_reference": row.get("annee_reference", "2024-2025"),
                })
            return result
        except Exception:
            return []


def search_news_announcements_db(limit: int = 10, 
                                category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recherche les actualités et annonces dans la base de données
    
    Args:
        limit: Nombre maximum de résultats
        category: Catégorie d'annonce (optionnel)
        
    Returns:
        Liste des actualités/annonces trouvées
    """
    global _db_type
    
    if _db_type == DatabaseType.MONGODB:
        filter_query = {}
        if category:
            filter_query["category"] = category
        
        return query_database({
            "collection": "announcements",
            "filter": filter_query,
            "limit": limit
        })
    else:
        # La table 'announcements' n'existe pas dans scolarite_uam.db.
        # On retourne [] — l'agent bascule sur les documents RAG pour les actualités.
        return []


def get_official_stats_db(
    faculty: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retourne les statistiques officielles (étudiants + enseignants-chercheurs + PAT)
    depuis la table statistiques_composantes, issue des documents officiels UAM.

    Args:
        faculty: Sigle de la composante — None = toutes
    """
    query = """
        SELECT
            c.sigle            AS faculty,
            c.nom_complet      AS faculty_name,
            s.annee_reference,
            s.nb_etudiants,
            s.nb_enseignants_chercheurs,
            s.dont_rang_a,
            s.nb_vacataires,
            s.nb_pat,
            s.source
        FROM statistiques_composantes s
        JOIN composantes c ON c.id = s.composante_id
        WHERE 1=1
    """
    params: Dict[str, Any] = {}
    if faculty:
        query += " AND UPPER(c.sigle) = :faculty"
        params["faculty"] = faculty.upper()
    query += " ORDER BY c.sigle, s.annee_reference DESC"
    return query_database(query, params)


def get_statistics_db(
    faculty: Optional[str] = None,
    level: Optional[str] = None,
    year: str = "2024-2025",
) -> List[Dict[str, Any]]:
    """
    Retourne les effectifs d'étudiants inscrits, agrégés par composante et/ou niveau.

    Args:
        faculty: Sigle de la composante (FAST, FLSH…) — None = toutes
        level:   Niveau (L1, L2, L3, M1, M2…) — None = tous
        year:    Année académique (défaut : 2024-2025)
    """
    query = """
        SELECT
            c.sigle            AS faculty,
            c.nom_complet      AS faculty_name,
            f.niveau           AS level,
            COUNT(i.id)        AS effectif
        FROM inscriptions i
        JOIN formations   f ON f.id = i.formation_id
        JOIN departements d ON d.id = f.departement_id
        JOIN composantes  c ON c.id = d.composante_id
        WHERE i.annee_academique = :year
    """
    params: Dict[str, Any] = {"year": year}
    if faculty:
        query += " AND UPPER(c.sigle) = :faculty"
        params["faculty"] = faculty.upper()
    if level:
        query += " AND LOWER(f.niveau) = :level"
        params["level"] = level.lower()
    query += " GROUP BY c.sigle, c.nom_complet, f.niveau ORDER BY c.sigle, f.niveau"
    return query_database(query, params)


def search_student_courses_db(
    student_id: str,
    year: str = "2024-2025",
) -> List[Dict[str, Any]]:
    """
    Retourne les unités d'enseignement (cours) auxquelles un étudiant est inscrit,
    avec le statut et la note finale si disponibles.

    Args:
        student_id: Matricule de l'étudiant (ex: UAM050023)
        year:       Année académique (défaut : 2024-2025)
    """
    query = """
        SELECT
            ue.code_ue,
            ue.intitule,
            ue.credits_ects,
            ue.semestre,
            ue.type_ue,
            COALESCE(r.statut_ue, 'non_renseigne') AS statut_ue,
            r.note_finale
        FROM etudiants e
        JOIN inscriptions          i  ON i.etudiant_id  = e.id
        JOIN unites_enseignement   ue ON ue.formation_id = i.formation_id
        LEFT JOIN resultats        r  ON r.ue_id = ue.id AND r.inscription_id = i.id
        WHERE e.matricule          = :student_id
          AND i.annee_academique   = :year
        ORDER BY ue.semestre, ue.id
    """
    return query_database(query, {"student_id": student_id.upper(), "year": year})


def is_database_available() -> bool:
    """
    Vérifie si la base de données est disponible ET que son schéma est initialisé.

    Finding 3 (revue finale de branche) : tester seulement l'existence d'un
    objet connexion ment sur une installation neuve. `sqlite3.connect()`
    **crée** le fichier cible s'il est absent — sur un clone qui reprend
    `.env.example` (lequel pose `UAM_DB_TYPE=sqlite`), c'est le cas nominal.
    La connexion « réussit » donc sur une base vide sans la moindre table,
    `is_database_available()` renvoyait `True`, `search_student_record`
    était exposé et annoncé au LLM, et chaque requête réelle journalisait une
    `OperationalError` en ERROR.

    La disponibilité est donc mesurée par une sonde de schéma bon marché — une
    requête qui échoue si les tables/collections attendues n'existent pas —
    plutôt que par l'existence de la connexion. Cette fonction est appelée au
    niveau module par `tools/_db.py` : la sonde ne doit jamais lever, une
    erreur inattendue vaut indisponibilité, pas une exception qui remonterait
    jusqu'à l'import du paquet `tools`.

    Returns:
        True si la base de données est configurée, accessible, et que son
        schéma attendu (table `etudiants` en SQL, ping serveur en MongoDB)
        est bien initialisé.
    """
    global _db_connection, _db_type

    if _db_connection is None:
        _db_connection = get_db_connection()

    if _db_connection is None:
        return False

    try:
        if _db_type == DatabaseType.MONGODB:
            # `_db_connection[collection].find(...)` réussirait aussi
            # silencieusement sur une collection absente (même piège que
            # sqlite3.connect() sur un fichier absent) : on sonde plutôt le
            # serveur lui-même, sans dépendre d'une collection précise.
            _db_connection.client.admin.command("ping")
        else:
            cursor = _db_connection.cursor()
            try:
                cursor.execute("SELECT 1 FROM etudiants LIMIT 1")
                cursor.fetchone()
            finally:
                cursor.close()
        return True
    except Exception as e:
        # PostgreSQL laisse la transaction courante en état « aborted »
        # après une requête en échec : sans rollback, les appels réels
        # suivants sur cette même connexion échoueraient aussi, même si le
        # schéma est en réalité valide (faux négatif en cascade). Sans effet
        # sur SQLite/MySQL (autocommit), donc inconditionnel et sans risque.
        try:
            _db_connection.rollback()
        except Exception:
            pass
        logger.debug(f"Sonde de disponibilité de la base échouée (schéma absent ou base injoignable) : {e}")
        return False


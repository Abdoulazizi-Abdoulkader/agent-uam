"""
Module de connexion à la base de données UAM
Permet d'interroger une base de données pour obtenir des informations à jour
"""

import os
import re
import threading
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
import json
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
            from mysql.connector import Error
            
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
    Exécute une requête SQL sur la base de données
    
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
            # Convertir les RealDictRow en dictionnaires
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
            # Convertir les Row en dictionnaires
            return [dict(row) for row in results]
            
        elif _db_type == DatabaseType.MONGODB:
            # Pour MongoDB, la requête doit être un dictionnaire
            if isinstance(query, dict):
                collection_name = query.get("collection", "documents")
                filter_query = query.get("filter", {})
                projection = query.get("projection", None)
                limit = query.get("limit", 100)
                
                collection = _db_connection[collection_name]
                results = list(collection.find(filter_query, projection).limit(limit))
                
                # Convertir ObjectId en string pour la sérialisation JSON
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
        # La table 'scolarite' n'existe pas dans scolarite_uam.db.
        # Les frais sont gérés par les données statiques de tools.py.
        # On retourne [] pour que l'agent bascule sur le fallback RAG/statique.
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


def is_database_available() -> bool:
    """
    Vérifie si la base de données est disponible
    
    Returns:
        True si la base de données est configurée et accessible
    """
    global _db_connection
    
    if _db_connection is None:
        _db_connection = get_db_connection()
    
    return _db_connection is not None


def close_db_connection():
    """Ferme la connexion à la base de données"""
    global _db_connection, _db_type
    
    if _db_connection is not None:
        try:
            if _db_type == DatabaseType.POSTGRESQL or _db_type == DatabaseType.MYSQL:
                _db_connection.close()
            elif _db_type == DatabaseType.SQLITE:
                _db_connection.close()
            elif _db_type == DatabaseType.MONGODB:
                _db_connection.client.close()
            
            _db_connection = None
            _db_type = None
            logger.info("Connexion à la base de données fermée")
        except Exception as e:
            logger.warning(f"Erreur lors de la fermeture de la connexion : {e}")


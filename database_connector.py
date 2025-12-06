"""
Module de connexion à la base de données UAM
Permet d'interroger une base de données pour obtenir des informations à jour
"""

import os
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
import json

# Charger les variables d'environnement
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Variable globale pour la connexion
_db_connection = None
_db_type = None


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
    
    # Détecter le type de base de données depuis les variables d'environnement
    db_type = os.getenv("UAM_DB_TYPE", "").lower()
    
    if not db_type:
        # Pas de base de données configurée
        return None
    
    try:
        if db_type == DatabaseType.POSTGRESQL:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            _db_connection = psycopg2.connect(
                host=os.getenv("UAM_DB_HOST", "localhost"),
                port=os.getenv("UAM_DB_PORT", "5432"),
                database=os.getenv("UAM_DB_NAME", "uam_db"),
                user=os.getenv("UAM_DB_USER", "postgres"),
                password=os.getenv("UAM_DB_PASSWORD", ""),
                cursor_factory=RealDictCursor
            )
            _db_type = DatabaseType.POSTGRESQL
            print("✅ Connexion PostgreSQL établie")
            
        elif db_type == DatabaseType.MYSQL:
            import mysql.connector
            from mysql.connector import Error
            
            _db_connection = mysql.connector.connect(
                host=os.getenv("UAM_DB_HOST", "localhost"),
                port=int(os.getenv("UAM_DB_PORT", "3306")),
                database=os.getenv("UAM_DB_NAME", "uam_db"),
                user=os.getenv("UAM_DB_USER", "root"),
                password=os.getenv("UAM_DB_PASSWORD", "")
            )
            _db_type = DatabaseType.MYSQL
            print("✅ Connexion MySQL établie")
            
        elif db_type == DatabaseType.SQLITE:
            import sqlite3
            
            db_path = os.getenv("UAM_DB_PATH", "./uam_database.db")
            _db_connection = sqlite3.connect(db_path, check_same_thread=False)
            _db_connection.row_factory = sqlite3.Row  # Pour obtenir des dictionnaires
            _db_type = DatabaseType.SQLITE
            print(f"✅ Connexion SQLite établie : {db_path}")
            
        elif db_type == DatabaseType.MONGODB:
            from pymongo import MongoClient
            
            connection_string = os.getenv("UAM_DB_CONNECTION_STRING", 
                                         "mongodb://localhost:27017/")
            client = MongoClient(connection_string)
            db_name = os.getenv("UAM_DB_NAME", "uam_db")
            _db_connection = client[db_name]
            _db_type = DatabaseType.MONGODB
            print("✅ Connexion MongoDB établie")
            
        else:
            print(f"⚠️ Type de base de données non supporté : {db_type}")
            return None
            
    except ImportError as e:
        print(f"⚠️ Bibliothèque de base de données non installée : {e}")
        print("   Installez-la avec : pip install psycopg2-binary (PostgreSQL)")
        print("                      pip install mysql-connector-python (MySQL)")
        print("                      pip install pymongo (MongoDB)")
        return None
    except Exception as e:
        print(f"❌ Erreur de connexion à la base de données : {e}")
        return None
    
    return _db_connection


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
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            # Convertir les RealDictRow en dictionnaires
            return [dict(row) for row in results]
            
        elif _db_type == DatabaseType.MYSQL:
            cursor = _db_connection.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
            
        elif _db_type == DatabaseType.SQLITE:
            cursor = _db_connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
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
                print("⚠️ Pour MongoDB, la requête doit être un dictionnaire")
                return []
                
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution de la requête : {e}")
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
        # SQL - Nouveau schéma avec jointure sur structures
        query = """
            SELECT 
                f.id,
                f.nom as name,
                f.niveau as level,
                f.conditions_acces,
                f.pieces_requises,
                f.objectifs,
                s.nom as structure_nom,
                s.type as structure_type
            FROM formations f
            JOIN structures s ON f.structure_id = s.id
            WHERE 1=1
        """
        params = {}
        
        if faculty:
            # Rechercher par nom ou abréviation de la structure
            query += " AND (s.nom LIKE :faculty_pattern OR s.nom LIKE :faculty_pattern2)"
            params["faculty_pattern"] = f"%{faculty}%"
            params["faculty_pattern2"] = f"%{faculty.upper()}%"
        
        if level:
            query += " AND LOWER(f.niveau) = LOWER(:level)"
            params["level"] = level
        
        query += " ORDER BY s.nom, f.niveau, f.nom"
        
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
        # SQL
        query = "SELECT * FROM students WHERE 1=1"
        params = {}
        
        if student_id:
            query += " AND student_id = :student_id"
            params["student_id"] = student_id
        
        if faculty:
            query += " AND faculty_abbreviation = :faculty"
            params["faculty"] = faculty.upper()
        
        if level:
            query += " AND level = :level"
            params["level"] = level.lower()
        
        query += " ORDER BY last_name, first_name"
        
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
        # SQL - Nouveau schéma avec table scolarite
        query = "SELECT * FROM scolarite WHERE 1=1"
        params = {}
        
        if level:
            # Rechercher dans le champ niveau qui peut contenir "Licence", "Master", etc.
            query += " AND (LOWER(niveau) LIKE :level_pattern OR LOWER(niveau) LIKE :level_pattern2)"
            params["level_pattern"] = f"%{level.lower()}%"
            params["level_pattern2"] = f"%{level.lower()}%"
        
        if faculty:
            # Rechercher dans le champ niveau qui peut contenir le nom de la faculté
            query += " AND (LOWER(niveau) LIKE :faculty_pattern)"
            params["faculty_pattern"] = f"%{faculty.lower()}%"
        
        query += " ORDER BY niveau, type_inscription"
        
        results = query_database(query, params)
        
        # Transformer les résultats pour compatibilité
        transformed_results = []
        for row in results:
            transformed = {
                "level": row.get("niveau", ""),
                "type_inscription": row.get("type_inscription", ""),
                "frais_inscription": row.get("frais_inscription", 0),
                "frais_scolarite": row.get("frais_scolarite", 0),
                "frais_labo": row.get("frais_labo", 0),
                "periode": row.get("periode", ""),
                "amount": row.get("frais_inscription", 0) + row.get("frais_scolarite", 0) + row.get("frais_labo", 0)
            }
            transformed_results.append(transformed)
        
        return transformed_results


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
        # SQL
        query = "SELECT * FROM announcements WHERE 1=1"
        params = {}
        
        if category:
            query += " AND category = :category"
            params["category"] = category
        
        query += " ORDER BY published_date DESC LIMIT :limit"
        params["limit"] = limit
        
        return query_database(query, params)


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
            print("✅ Connexion à la base de données fermée")
        except Exception as e:
            print(f"⚠️ Erreur lors de la fermeture de la connexion : {e}")


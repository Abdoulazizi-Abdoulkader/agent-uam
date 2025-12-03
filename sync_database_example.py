"""
Exemple de script de synchronisation de la base de données
Ce script peut être exécuté périodiquement pour mettre à jour les données
"""

import json
from datetime import datetime
from database_connector import get_db_connection, query_database, DatabaseType
import os

def sync_formations():
    """Synchronise les formations depuis un fichier JSON ou une API"""
    # Exemple avec un fichier JSON
    json_file = "data/formations.json"
    
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} non trouvé")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        formations = json.load(f)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Impossible de se connecter à la base de données")
        return
    
    db_type = os.getenv("UAM_DB_TYPE", "").lower()
    
    for formation in formations:
        if db_type == DatabaseType.MONGODB:
            # Pour MongoDB
            collection = conn["formations"]
            formation["updated_at"] = datetime.now()
            collection.update_one(
                {
                    "name": formation["name"],
                    "faculty": formation["faculty"],
                    "level": formation["level"]
                },
                {"$set": formation},
                upsert=True
            )
        else:
            # Pour SQL
            query = """
                INSERT INTO formations (name, faculty_abbreviation, level, description, duration_years, updated_at)
                VALUES (:name, :faculty, :level, :description, :duration, :updated_at)
                ON CONFLICT (name, faculty_abbreviation, level) 
                DO UPDATE SET 
                    description = EXCLUDED.description,
                    duration_years = EXCLUDED.duration_years,
                    updated_at = EXCLUDED.updated_at
            """
            formation["updated_at"] = datetime.now()
            query_database(query, formation)
    
    print(f"✅ {len(formations)} formations synchronisées")


def sync_fees():
    """Synchronise les frais de scolarité"""
    json_file = "data/fees.json"
    
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} non trouvé")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        fees = json.load(f)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Impossible de se connecter à la base de données")
        return
    
    db_type = os.getenv("UAM_DB_TYPE", "").lower()
    
    for fee in fees:
        if db_type == DatabaseType.MONGODB:
            collection = conn["fees"]
            fee["updated_at"] = datetime.now()
            collection.update_one(
                {
                    "level": fee["level"],
                    "faculty": fee.get("faculty"),
                    "academic_year": fee["academic_year"]
                },
                {"$set": fee},
                upsert=True
            )
        else:
            query = """
                INSERT INTO fees (level, faculty_abbreviation, amount, academic_year, description, updated_at)
                VALUES (:level, :faculty, :amount, :academic_year, :description, :updated_at)
                ON CONFLICT (level, faculty_abbreviation, academic_year) 
                DO UPDATE SET 
                    amount = EXCLUDED.amount,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
            """
            fee["updated_at"] = datetime.now()
            query_database(query, fee)
    
    print(f"✅ {len(fees)} tarifs synchronisés")


def sync_announcements():
    """Synchronise les annonces depuis une source externe"""
    # Exemple : récupérer depuis une API ou un fichier
    json_file = "data/announcements.json"
    
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} non trouvé")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        announcements = json.load(f)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Impossible de se connecter à la base de données")
        return
    
    db_type = os.getenv("UAM_DB_TYPE", "").lower()
    
    for announcement in announcements:
        if db_type == DatabaseType.MONGODB:
            collection = conn["announcements"]
            announcement["created_at"] = datetime.now()
            announcement["updated_at"] = datetime.now()
            collection.update_one(
                {"title": announcement["title"], "published_date": announcement["published_date"]},
                {"$set": announcement},
                upsert=True
            )
        else:
            query = """
                INSERT INTO announcements (title, content, category, published_date, expiry_date, link, target_faculty, updated_at)
                VALUES (:title, :content, :category, :published_date, :expiry_date, :link, :target_faculty, :updated_at)
                ON CONFLICT (title, published_date) 
                DO UPDATE SET 
                    content = EXCLUDED.content,
                    category = EXCLUDED.category,
                    expiry_date = EXCLUDED.expiry_date,
                    link = EXCLUDED.link,
                    updated_at = EXCLUDED.updated_at
            """
            announcement["updated_at"] = datetime.now()
            query_database(query, announcement)
    
    print(f"✅ {len(announcements)} annonces synchronisées")


if __name__ == "__main__":
    print("🔄 Début de la synchronisation...")
    print(f"⏰ {datetime.now()}")
    print()
    
    sync_formations()
    sync_fees()
    sync_announcements()
    
    print()
    print("✅ Synchronisation terminée")


"""
Outils (Tools) pour l'agent conversationnel UAM
Tous les outils disponibles pour la recherche et l'interaction
"""
import json
from datetime import datetime
from langchain_core.tools import tool
from langchain_community.vectorstores import FAISS
from uam_structures import (
    get_structure_info,
    detect_structure_in_text,
    UAM_STRUCTURES,
    list_all_structures_internal
)
from memory import _user_memory

# Variables globales
_vectorstore = None

# Import du module de connexion à la base de données
try:
    from database_connector import (
        is_database_available,
        search_formations_db,
        search_students_db,
        search_schedules_db,
        search_fees_db,
        search_news_announcements_db,
        query_database
    )
    _db_available = is_database_available()
except ImportError:
    _db_available = False
    print(" Module database_connector non disponible")
except Exception as e:
    _db_available = False
    print(f" Erreur lors de l'initialisation de la base de données : {e}")


def set_vectorstore(vectorstore: FAISS):
    """Définit le vectorstore global pour les outils"""
    global _vectorstore
    _vectorstore = vectorstore
    # Mettre à jour aussi agent_uam._vectorstore si le module est importé
    try:
        import agent_uam
        if hasattr(agent_uam, '_vectorstore'):
            agent_uam._vectorstore = vectorstore
    except (ImportError, AttributeError):
        pass  # Le module n'est pas encore importé ou n'a pas l'attribut


# ==================== OUTILS (TOOLS) ====================


@tool
def search_uam_knowledge(query: str) -> str:
    """
    Recherche des informations dans la base de connaissances de l'UAM.
    Comprend automatiquement les abréviations (ex: FAST, FLSH, ENS, etc.).
    
    Args:
        query: La question ou le terme à rechercher dans les documents UAM.
               Peut contenir des abréviations comme FAST, FLSH, ENS, etc.
        
    Returns:
        Le contexte pertinent trouvé dans les documents
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Détecter et remplacer les abréviations par leurs noms complets pour améliorer la recherche
    query_expanded = query
    detected_structures = detect_structure_in_text(query)
    
    if detected_structures:
        # Ajouter les noms complets des structures détectées à la requête
        structure_names = [s["nom_complet"] for s in detected_structures]
        query_expanded = f"{query} {' '.join(structure_names)}"
    
    # Recherche sémantique avec la requête enrichie
    docs = _vectorstore.similarity_search(query_expanded, k=4)
    
    # Combiner les documents
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    return context if context else "Aucune information trouvée pour cette requête."


@tool
def detect_greeting(message: str) -> str:
    """
    Détecte si le message de l'utilisateur est une salutation ou une formule de politesse.
    
    Args:
        message: Le message de l'utilisateur
        
    Returns:
        "GREETING" si c'est une salutation, "QUESTION" si c'est une question, "BOTH" si les deux
    """
    message_lower = message.lower().strip()
    
    # Salutations courantes
    greetings = [
        "bonjour", "bonsoir", "salut", "bonne journée", "bonne soirée",
        "bonne nuit", "coucou", "hey", "hi", "hello", "bon matin",
        "bon après-midi", "à bientôt", "au revoir", "adieu",
        "merci", "merci beaucoup", "merci bien", "je vous remercie",
        "s'il vous plaît", "s'il te plaît", "svp", "stp",
        "excusez-moi", "excuse-moi", "pardon", "désolé", "désolée"
    ]
    
    # Vérifier si le message contient une salutation
    is_greeting = any(greeting in message_lower for greeting in greetings)
    
    # Vérifier si c'est une question (contient des mots-clés de question)
    question_keywords = ["?", "quoi", "comment", "pourquoi", "quand", "où", "qui", "quel", "quelle", "quels", "quelles"]
    is_question = any(keyword in message_lower for keyword in question_keywords) or "?" in message
    
    # Vérifier si le message contient des mots-clés UAM (pour savoir si c'est une vraie question)
    uam_keywords = ["uam", "université", "faculté", "école", "institut", "formation", "inscription", "admission", "diplôme", "fast", "flsh", "fseg", "fsjp", "fa", "fss", "ens"]
    has_uam_content = any(keyword in message_lower for keyword in uam_keywords)
    
    if is_greeting and (is_question or has_uam_content):
        return "BOTH"
    elif is_greeting:
        return "GREETING"
    elif is_question or has_uam_content:
        return "QUESTION"
    else:
        return "QUESTION"  # Par défaut, traiter comme une question


@tool
def check_question_relevance(question: str) -> str:
    """
    Vérifie si une question concerne l'Université Abdou Moumouni de Niamey.
    
    Args:
        question: La question de l'utilisateur
        
    Returns:
        "PERTINENT" si la question concerne l'UAM, "HORS_SUJET" sinon
    """
    keywords_uam = [
        "uam", "université", "abdou moumouni", "niamey", "niger",
        "faculté", "école", "institut", "formation", "filière",
        "inscription", "admission", "diplôme", "attestation", "relevé",
        "scolarité", "étudiant", "licence", "master", "doctorat",
        "cours", "horaire", "service", "recteur", "doyen"
    ]
    
    question_lower = question.lower()
    
    # Vérifier si la question contient des mots-clés UAM
    for keyword in keywords_uam:
        if keyword in question_lower:
            return "PERTINENT"
    
    # Questions générales sur l'éducation peuvent être pertinentes
    education_keywords = ["comment s'inscrire", "quelles formations", "quel diplôme"]
    for keyword in education_keywords:
        if keyword in question_lower:
            return "PERTINENT"
    
    return "HORS_SUJET"


@tool
def calculate_fees(level: str, faculty: str = "") -> str:
    """
    Calcule les frais de scolarité selon le niveau et la faculté.
    Utilise la base de données si disponible pour obtenir les tarifs à jour.
    
    Args:
        level: Niveau d'étude (licence, master, doctorat)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les frais de scolarité (à jour si BD disponible)
    """
    results_parts = []
    
    # 1. Recherche dans la base de données (si disponible)
    if _db_available:
        try:
            # Détecter l'abréviation de la faculté si nécessaire
            faculty_abbrev = None
            if faculty:
                structure_info = get_structure_info(faculty)
                if structure_info:
                    faculty_abbrev = structure_info["abreviation"]
                else:
                    faculty_abbrev = faculty.upper()
            
            # Obtenir l'année académique actuelle
            current_year = datetime.now().year
            
            db_results = search_fees_db(level=level, faculty=faculty_abbrev, year=current_year)
            
            if db_results:
                results_parts.append("💰 FRAIS DE SCOLARITÉ À JOUR (BASE DE DONNÉES) :")
                results_parts.append("")
                for fee in db_results[:5]:  # Limiter à 5 résultats
                    fee_info = []
                    if "level" in fee:
                        fee_info.append(f"Niveau : {fee['level'].capitalize()}")
                    if "faculty" in fee:
                        fee_info.append(f"Faculté : {fee['faculty']}")
                    if "amount" in fee:
                        fee_info.append(f"Montant : {fee['amount']:,} FCFA")
                    if "academic_year" in fee:
                        fee_info.append(f"Année académique : {fee['academic_year']}")
                    if "description" in fee:
                        fee_info.append(f"Description : {fee['description']}")
                    
                    results_parts.append("\n".join(fee_info))
                    results_parts.append("---")
                    results_parts.append("")
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche dans la base de données : {e}")
    
    # 2. Tarifs de base (fallback si pas de BD ou pas de résultats)
    if not results_parts:
        fees_base = {
            "licence": {
                "base": 50000,  # FCFA
                "description": "Frais de scolarité pour la Licence"
            },
            "master": {
                "base": 75000,  # FCFA
                "description": "Frais de scolarité pour le Master"
            },
            "doctorat": {
                "base": 100000,  # FCFA
                "description": "Frais de scolarité pour le Doctorat"
            }
        }
        
        level_lower = level.lower()
        
        if level_lower in fees_base:
            info = fees_base[level_lower]
            results_parts.append(f" {info['description']}: {info['base']:,} FCFA par an")
            if faculty:
                results_parts.append(f"Faculté: {faculty}")
            results_parts.append("\n Note: Ces tarifs sont indicatifs. Veuillez contacter le service de scolarité pour les tarifs exacts.")
        else:
            return f"Niveau '{level}' non reconnu. Niveaux disponibles: licence, master, doctorat"
    
    return "\n".join(results_parts)


@tool
def search_formations(faculty: str = "", level: str = "") -> str:
    """
    Recherche les formations disponibles selon la faculté et le niveau.
    Combine les résultats de la base de données (si disponible) et des documents.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        level: Niveau d'étude (licence, master, doctorat) - optionnel
        
    Returns:
        Liste des formations disponibles avec informations à jour
    """
    results_parts = []
    
    # 1. Recherche dans la base de données (si disponible)
    if _db_available:
        try:
            # Détecter l'abréviation de la faculté si nécessaire
            faculty_abbrev = None
            if faculty:
                structure_info = get_structure_info(faculty)
                if structure_info:
                    faculty_abbrev = structure_info["abreviation"]
                else:
                    faculty_abbrev = faculty.upper()
            
            db_results = search_formations_db(faculty=faculty_abbrev, level=level)
            
            if db_results:
                results_parts.append("📊 INFORMATIONS À JOUR DEPUIS LA BASE DE DONNÉES :")
                results_parts.append("")
                for formation in db_results[:10]:  # Limiter à 10 résultats
                    formation_info = []
                    if "name" in formation:
                        formation_info.append(f"• {formation['name']}")
                    if "faculty" in formation:
                        formation_info.append(f"  Faculté : {formation['faculty']}")
                    if "level" in formation:
                        formation_info.append(f"  Niveau : {formation['level']}")
                    if "description" in formation:
                        formation_info.append(f"  Description : {formation['description']}")
                    if "duration_years" in formation:
                        formation_info.append(f"  Durée : {formation['duration_years']} ans")
                    
                    results_parts.append("\n".join(formation_info))
                    results_parts.append("")
                
                results_parts.append("---")
                results_parts.append("")
        except Exception as e:
            print(f" Erreur lors de la recherche dans la base de données : {e}")
    
    # 2. Recherche dans les documents (base de connaissances)
    if _vectorstore is None:
        if not results_parts:
            return "Erreur: Base de connaissances non initialisée"
    else:
        # Construire la requête de recherche
        query_parts = []
        if faculty:
            query_parts.append(f"faculté {faculty}")
        if level:
            query_parts.append(f"formation {level}")
        
        query = " ".join(query_parts) if query_parts else "formations disponibles"
        
        # Recherche dans la base de connaissances
        docs = _vectorstore.similarity_search(query, k=5)
        
        if docs:
            if results_parts:
                results_parts.append("📄 INFORMATIONS COMPLÉMENTAIRES DES DOCUMENTS :")
            else:
                results_parts.append("📄 FORMATIONS DISPONIBLES :")
            results_parts.append("")
            
            for doc in docs:
                results_parts.append(doc.page_content[:500])  # Limiter la longueur
                results_parts.append("---")
    
    if not results_parts:
        return f"Aucune formation trouvée pour {faculty if faculty else 'toutes les facultés'}"
    
    return "\n\n".join(results_parts)


@tool
def get_faculty_info(faculty_name: str) -> str:
    """
    Obtient des informations détaillées sur une faculté, école ou institut spécifique.
    Recherche automatiquement la définition et la mission de la structure.
    
    Args:
        faculty_name: Nom ou abréviation de la structure (ex: "FA", "FAST", "Faculté d'Agronomie", "ENS")
        
    Returns:
        Informations complètes sur la structure incluant : nom complet, type, définition et mission
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Vérifier d'abord dans la base de connaissances structurée
    structure_info = get_structure_info(faculty_name)
    
    result_parts = []
    
    if structure_info:
        result_parts.append(f" {structure_info['nom_complet']} ({structure_info['abreviation']})")
        result_parts.append(f"Type: {structure_info['type'].capitalize()}")
        result_parts.append("")
        
        # Recherche spécifique pour la définition et la mission
        nom_complet = structure_info['nom_complet']
        
        # Recherche 1 : Définition
        query_definition = f"{nom_complet} définition présentation description"
        docs_definition = _vectorstore.similarity_search(query_definition, k=2)
        
        # Recherche 2 : Mission
        query_mission = f"{nom_complet} mission objectifs rôles fonctions"
        docs_mission = _vectorstore.similarity_search(query_mission, k=2)
        
        # Recherche 3 : Informations générales
        query_general = f"{nom_complet} informations générales"
        docs_general = _vectorstore.similarity_search(query_general, k=3)
        
        # Combiner tous les résultats uniques
        all_docs = {}
        for doc in docs_definition + docs_mission + docs_general:
            # Utiliser le contenu comme clé pour éviter les doublons
            content_key = doc.page_content[:200]  # Premiers 200 caractères comme clé
            if content_key not in all_docs:
                all_docs[content_key] = doc.page_content
        
        if all_docs:
            result_parts.append(" DÉFINITION ET MISSION :")
            result_parts.append("")
            for i, content in enumerate(all_docs.values(), 1):
                result_parts.append(content[:1000])  # Limiter à 1000 caractères par document
                if i < len(all_docs):
                    result_parts.append("---")
        else:
            # Si pas de résultats spécifiques, faire une recherche générale
            search_query = nom_complet
            docs = _vectorstore.similarity_search(search_query, k=3)
            
            if docs:
                result_parts.append(" INFORMATIONS :")
                result_parts.append("")
                for doc in docs:
                    result_parts.append(doc.page_content[:800])
                    result_parts.append("---")
    else:
        # Si la structure n'est pas trouvée dans la base structurée, faire une recherche générale
        search_query = f"{faculty_name} faculté école institut"
        docs = _vectorstore.similarity_search(search_query, k=3)
        
        if docs:
            result_parts.append(f"Informations sur '{faculty_name}' :")
            result_parts.append("")
            for doc in docs:
                result_parts.append(doc.page_content[:800])
                result_parts.append("---")
        else:
            return f"Aucune information trouvée sur '{faculty_name}'. Vérifiez l'orthographe ou utilisez l'abréviation."
    
    return "\n\n".join(result_parts)


@tool
def get_structure_by_abbreviation(abbreviation: str) -> str:
    """
    Obtient le nom complet d'une structure à partir de son abréviation.
    
    Args:
        abbreviation: Abréviation de la structure (ex: "FAST", "FLSH", "ENS")
        
    Returns:
        Nom complet et informations sur la structure
    """
    structure_info = get_structure_info(abbreviation)
    
    if structure_info:
        return f"{structure_info['nom_complet']} ({structure_info['abreviation']})\nType: {structure_info['type'].capitalize()}"
    else:
        # Liste toutes les structures disponibles
        all_structures = []
        for category in ["facultes", "instituts", "ecoles"]:
            category_name = category.capitalize()[:-1]  # Enlever le 's'
            structures = [f"{info['nom_complet']} ({abbrev})" 
                         for abbrev, info in UAM_STRUCTURES[category].items()]
            all_structures.append(f"{category_name}:\n" + "\n".join(f"  - {s}" for s in structures))
        
        return f"Abréviation '{abbreviation}' non trouvée.\n\nStructures disponibles:\n\n" + "\n\n".join(all_structures)


def _list_all_structures_internal() -> str:
    """
    Fonction interne pour lister toutes les structures (utilisée par l'outil)
    """
    result = []
    
    result.append(" STRUCTURES DE L'UNIVERSITÉ ABDOU MOUMOUNI DE NIAMEY\n")
    result.append("=" * 60)
    
    # Facultés
    result.append("\n FACULTÉS:")
    for abbrev, info in UAM_STRUCTURES["facultes"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    # Instituts
    result.append("\n INSTITUTS DE RECHERCHE:")
    for abbrev, info in UAM_STRUCTURES["instituts"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    # Écoles
    result.append("\n ÉCOLES:")
    for abbrev, info in UAM_STRUCTURES["ecoles"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    return "\n".join(result)


@tool
def list_all_structures() -> str:
    """
    Liste toutes les facultés, écoles et instituts de l'UAM avec leurs abréviations.
    
    Returns:
        Liste complète des structures de l'UAM
    """
    return _list_all_structures_internal()


@tool
def save_user_preference(user_id: str, preference_key: str, preference_value: str) -> str:
    """
    Sauvegarde une préférence utilisateur pour la mémoire à long terme.
    
    Args:
        user_id: Identifiant de l'utilisateur
        preference_key: Clé de la préférence (ex: 'faculte_interesse', 'niveau_etude')
        preference_value: Valeur de la préférence
        
    Returns:
        Confirmation de sauvegarde
    """
    _user_memory.save_user_preference(user_id, preference_key, preference_value)
    return f"Préférence '{preference_key}' sauvegardée avec succès: {preference_value}"


@tool
def get_user_preferences(user_id: str) -> str:
    """
    Récupère les préférences sauvegardées d'un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        Préférences de l'utilisateur au format JSON
    """
    preferences = _user_memory.get_user_preferences(user_id)
    if not preferences:
        return "Aucune préférence sauvegardée pour cet utilisateur."
    return json.dumps(preferences, ensure_ascii=False, indent=2)


@tool
def search_prerequisites(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les prérequis (pré-requis) nécessaires pour une filière ou une faculté.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel, ex: "FAST", "Faculté des Sciences")
        
    Returns:
        Informations sur les prérequis
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"prérequis pré-requis conditions admission {filiere}")
    if faculty:
        # Détecter la structure pour obtenir le nom complet
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} prérequis pré-requis conditions admission")
        else:
            query_parts.append(f"{faculty} prérequis pré-requis conditions admission")
    
    query = " ".join(query_parts) if query_parts else "prérequis pré-requis conditions admission filière"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les prérequis trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    # Combiner les résultats
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_competences_requises(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les connaissances et compétences requises pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les connaissances et compétences requises
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"compétences connaissances requises {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} compétences connaissances requises")
        else:
            query_parts.append(f"{faculty} compétences connaissances requises")
    
    query = " ".join(query_parts) if query_parts else "compétences connaissances requises filière"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les compétences requises trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_cycles_et_duree(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les cycles disponibles et la durée d'études pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les cycles (licence, master, doctorat) et leurs durées
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"cycles durée études licence master doctorat {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} cycles durée études licence master doctorat")
        else:
            query_parts.append(f"{faculty} cycles durée études licence master doctorat")
    
    query = " ".join(query_parts) if query_parts else "cycles durée études licence master doctorat"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les cycles et durées trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_chronogramme(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche le chronogramme annuel d'études (modules, heures de cours) pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur le chronogramme, les modules et les heures de cours
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"chronogramme modules heures cours emploi temps programme {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} chronogramme modules heures cours emploi temps programme")
        else:
            query_parts.append(f"{faculty} chronogramme modules heures cours emploi temps programme")
    
    query = " ".join(query_parts) if query_parts else "chronogramme modules heures cours emploi temps programme"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur le chronogramme trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_coefficients(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les coefficients des différents modules pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les coefficients des modules
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"coefficients modules {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} coefficients modules")
        else:
            query_parts.append(f"{faculty} coefficients modules")
    
    query = " ".join(query_parts) if query_parts else "coefficients modules"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les coefficients trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_professeurs(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les professeurs assignés aux différents modules et leurs qualifications.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les professeurs et leurs qualifications
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"professeurs enseignants corps professoral qualifications {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} professeurs enseignants corps professoral qualifications")
        else:
            query_parts.append(f"{faculty} professeurs enseignants corps professoral qualifications")
    
    query = " ".join(query_parts) if query_parts else "professeurs enseignants corps professoral qualifications"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les professeurs trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_debouches(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les débouchés professionnels et les possibilités d'embauche après les études.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les débouchés professionnels et les possibilités d'embauche
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"débouchés professionnels embauche emploi carrière métiers {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} débouchés professionnels embauche emploi carrière métiers")
        else:
            query_parts.append(f"{faculty} débouchés professionnels embauche emploi carrière métiers")
    
    query = " ".join(query_parts) if query_parts else "débouchés professionnels embauche emploi carrière métiers"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les débouchés trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_reglement_interieur(faculty: str = "") -> str:
    """
    Recherche le règlement intérieur d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel, si vide recherche le règlement général)
        
    Returns:
        Informations sur le règlement intérieur
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} règlement intérieur règles discipline"
        else:
            query = f"{faculty} règlement intérieur règles discipline"
    else:
        query = "règlement intérieur UAM université règles discipline"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur le règlement intérieur trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_organisation_corps_professoral(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps professoral d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur l'organisation du corps professoral
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} organisation corps professoral structure enseignants"
        else:
            query = f"{faculty} organisation corps professoral structure enseignants"
    else:
        query = "organisation corps professoral UAM structure enseignants"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur l'organisation du corps professoral trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_organisation_corps_estudiantin(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps estudiantin (associations étudiantes, clubs, etc.) d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur l'organisation du corps estudiantin
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} organisation corps estudiantin associations étudiantes clubs étudiants"
        else:
            query = f"{faculty} organisation corps estudiantin associations étudiantes clubs étudiants"
    else:
        query = "organisation corps estudiantin UAM associations étudiantes clubs étudiants"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur l'organisation du corps estudiantin trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_reclamations() -> str:
    """
    Recherche les différents types de réclamations possibles et comment les faire.
    
    Returns:
        Informations sur les réclamations et les procédures pour les faire
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    query = "réclamations réclamation procédure comment faire démarche"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return "Aucune information sur les réclamations trouvée dans la base de connaissances."
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_avantages_universite(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les avantages de suivre une filière à l'université plutôt que dans d'autres écoles et instituts.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les avantages de l'université
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"avantages université UAM {filiere} écoles instituts")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} avantages université écoles instituts")
        else:
            query_parts.append(f"{faculty} avantages université écoles instituts")
    
    query = " ".join(query_parts) if query_parts else "avantages université UAM écoles instituts"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les avantages trouvée pour {filiere if filiere else faculty if faculty else 'l\'université'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_latest_news(limit: int = 5, category: str = "") -> str:
    """
    Recherche les dernières actualités et annonces de l'UAM depuis la base de données.
    
    Args:
        limit: Nombre maximum d'actualités à retourner (défaut: 5)
        category: Catégorie d'annonce (optionnel, ex: "admission", "examen", "formation")
        
    Returns:
        Liste des dernières actualités et annonces
    """
    if not _db_available:
        return " Base de données non disponible. Les actualités ne peuvent pas être récupérées."
    
    try:
        announcements = search_news_announcements_db(limit=limit, category=category)
        
        if not announcements:
            return "Aucune actualité trouvée."
        
        results_parts = []
        results_parts.append(" DERNIÈRES ACTUALITÉS ET ANNONCES UAM :")
        results_parts.append("")
        
        for i, announcement in enumerate(announcements, 1):
            ann_info = []
            ann_info.append(f"{i}. {announcement.get('title', 'Sans titre')}")
            
            if "published_date" in announcement:
                ann_info.append(f"   Date : {announcement['published_date']}")
            
            if "category" in announcement:
                ann_info.append(f"   Catégorie : {announcement['category']}")
            
            if "content" in announcement:
                content = announcement['content'][:300]  # Limiter à 300 caractères
                ann_info.append(f"   {content}...")
            
            if "link" in announcement:
                ann_info.append(f"   Lien : {announcement['link']}")
            
            results_parts.append("\n".join(ann_info))
            results_parts.append("")
        
        return "\n".join(results_parts)
        
    except Exception as e:
        return f"Erreur lors de la récupération des actualités : {e}"


@tool
def get_schedules_from_db(faculty: str = "", filiere: str = "", level: str = "") -> str:
    """
    Recherche les horaires/emplois du temps depuis la base de données.
    
    Args:
        faculty: Abréviation de la faculté (optionnel)
        filiere: Nom de la filière (optionnel)
        level: Niveau d'étude (optionnel)
        
    Returns:
        Informations sur les horaires et emplois du temps
    """
    if not _db_available:
        return " Base de données non disponible. Les horaires ne peuvent pas être récupérés depuis la BD."
    
    try:
        # Détecter l'abréviation de la faculté si nécessaire
        faculty_abbrev = None
        if faculty:
            structure_info = get_structure_info(faculty)
            if structure_info:
                faculty_abbrev = structure_info["abreviation"]
            else:
                faculty_abbrev = faculty.upper()
        
        # Utiliser la fonction importée depuis database_connector
        # Utiliser la fonction importée depuis database_connector (au niveau global)
        # Note: search_schedules_db est importée au niveau global si disponible
        try:
            schedules = search_schedules_db(faculty=faculty_abbrev, filiere=filiere, level=level)
        except NameError:
            # Si la fonction n'est pas disponible, retourner un message
            return " Fonction de recherche dans la base de données non disponible."
        
        if not schedules:
            return f"Aucun horaire trouvé pour {faculty if faculty else 'les structures'}."
        
        results_parts = []
        results_parts.append(" HORAIRES ET EMPLOIS DU TEMPS (BASE DE DONNÉES) :")
        results_parts.append("")
        
        for schedule in schedules[:20]:  # Limiter à 20 résultats
            sched_info = []
            if "filiere_name" in schedule:
                sched_info.append(f"Filière : {schedule['filiere_name']}")
            if "day_of_week" in schedule:
                sched_info.append(f"Jour : {schedule['day_of_week']}")
            if "start_time" in schedule and "end_time" in schedule:
                sched_info.append(f"Heure : {schedule['start_time']} - {schedule['end_time']}")
            if "module_name" in schedule:
                sched_info.append(f"Module : {schedule['module_name']}")
            if "room" in schedule:
                sched_info.append(f"Salle : {schedule['room']}")
            if "professor" in schedule:
                sched_info.append(f"Professeur : {schedule['professor']}")
            
            results_parts.append("\n".join(sched_info))
            results_parts.append("---")
            results_parts.append("")
        
        return "\n".join(results_parts)
        
    except Exception as e:
        return f"Erreur lors de la récupération des horaires : {e}"


def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    tools = [
        detect_greeting,
        search_uam_knowledge,
        check_question_relevance,
        calculate_fees,
        search_formations,
        get_faculty_info,
        get_structure_by_abbreviation,
        list_all_structures,
        save_user_preference,
        get_user_preferences,
        search_prerequisites,
        search_competences_requises,
        search_cycles_et_duree,
        search_chronogramme,
        search_coefficients,
        search_professeurs,
        search_debouches,
        search_reglement_interieur,
        search_organisation_corps_professoral,
        search_organisation_corps_estudiantin,
        search_reclamations,
        search_avantages_universite
    ]
    
    # Ajouter les outils de base de données si disponible
    if _db_available:
        tools.extend([
            search_latest_news,
            get_schedules_from_db
        ])
    
    return tools



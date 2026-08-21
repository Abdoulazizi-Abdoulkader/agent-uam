"""Outils sur les structures de l'UAM : facultés, écoles et instituts."""
from langchain_core.tools import tool

from context_tracker import push_text
from uam_structures import (
    get_structure_info,
    UAM_STRUCTURES,
    list_all_structures_internal
)

from ._rag import _rag_search
from ._vectorstore import get_vectorstore


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
    if get_vectorstore() is None:
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
        docs_definition = _rag_search(query_definition, k=2)
        
        # Recherche 2 : Mission
        query_mission = f"{nom_complet} mission objectifs rôles fonctions"
        docs_mission = _rag_search(query_mission, k=2)
        
        # Recherche 3 : Informations générales
        query_general = f"{nom_complet} informations générales"
        docs_general = _rag_search(query_general, k=3)
        
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
            docs = _rag_search(search_query, k=3)
            
            if docs:
                result_parts.append(" INFORMATIONS :")
                result_parts.append("")
                for doc in docs:
                    result_parts.append(doc.page_content[:800])
                    result_parts.append("---")
    else:
        # Si la structure n'est pas trouvée dans la base structurée, faire une recherche générale
        search_query = f"{faculty_name} faculté école institut"
        docs = _rag_search(search_query, k=3)
        
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


@tool
def list_all_structures() -> str:
    """
    Liste toutes les facultés, écoles et instituts de l'UAM avec leurs abréviations.

    Returns:
        Liste complète des structures de l'UAM
    """
    result = list_all_structures_internal()
    push_text(result)
    return result

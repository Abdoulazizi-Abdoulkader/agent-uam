"""
Gestion des structures UAM (facultés, écoles, instituts)
Détection et résolution des abréviations
"""
from typing import Optional, Dict, Any, List


# Dictionnaire des facultés, écoles et instituts avec leurs abréviations
UAM_STRUCTURES = {
    "facultes": {
        "FAST": {
            "nom_complet": "Faculté des Sciences et Techniques",
            "variantes": ["Faculté des sciences & techniques", "Faculté des Sciences et Techniques", "FAST", "sciences et techniques", "sciences techniques"]
        },
        "FLSH": {
            "nom_complet": "Faculté des Lettres et Sciences Humaines",
            "variantes": ["Faculté des lettres et sciences humaines", "Faculté des Lettres et Sciences Humaines","FLSH", "lettres et sciences humaines", "lettres sciences humaines"]
        },
        "FA": {
            "nom_complet": "Faculté d'Agronomie",
            "variantes": ["Faculté d'agronomie", "Faculté d'Agronomie", "FA", "agronomie"]
        },
        "FSEG": {
            "nom_complet": "Faculté des Sciences Économiques et de Gestion",
            "variantes": ["Faculté des sciences économiques et de gestion", "Faculté des Sciences Économiques et de Gestion", "FSEG", "sciences économiques et de gestion", "sciences économiques gestion"]
        },
        "FSEJ": {
            "nom_complet": "Faculté des Sciences Économiques et Juridiques",
            "variantes": ["Faculté des sciences économiques et juridiques", "Faculté des Sciences Économiques et Juridiques", "FSEJ", "sciences économiques et juridiques", "droit et économie", "juridique et économique"]
        },
        "FSJP": {
            "nom_complet": "Faculté des Sciences Juridiques et Politiques",
            "variantes": ["Faculté des sciences juridiques et politiques","Faculté des Sciences Juridiques et Politiques", "FSJP", "sciences juridiques et politiques", "droit", "juridique"]
        },
        "FSS": {
            "nom_complet": "Faculté des Sciences de la Santé",
            "variantes": ["Faculté des sciences de la santé", "Faculté des Sciences de la Santé", "FSS", "sciences de la santé", "santé", "médecine"]
        }
    },
    "instituts": {
        "IRSH": {
            "nom_complet": "Institut de Recherche en Sciences Humaines",
            "variantes": ["Institut de recherche en sciences humaines", "Institut de Recherche en Sciences Humaines", "IRSH"]
        },
        "IREM": {
            "nom_complet": "Institut de Recherches pour l'Enseignement des Mathématiques",
            "variantes": ["Institut de recherches pour l'enseignement des mathématiques", "Institut de Recherches pour l'Enseignement des Mathématiques", "IREM"]
        },
        "IRI": {
            "nom_complet": "Institut des Radio-isotopes",
            "variantes": ["Institut des radio-isotopes", "Institut des Radio-isotopes", "IRI"]
        }
    },
    "ecoles": {
        "ENS": {
            "nom_complet": "École Normale Supérieure",
            "variantes": ["École normale supérieure", "École Normale Supérieure", "ENS"]
        },
        "ED-SVT": {
            "nom_complet": "École Doctorale des Sciences de la Vie et de la Terre",
            "variantes": ["École doctorale des Sciences de la Vie et de la Terre", "École Doctorale des Sciences de la Vie et de la Terre", "ED-SVT", "École doctorale SVT"]
        },
        "ED-LASHS": {
            "nom_complet": "École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société",
            "variantes": ["École doctorale des Lettres, Arts, Sciences de l'Homme et de la Société", "École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société", "ED-LASHS", "École doctorale LASHS"]
        },
        "ED-SET": {
            "nom_complet": "École Doctorale des Sciences Exactes et Techniques",
            "variantes": ["École doctorale des Sciences Exactes et Techniques", "École Doctorale des Sciences Exactes et Techniques", "ED-SET", "École doctorale SET"]
        }
    }
}


def get_structure_info(structure_name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche une structure (faculté, école, institut) par son nom ou abréviation

    Args:
        structure_name: Nom ou abréviation de la structure

    Returns:
        Dictionnaire avec les informations de la structure ou None si non trouvé
    """
    structure_name_lower = structure_name.lower().strip()

    # Rechercher dans toutes les catégories
    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            # Vérifier l'abréviation
            if abbrev.lower() == structure_name_lower:
                return {
                    "type": category[:-1],  # Enlever le 's' final
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"],
                    "variantes": info["variantes"]
                }
            # Vérifier les variantes
            for variant in info["variantes"]:
                if variant.lower() == structure_name_lower or variant.lower() in structure_name_lower:
                    return {
                        "type": category[:-1],
                        "abreviation": abbrev,
                        "nom_complet": info["nom_complet"],
                        "variantes": info["variantes"]
                    }

    return None


def detect_structure_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Détecte toutes les structures mentionnées dans un texte

    Args:
        text: Texte à analyser

    Returns:
        Liste des structures détectées
    """
    text_lower = text.lower()
    detected = []

    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            # Vérifier si l'abréviation ou une variante est dans le texte
            if abbrev.lower() in text_lower:
                detected.append({
                    "type": category[:-1],
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"]
                })
            else:
                for variant in info["variantes"]:
                    if variant.lower() in text_lower:
                        detected.append({
                            "type": category[:-1],
                            "abreviation": abbrev,
                            "nom_complet": info["nom_complet"]
                        })
                        break

    return detected


def list_all_structures_internal() -> str:
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


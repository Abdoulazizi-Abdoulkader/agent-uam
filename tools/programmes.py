"""Outils sur le contenu des programmes : prérequis, cycles, modules, corps
universitaire, débouchés et règlement."""
from langchain_core.tools import tool

from uam_structures import get_structure_info

from ._rag import _rag_response


def _search_filiere_faculty(
    kw: str, filiere: str, faculty: str, not_found_tpl: str,
    default_target: str = "les filières",
) -> str:
    """Helper pour les outils (filiere, faculty) → requête FAISS + message introuvable.

    Construit la requête : kw+filière d'un côté, nom_complet+kw côté faculté.
    not_found_tpl doit contenir {target} (ex: "Aucune info pour {target}").
    """
    parts = []
    if filiere:
        parts.append(f"{kw} {filiere}")
    if faculty:
        info = get_structure_info(faculty)
        parts.append(f"{info['nom_complet'] if info else faculty} {kw}")
    query = " ".join(parts) if parts else kw
    target = filiere or faculty or default_target
    return _rag_response(query, not_found_tpl.format(target=target))


def _search_by_faculty_or_uam(kw: str, faculty: str, not_found_tpl: str) -> str:
    """Helper pour les outils faculty-only : requête faculté précise ou UAM en général.

    not_found_tpl doit contenir {target}.
    """
    if faculty:
        info = get_structure_info(faculty)
        nom = info["nom_complet"] if info else faculty
        query = f"{nom} {kw}"
    else:
        query = f"{kw} UAM université"
    target = faculty or "l'UAM"
    return _rag_response(query, not_found_tpl.format(target=target))


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
    return _search_filiere_faculty(
        "prérequis pré-requis conditions admission",
        filiere, faculty,
        "Aucune information sur les prérequis trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "compétences connaissances requises",
        filiere, faculty,
        "Aucune information sur les compétences requises trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "cycles durée études licence master doctorat",
        filiere, faculty,
        "Aucune information sur les cycles et durées trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "chronogramme modules heures cours emploi temps programme",
        filiere, faculty,
        "Aucune information sur le chronogramme trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "coefficients modules",
        filiere, faculty,
        "Aucune information sur les coefficients trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "professeurs enseignants corps professoral qualifications",
        filiere, faculty,
        "Aucune information sur les professeurs trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "débouchés professionnels embauche emploi carrière métiers",
        filiere, faculty,
        "Aucune information sur les débouchés trouvée pour {target}",
    )


@tool
def search_reglement_interieur(faculty: str = "") -> str:
    """
    Recherche le règlement intérieur d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel, si vide recherche le règlement général)

    Returns:
        Informations sur le règlement intérieur
    """
    return _search_by_faculty_or_uam(
        "règlement intérieur règles discipline",
        faculty,
        "Aucune information sur le règlement intérieur trouvée pour {target}",
    )


@tool
def search_organisation_corps_professoral(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps professoral d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)

    Returns:
        Informations sur l'organisation du corps professoral
    """
    return _search_by_faculty_or_uam(
        "organisation corps professoral structure enseignants",
        faculty,
        "Aucune information sur l'organisation du corps professoral trouvée pour {target}",
    )


@tool
def search_organisation_corps_estudiantin(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps estudiantin (associations étudiantes, clubs, etc.) d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)

    Returns:
        Informations sur l'organisation du corps estudiantin
    """
    return _search_by_faculty_or_uam(
        "organisation corps estudiantin associations étudiantes clubs étudiants",
        faculty,
        "Aucune information sur l'organisation du corps estudiantin trouvée pour {target}",
    )


@tool
def search_reclamations() -> str:
    """
    Recherche les différents types de réclamations possibles et comment les faire.

    Returns:
        Informations sur les réclamations et les procédures pour les faire
    """
    return _rag_response(
        "réclamations réclamation procédure comment faire démarche",
        "Aucune information sur les réclamations trouvée dans la base de connaissances.",
    )


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
    return _search_filiere_faculty(
        "avantages université UAM écoles instituts",
        filiere, faculty,
        "Aucune information sur les avantages trouvée pour {target}",
        default_target="l'université",
    )

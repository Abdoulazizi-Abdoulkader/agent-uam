"""Outils de scolarité : frais, formations, admission, inscription, documents
et services à l'étudiant."""
from datetime import datetime

from langchain_core.tools import tool

from context_tracker import push_text
from logger_config import get_logger
from uam_structures import get_structure_info

from ._db import _db_available, search_fees_db, search_formations_db
from ._rag import _rag_response, _rag_search
from ._vectorstore import get_vectorstore

logger = get_logger(__name__)


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
                results_parts.append(f"💰 FRAIS D'INSCRIPTION — {level.upper()} (tarifs officiels UAM) :")
                results_parts.append("")
                # Séparer UEMOA et hors UEMOA
                from collections import defaultdict
                by_nat: dict = defaultdict(list)
                for fee in db_results:
                    by_nat[fee.get("nationalite", "uemoa")].append(fee)

                # UEMOA : montant unique
                if "uemoa" in by_nat:
                    results_parts.append("  📋 Étudiants nigériens & zone UEMOA :")
                    for fee in by_nat["uemoa"]:
                        ind = fee.get("montant_indicatif")
                        results_parts.append(f"    • {ind:,} FCFA")
                    results_parts.append("")

                # Hors UEMOA : regrouper les facultés par montant
                if "hors_uemoa" in by_nat:
                    results_parts.append("  📋 Étudiants hors zone UEMOA :")
                    # Regrouper par montant → liste de composantes
                    by_amount: dict = defaultdict(list)
                    for fee in by_nat["hors_uemoa"]:
                        comp = fee.get("composante_sigle") or ""
                        ind = fee.get("montant_indicatif", 0)
                        if comp:
                            by_amount[ind].append(comp)
                    if by_amount:
                        for montant in sorted(by_amount.keys()):
                            composantes = ", ".join(sorted(set(by_amount[montant])))
                            results_parts.append(f"    • {composantes} : {montant:,} FCFA / an")
                    else:
                        # Pas de composante précisée → montant unique
                        for fee in by_nat["hors_uemoa"]:
                            ind = fee.get("montant_indicatif", 0)
                            results_parts.append(f"    • {ind:,} FCFA / an")
                    results_parts.append("")

                source_label = "officielle" if any(f.get("source") == "officiel_uam" for f in db_results) else "indicative"
                if source_label == "officielle":
                    results_parts.append("📄 Source : Service Central de la Scolarité (Formalités d'admission).")
                else:
                    results_parts.append("⚠️ Montants indicatifs — contactez le secrétariat de votre faculté.")
                results_parts.append("Zone UEMOA : Niger, Bénin, Côte d'Ivoire, Togo, Burkina Faso, Sénégal, Mali, Guinée Bissau.")
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche des frais en base de données : {e}")

    # 2. Tarifs officiels (fallback si BDD indisponible)
    # Source : Formalités_d_admission.txt — tarifs officiels d'inscription UAM
    if not results_parts:
        level_lower = level.lower()
        if level_lower in ("licence", "l1", "l2", "l3"):
            results_parts.append("💰 FRAIS D'INSCRIPTION EN LICENCE (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 10 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA (annuel) :")
            results_parts.append("    • FA, FAST : 250 000 FCFA")
            results_parts.append("    • FLSH, ENS, FSEG, FSJP : 150 000 FCFA")
            results_parts.append("    • FSS (Santé, 1ère–6ème année) : 200 000 FCFA")
        elif level_lower in ("master", "m1", "m2"):
            results_parts.append("💰 FRAIS D'INSCRIPTION EN MASTER (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 50 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA :")
            results_parts.append("    • Toutes facultés : 250 000 FCFA")
        elif level_lower == "doctorat":
            results_parts.append("💰 FRAIS D'INSCRIPTION EN DOCTORAT (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 50 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA :")
            results_parts.append("    • FA, FAST, FLSH, ENS, FSEG, FSJP : 250 000 FCFA")
            results_parts.append("    • FSS (Santé, 7ème année – thèse) : 400 000 FCFA")
        else:
            return f"Niveau '{level}' non reconnu. Niveaux disponibles : licence, master, doctorat"
        if faculty:
            results_parts.append(f"\n  • Faculté concernée : {faculty}")
        results_parts.append("\nZone UEMOA : Niger, Bénin, Côte d'Ivoire, Togo, Burkina Faso, Sénégal, Mali, Guinée Bissau.")
        results_parts.append("⚠️ Dépôt du dossier au Service Central de la Scolarité (ENS).")

    result = "\n".join(results_parts)
    # Capture pour RAGAS : la grille tarifaire (codée en dur ou issue de la BD) est
    # la source factuelle de la réponse — sans ce push, faithfulness la voit "non soutenue".
    push_text(result)
    return result


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
                results_parts.append("📊 FORMATIONS DISPONIBLES (BASE DE DONNÉES) :")
                results_parts.append("")
                for formation in db_results[:15]:  # Limiter à 15 résultats
                    formation_info = []
                    if "name" in formation:
                        formation_info.append(f"🎓 {formation['name']}")
                    if "structure_nom" in formation:
                        formation_info.append(f"   Structure : {formation['structure_nom']}")
                    if "level" in formation:
                        formation_info.append(f"   Niveau : {formation['level']}")
                    if "conditions_acces" in formation and formation["conditions_acces"]:
                        formation_info.append(f"   Conditions d'accès : {formation['conditions_acces']}")
                    if "pieces_requises" in formation and formation["pieces_requises"]:
                        formation_info.append(f"   Pièces requises : {formation['pieces_requises']}")
                    if "objectifs" in formation and formation["objectifs"]:
                        formation_info.append(f"   Objectifs : {formation['objectifs']}")
                    
                    results_parts.append("\n".join(formation_info))
                    results_parts.append("")
                
                results_parts.append("---")
                results_parts.append("")
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche des formations en base de données : {e}")

    # 2. Recherche dans les documents (base de connaissances)
    if get_vectorstore() is None:
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
        docs = _rag_search(query, k=5)
        
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
def search_admission_requirements(level: str = "", faculty: str = "", filiere: str = "") -> str:
    """
    Recherche les conditions d'admission et d'accès (par niveau, faculté ou filière).
    """
    query_parts = ["conditions d'admission", "conditions d'accès", "critères", "admissibilité"]
    if level:
        query_parts.append(f"niveau {level}")
    if filiere:
        query_parts.append(f"filière {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        query_parts.append(structure_info["nom_complet"] if structure_info else faculty)
    return _rag_response(" ".join(query_parts), "Aucune information sur les conditions d'admission trouvée.")


@tool
def search_required_documents(process: str = "inscription", level: str = "", faculty: str = "") -> str:
    """
    Recherche les pièces à fournir et documents requis (inscription/réinscription).
    """
    query_parts = ["pièces à fournir", "documents requis", "dossier", f"{process} université"]
    if level:
        query_parts.append(f"niveau {level}")
    if faculty:
        structure_info = get_structure_info(faculty)
        query_parts.append(structure_info["nom_complet"] if structure_info else faculty)
    return _rag_response(" ".join(query_parts), "Aucune information sur les pièces à fournir trouvée.")


@tool
def search_registration_procedure(process: str = "inscription") -> str:
    """
    Recherche la procédure/les étapes d'inscription ou de réinscription.
    """
    return _rag_response(
        f"procédure étapes {process} université UAM",
        "Aucune information sur la procédure d'inscription trouvée.",
    )


@tool
def search_registration_calendar(year: str = "") -> str:
    """
    Recherche le calendrier académique et les dates d'inscription.
    """
    query = "calendrier académique dates d'inscription date limite"
    if year:
        query = f"{query} {year}"
    return _rag_response(query, "Aucune information sur le calendrier d'inscription trouvée.")


@tool
def search_student_card() -> str:
    """
    Recherche les informations sur la carte d'étudiant (obtention, retrait, remplacement).
    """
    return _rag_response(
        "carte étudiant badge étudiant obtention retrait remplacement",
        "Aucune information sur la carte d'étudiant trouvée.",
    )


@tool
def search_transfer_equivalence(topic: str = "transfert") -> str:
    """
    Recherche les démarches de transfert, équivalence ou changement de filière.
    """
    return _rag_response(
        f"démarches {topic} équivalence changement de filière reprise d'études",
        "Aucune information sur le transfert/équivalence trouvée.",
    )


@tool
def search_housing_and_services(service: str = "") -> str:
    """
    Recherche les informations sur la vie étudiante (logement, restauration, transport, bibliothèque).
    """
    query = "logement cité universitaire restauration transport bibliothèque service social"
    if service:
        query = f"{query} {service}"
    return _rag_response(query, "Aucune information sur la vie étudiante trouvée.")


@tool
def search_scholarships() -> str:
    """
    Recherche les informations sur les bourses et aides financières.
    """
    return _rag_response(
        "bourse bourses aide financière allocation étudiant",
        "Aucune information sur les bourses trouvée.",
    )


@tool
def search_contacts_services(service: str = "") -> str:
    """
    Recherche les contacts des services (scolarité, secrétariat, admissions, etc.).
    """
    query = "contacts téléphone email adresse service scolarité secrétariat admissions"
    if service:
        query = f"{query} {service}"
    return _rag_response(query, "Aucune information de contact trouvée.")


@tool
def search_international_equivalence(level: str = "", country: str = "") -> str:
    """
    Recherche les procédures d'équivalence internationale et reconnaissance des diplômes étrangers.
    """
    query = "équivalence internationale reconnaissance diplômes étrangers admission"
    if level:
        query = f"{query} niveau {level}"
    if country:
        query = f"{query} pays {country}"
    return _rag_response(query, "Aucune information sur l'équivalence internationale trouvée.")


@tool
def search_late_reenrollment(reason: str = "") -> str:
    """
    Recherche les règles et démarches pour une réinscription tardive.
    """
    query = "réinscription tardive pénalités délais dérogation"
    if reason:
        query = f"{query} motif {reason}"
    return _rag_response(query, "Aucune information sur la réinscription tardive trouvée.")


@tool
def search_internship_info(filiere: str = "", level: str = "") -> str:
    """
    Recherche les informations sur les stages (conditions, durée, procédure).
    """
    query = "stage stages conditions durée convention procédure"
    if filiere:
        query = f"{query} filière {filiere}"
    if level:
        query = f"{query} niveau {level}"
    return _rag_response(query, "Aucune information sur les stages trouvée.")


@tool
def search_double_degree(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les informations sur les doubles diplômes ou parcours bi-diplômants.
    """
    query = "double diplôme double diplome bi-diplômant parcours double cursus"
    if filiere:
        query = f"{query} filière {filiere}"
    if faculty:
        structure_info = get_structure_info(faculty)
        query = f"{query} {structure_info['nom_complet'] if structure_info else faculty}"
    return _rag_response(query, "Aucune information sur les doubles diplômes trouvée.")


@tool
def generate_registration_checklist(
    profile: str = "nouveau",
    level: str = "",
    faculty: str = "",
    is_international: bool = False
) -> str:
    """
    Génère une checklist guidée pour l'inscription/réinscription selon le profil.
    """
    profile_lower = (profile or "nouveau").strip().lower()
    checklist = []

    if profile_lower in ["nouveau", "nouvel étudiant", "nouvelle etudiante"]:
        checklist.append("Checklist - Nouvel étudiant")
        checklist.append("1. Vérifier les conditions d'admission de la filière")
        checklist.append("2. Préparer les pièces requises (acte de naissance, relevés, etc.)")
        checklist.append("3. Déposer le dossier ou suivre la procédure indiquée")
        checklist.append("4. Payer les frais d'inscription/scolarité")
        checklist.append("5. Récupérer la carte d'étudiant")
    elif profile_lower in ["ancien", "réinscription", "reinscription", "ancien étudiant"]:
        checklist.append("Checklist - Réinscription")
        checklist.append("1. Consulter le calendrier de réinscription")
        checklist.append("2. Mettre à jour les pièces si nécessaire")
        checklist.append("3. Régler les frais de réinscription")
        checklist.append("4. Vérifier la confirmation d'inscription")
    else:
        checklist.append("Checklist - Inscription")
        checklist.append("1. Vérifier les conditions d'accès")
        checklist.append("2. Préparer les pièces requises")
        checklist.append("3. Suivre la procédure d'inscription")

    if level:
        checklist.append(f" Niveau ciblé : {level}")
    if faculty:
        checklist.append(f" Structure : {faculty}")
    if is_international:
        checklist.append(" Ajouter : documents d'équivalence et traduction certifiée si requis")

    checklist.append(" Besoin de détails ? Demandez les pièces ou la procédure exacte.")
    result = "\n".join(checklist)
    push_text(result)
    return result

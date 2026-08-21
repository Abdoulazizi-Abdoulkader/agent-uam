"""Outils adossés à la base de données scolarité de l'UAM.

Ce sont les quatre outils que get_tools() n'expose que si `_db_available`.
"""
from langchain_core.tools import tool

from context_tracker import push_text
from logger_config import get_logger
from uam_structures import get_structure_info
from utils import sanitize_input

from ._db import (
    _db_available,
    get_official_stats_db,
    get_statistics_db,
    search_news_announcements_db,
    search_schedules_db,
    search_student_courses_db,
    search_students_db,
)

logger = get_logger(__name__)

# Statuts BD considérés comme "inscription validée" — centralisé ici pour éviter la dispersion.
_STATUTS_INSCRIPTION_VALIDES: frozenset = frozenset({
    "validé", "validee", "validated",
    "actif", "active",
    "inscrit", "inscrite", "enregistré", "enregistree",
    "confirmed", "confirmé",
})


@tool
def search_student_record(matricule: str, query_type: str = "inscription") -> str:
    """
    Consulte le dossier d'un étudiant par son matricule dans la base de données UAM.
    Permet de vérifier le statut d'inscription, les paiements, les résultats et les cours inscrits.

    Args:
        matricule: Numéro de matricule de l'étudiant (ex: UAM240001)
        query_type: Type de consultation —
            "inscription" : statut d'inscription uniquement
            "paiement"    : montants payés et frais
            "resultats"   : notes et crédits ECTS
            "cours"       : liste des UEs inscrites ce semestre
            "general"     : toutes les informations disponibles

    Returns:
        Informations sur le dossier de l'étudiant avec statut d'inscription, montants FCFA, notes, ECTS.
    """
    if not matricule or not matricule.strip():
        return "Veuillez fournir un numéro de matricule valide (ex: UAM240001)."

    matricule = matricule.strip().upper()

    if not _db_available:
        return (
            f"La base de données n'est pas disponible pour consulter le matricule {matricule}.\n"
            "Veuillez contacter directement le service de scolarité de votre faculté.\n"
            "Scolarité Centrale UAM : +227 20 74 06 61 — Lun–Ven 7h30–15h30."
        )

    try:
        students = search_students_db(student_id=matricule)
    except Exception as e:
        logger.error(f"Erreur BDD lors de la consultation du matricule {matricule}: {e}")
        return (
            f"Une erreur est survenue lors de la consultation du matricule {matricule}.\n"
            "Veuillez réessayer ou contacter le service de scolarité."
        )

    if not students:
        return (
            f"Aucun étudiant trouvé avec le matricule {matricule}.\n"
            "Vérifiez le numéro saisi ou contactez le service des inscriptions de l'UAM."
        )

    def _first_not_none(d: dict, *keys):
        """Retourne la première valeur non-None parmi les clés données (gère 0 correctement)."""
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    student = students[0]
    lines = [f"Dossier étudiant — Matricule : **{matricule}**\n"]

    # sanitize_input protège contre l'injection indirecte depuis la BDD
    nom = sanitize_input(
        f"{student.get('last_name', '')} {student.get('first_name', '')}".strip(),
        max_length=100
    )
    if nom:
        lines.append(f"**Nom :** {nom}")

    faculte = sanitize_input(
        student.get("faculty_abbreviation") or student.get("faculty", ""),
        max_length=50
    )
    if faculte:
        lines.append(f"**Faculté :** {faculte}")

    niveau = sanitize_input(student.get("level", ""), max_length=30)
    if niveau:
        lines.append(f"**Niveau :** {niveau}")

    # Statut d'inscription
    statut = student.get("inscription_status") or student.get("status", "")
    if statut:
        statut_label = "validée ✓" if statut.lower() in _STATUTS_INSCRIPTION_VALIDES else statut
        lines.append(f"\n**Statut d'inscription :** {statut_label}")
    else:
        lines.append("\n**Statut d'inscription :** non renseigné — contactez la scolarité pour confirmation.")

    # Paiements / frais (FCFA) — _first_not_none gère correctement la valeur 0
    if query_type in ("paiement", "general"):
        montant = _first_not_none(student, "fees_paid", "montant_paye")
        if montant is not None:
            lines.append(f"**Montant payé :** {int(montant):,} FCFA")
        frais_total = _first_not_none(student, "total_fees", "frais_total")
        if frais_total is not None:
            lines.append(f"**Frais totaux :** {int(frais_total):,} FCFA")
        reste = _first_not_none(student, "remaining_fees", "reste_a_payer")
        if reste is not None:
            lines.append(f"**Reste à payer :** {int(reste):,} FCFA")

    # Résultats académiques — idem pour 0 crédit ou 0/20
    if query_type in ("resultats", "general"):
        moyenne = _first_not_none(student, "average", "moyenne_generale")
        if moyenne is not None:
            lines.append(f"\n**Moyenne générale :** {moyenne}/20")
        credits = _first_not_none(student, "credits_valides", "ects_valides")
        if credits is not None:
            lines.append(f"**Crédits ECTS validés :** {credits}")
        notes_raw = student.get("notes") or student.get("results")
        if notes_raw:
            lines.append("**Notes par UE :**")
            if isinstance(notes_raw, list):
                for ue in notes_raw[:8]:
                    ue_name = ue.get("ue") or ue.get("matiere", "UE inconnue")
                    note = ue.get("note") or ue.get("grade", "—")
                    valide = " ✓ validé" if ue.get("valide") or ue.get("validated") else ""
                    lines.append(f"  • {ue_name} : {note}/20{valide}")
            else:
                lines.append(f"  {notes_raw}")

    # Cours inscrits (UEs de la formation)
    if query_type in ("cours", "general"):
        try:
            cours = search_student_courses_db(matricule)
        except Exception as e:
            logger.error(f"Erreur récupération cours pour {matricule}: {e}")
            cours = []
        if cours:
            lines.append("\n**Cours inscrits cette année :**")
            sem_courant = None
            for c in cours:
                sem = c.get("semestre")
                if sem != sem_courant:
                    sem_courant = sem
                    lines.append(f"\n  *Semestre {sem}*")
                code   = sanitize_input(c.get("code_ue", ""), max_length=20)
                titre  = sanitize_input(c.get("intitule", ""), max_length=80)
                ects   = c.get("credits_ects", "?")
                statut = c.get("statut_ue", "")
                statut_label = " ✓" if statut == "valide" else (" ⏳" if statut == "en_cours" else "")
                lines.append(f"  • {code} — {titre} ({ects} ECTS){statut_label}")
        else:
            lines.append("\nAucun cours trouvé pour cette inscription. Contactez la scolarité.")

    lines.append(
        "\nPour toute contestation ou information complémentaire, contactez le service de scolarité "
        "de votre faculté ou la Scolarité Centrale (Tél : +227 20 74 06 61)."
    )
    result = "\n".join(lines)
    push_text(result)
    return result


@tool
def search_statistics_uam(faculty: str = "", level: str = "", year: str = "2024-2025") -> str:
    """
    Donne les statistiques de l'UAM : effectifs étudiants par composante/niveau ET
    nombre d'enseignants-chercheurs, PAT et vacataires issus des données officielles.
    Utiliser pour : "Combien d'étudiants à la FAST ?", "Combien d'enseignants-chercheurs ?",
    "Effectif total UAM ?", "Combien d'inscrits en L1 ?".

    Args:
        faculty: Sigle de la composante (FAST, FLSH, FA, FSEG, FSJP…) — vide = toutes
        level:   Niveau (L1, L2, L3, M1, M2…) — vide = tous
        year:    Année académique pour les inscriptions courantes (défaut : 2024-2025)
    """
    if not _db_available:
        return (
            "La base de données n'est pas disponible pour les statistiques.\n"
            "Contactez la Direction des Études et des Stages (DES) de l'UAM : +227 20 74 06 61."
        )

    from collections import defaultdict
    lines = []

    # ── Partie 1 : inscriptions courantes (table inscriptions) ─────────────────
    try:
        rows = get_statistics_db(
            faculty=faculty.strip() or None,
            level=level.strip() or None,
            year=year.strip() or "2024-2025",
        )
    except Exception as e:
        logger.error(f"Erreur BDD statistiques inscriptions: {e}")
        rows = []

    if rows:
        lines.append(f"**Inscriptions — Année {year}**\n")
        by_faculty: dict = defaultdict(list)
        for r in rows:
            by_faculty[f"{r.get('faculty','?')} — {r.get('faculty_name','?')}"].append(
                (r.get("level", "?"), int(r.get("effectif", 0)))
            )
        total_global = 0
        for fac_label, niveaux in sorted(by_faculty.items()):
            sous_total = sum(n for _, n in niveaux)
            total_global += sous_total
            lines.append(f"- **{fac_label}** : {sous_total} étudiant(s)")
            if len(niveaux) > 1 or level:
                for niv, nb in niveaux:
                    lines.append(f"    • {niv} : {nb}")
        if not faculty:
            lines.append(f"\n**Total inscriptions {year} : {total_global} étudiant(s)**")

    # ── Partie 2 : statistiques officielles (enseignants-chercheurs, effectifs historiques) ─
    try:
        official = get_official_stats_db(faculty=faculty.strip() or None)
    except Exception as e:
        logger.error(f"Erreur BDD statistiques officielles: {e}")
        official = []

    if official:
        if lines:
            lines.append("")
        lines.append("**Données officielles (source : documents UAM)**\n")
        for o in official:
            fac   = o.get("faculty", "?")
            fname = o.get("faculty_name", "?")
            annee = o.get("annee_reference", "?")
            nb_e  = o.get("nb_etudiants")
            nb_ec = o.get("nb_enseignants_chercheurs")
            rang_a= o.get("dont_rang_a")
            vacat = o.get("nb_vacataires")
            pat   = o.get("nb_pat")

            entry = [f"- **{fac} — {fname}** ({annee}) :"]
            if nb_e  is not None: entry.append(f"    • Étudiants : {nb_e:,}")
            if nb_ec is not None:
                ec_detail = f" (dont {rang_a} rang A)" if rang_a else ""
                entry.append(f"    • Enseignants-chercheurs : {nb_ec}{ec_detail}")
            if vacat is not None: entry.append(f"    • Vacataires : {vacat}")
            if pat   is not None: entry.append(f"    • PAT : {pat}")
            lines.extend(entry)

    if not lines:
        target = faculty.upper() if faculty else "l'UAM"
        return (
            f"Aucune statistique trouvée pour {target}.\n"
            "Contactez la scolarité ou la Direction des Études de l'UAM : +227 20 74 06 61."
        )

    lines.append(
        "\n*Inscriptions courantes : base scolarité UAM. "
        "Données officielles : documents UAM (info_UAM.md, rapport 2022-2023).*"
    )
    result = "\n".join(lines)
    push_text(result)
    return result


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

        result = "\n".join(results_parts)
        push_text(result)
        return result
        
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
        
        schedules = search_schedules_db(faculty=faculty_abbrev, filiere=filiere, level=level)
        
        if not schedules:
            return f"Aucun horaire trouvé pour {faculty if faculty else 'les structures'}."
        
        results_parts = []
        results_parts.append("⏰ HORAIRES DES SERVICES UAM (BASE DE DONNÉES) :")
        results_parts.append("")
        
        for schedule in schedules[:20]:  # Limiter à 20 résultats
            sched_info = []
            if "service" in schedule:
                sched_info.append(f"📍 {schedule['service']}")
            if "jours" in schedule:
                sched_info.append(f"   Jours : {schedule['jours']}")
            if "heures_ouverture" in schedule and "heures_fermeture" in schedule:
                sched_info.append(f"   Horaires : {schedule['heures_ouverture']} - {schedule['heures_fermeture']}")
            elif "start_time" in schedule and "end_time" in schedule:
                sched_info.append(f"   Horaires : {schedule['start_time']} - {schedule['end_time']}")
            if "notes" in schedule and schedule["notes"]:
                sched_info.append(f"   Notes : {schedule['notes']}")
            
            results_parts.append("\n".join(sched_info))
            results_parts.append("")
        
        result = "\n".join(results_parts)
        push_text(result)
        return result

    except Exception as e:
        return f"Erreur lors de la récupération des horaires : {e}"

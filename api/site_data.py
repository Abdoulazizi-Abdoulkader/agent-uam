"""
Contenu du site institutionnel UAM.

Agrège les données déjà présentes dans le projet — le dictionnaire statique
uam_structures.py (descriptions rédigées des composantes) et la base de scolarité
database/scolarite_uam.db (formations, frais, statistiques) — pour alimenter le
template Jinja2.

Les données étant statiques, tout est calculé une fois et mis en cache.
"""
import os
import re
import sys
from functools import lru_cache
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_config import get_logger  # noqa: E402
from uam_structures import UAM_INFO_GENERALE, UAM_STRUCTURES  # noqa: E402

logger = get_logger(__name__)

# Ordre d'affichage des niveaux de formation
_NIVEAU_ORDER = {"L1": 1, "L2": 2, "L3": 3, "M1": 4, "M2": 5, "D": 6, "Doctorat": 6}

_TYPE_LABELS = {
    "facultes": "Faculté",
    "instituts": "Institut",
    "ecoles": "École",
}


def _query(sql: str) -> List[Dict[str, Any]]:
    """Interroge la base de scolarité, en renvoyant [] si elle est indisponible."""
    try:
        from database_connector import query_database

        return query_database(sql) or []
    except Exception as exc:
        logger.warning(f"Base de scolarité indisponible ({exc}) — section ignorée")
        return []


@lru_cache(maxsize=1)
def get_composantes() -> List[Dict[str, Any]]:
    """Facultés, instituts et écoles, description statique enrichie des données de la base."""
    db_rows = {
        row["sigle"]: row
        for row in _query(
            "SELECT sigle, nom_complet, type_composante, doyen_directeur, "
            "email_contact, telephone FROM composantes"
        )
    }

    stats = {
        row["sigle"]: row
        for row in _query(
            "SELECT c.sigle, s.nb_etudiants, s.nb_enseignants_chercheurs, s.annee_reference "
            "FROM statistiques_composantes s "
            "JOIN composantes c ON c.id = s.composante_id"
        )
    }

    composantes = []
    for categorie, label in _TYPE_LABELS.items():
        for sigle, data in UAM_STRUCTURES.get(categorie, {}).items():
            db = db_rows.get(sigle, {})
            stat = stats.get(sigle, {})
            composantes.append(
                {
                    "sigle": sigle,
                    "categorie": categorie,
                    "type_label": label,
                    "nom_complet": data.get("nom_complet") or db.get("nom_complet", sigle),
                    "localisation": data.get("localisation", ""),
                    "missions": data.get("missions", ""),
                    "historique": data.get("historique", ""),
                    "departements": data.get("departements", []),
                    "effectifs": data.get("effectifs", {}),
                    "email": db.get("email_contact", ""),
                    "telephone": db.get("telephone", ""),
                    "nb_etudiants": stat.get("nb_etudiants"),
                    "nb_enseignants": stat.get("nb_enseignants_chercheurs"),
                    "annee_reference": stat.get("annee_reference", ""),
                }
            )

    # Facultés d'abord, puis instituts et écoles ; alphabétique à l'intérieur
    ordre = {"facultes": 0, "instituts": 1, "ecoles": 2}
    composantes.sort(key=lambda c: (ordre[c["categorie"]], c["sigle"]))
    return composantes


@lru_cache(maxsize=1)
def get_formations() -> List[Dict[str, Any]]:
    """Formations actives, avec leur département et leur composante de rattachement."""
    rows = _query(
        "SELECT f.intitule, f.niveau, f.capacite_accueil, f.duree_semestres, "
        "d.nom AS departement, c.sigle AS composante, c.nom_complet AS composante_nom "
        "FROM formations f "
        "JOIN departements d ON d.id = f.departement_id "
        "JOIN composantes c ON c.id = d.composante_id "
        "WHERE f.est_active = 1"
    )
    rows.sort(
        key=lambda r: (
            r.get("composante") or "",
            r.get("departement") or "",
            _NIVEAU_ORDER.get(r.get("niveau"), 99),
        )
    )
    return rows


@lru_cache(maxsize=1)
def get_filtres_formations() -> Dict[str, List[str]]:
    """Valeurs distinctes servant à filtrer la liste des formations côté navigateur."""
    formations = get_formations()
    composantes = sorted({f["composante"] for f in formations if f.get("composante")})
    niveaux = sorted(
        {f["niveau"] for f in formations if f.get("niveau")},
        key=lambda n: _NIVEAU_ORDER.get(n, 99),
    )
    return {"composantes": composantes, "niveaux": niveaux}


@lru_cache(maxsize=1)
def get_frais() -> List[Dict[str, Any]]:
    """Barèmes officiels des frais d'inscription, ordonnés selon le cursus LMD.

    Les lignes « hors UEMOA » ne se distinguent que par la composante : celle-ci
    est donc reprise dans un libellé lisible, sans quoi le tableau afficherait
    plusieurs fois le même montant sans raison apparente.
    """
    cursus = {"Licence": 1, "Master": 2, "Doctorat": 3}
    publics = {"uemoa": "Niger et UEMOA", "hors_uemoa": "Hors UEMOA"}

    rows = _query(
        "SELECT niveau, type_frais, nationalite, composante_sigle, montant_indicatif, "
        "montant_min, montant_max, devise, annee_reference, notes "
        "FROM frais_formations"
    )

    for row in rows:
        row["public"] = publics.get(row.get("nationalite"), row.get("nationalite", ""))
        row["perimetre"] = row.get("composante_sigle") or "Toutes composantes"

    rows.sort(
        key=lambda r: (
            cursus.get(r.get("niveau"), 99),
            0 if r.get("nationalite") == "uemoa" else 1,
            r.get("composante_sigle") or "",
        )
    )
    return rows


@lru_cache(maxsize=1)
def get_chiffres_cles() -> List[Dict[str, str]]:
    """Chiffres clés de l'université, pour le bandeau de la page d'accueil."""
    source = UAM_INFO_GENERALE.get("chiffres_cles_2022_2023", {})
    nb_formations = len(get_formations())

    chiffres = [
        {"valeur": source.get("etudiants", "—").split(" (")[0], "label": "Étudiants"},
        {"valeur": source.get("enseignants_chercheurs", "—"), "label": "Enseignants-chercheurs"},
        {"valeur": source.get("facultes_et_ecole", "—").split(" (")[0], "label": "Facultés et écoles"},
        {"valeur": source.get("laboratoires_recherche", "—"), "label": "Laboratoires de recherche"},
    ]
    if nb_formations:
        chiffres.append({"valeur": str(nb_formations), "label": "Formations référencées"})
    return chiffres


@lru_cache(maxsize=1)
def get_devise() -> Dict[str, str]:
    """Devise de l'université, séparée de sa mention de langue.

    Stockée sous la forme : « Karamin sani kukumi ne » (haoussa)
    """
    brut = UAM_INFO_GENERALE.get("devise", "")
    texte = re.search(r"«\s*(.+?)\s*»", brut)
    langue = re.search(r"\(([^)]+)\)", brut)
    return {
        "texte": texte.group(1) if texte else brut,
        "langue": langue.group(1) if langue else "",
    }


def get_site_context() -> Dict[str, Any]:
    """Contexte complet passé au template de la page d'accueil."""
    return {
        "info": UAM_INFO_GENERALE,
        "devise": get_devise(),
        "composantes": get_composantes(),
        "formations": get_formations(),
        "filtres": get_filtres_formations(),
        "frais": get_frais(),
        "chiffres": get_chiffres_cles(),
        "historique": UAM_INFO_GENERALE.get("historique_cles", {}),
        "lmd": UAM_INFO_GENERALE.get("systeme_lmd", {}),
        "inscription": UAM_INFO_GENERALE.get("inscription", {}),
        "recherche": UAM_INFO_GENERALE.get("recherche", {}),
        "contacts": UAM_INFO_GENERALE.get("contacts", {}),
    }


def warmup() -> None:
    """Précalcule les données du site au démarrage du serveur."""
    get_composantes()
    get_formations()
    get_frais()
    get_chiffres_cles()
    logger.info(
        f"Contenu du site prêt : {len(get_composantes())} composantes, "
        f"{len(get_formations())} formations, {len(get_frais())} barèmes de frais"
    )

"""
Outil @tool pour interroger la base de données de scolarité de l'UAM.
À intégrer dans tools/uam_tools.py du chatbot.

Requêtes sécurisées (lecture seule, requêtes paramétrées, pas de SQL brut).
"""

import sqlite3
import os
from typing import Optional

# En production : remplacer par mysql.connector + paramètres de connexion
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scolarite_uam.db")


def get_connection():
    """Connexion à la base SQLite (simulation) ou MySQL (production)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── FONCTIONS MÉTIER (à encapsuler dans des @tool) ─────────────────

def consulter_situation_etudiant(matricule: str) -> str:
    """
    Consulte la situation académique d'un étudiant à partir de son matricule.
    Retourne les informations d'inscription, la composante et le niveau.

    Args:
        matricule: Le matricule de l'étudiant (ex: UAM240001)

    Returns:
        Résumé textuel de la situation de l'étudiant.
    """
    matricule = matricule.strip().upper()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT nom_complet, composante, formation, niveau,
                   annee_academique, statut_inscription, date_inscription
            FROM vue_situation_etudiant
            WHERE matricule = ?
            ORDER BY annee_academique DESC
        """, (matricule,)).fetchall()

        if not rows:
            return (f"Aucun étudiant trouvé avec le matricule {matricule}. "
                    "Veuillez vérifier le matricule et réessayer.")

        r = rows[0]
        result = (
            f"📋 Situation de l'étudiant {r['nom_complet']} (matricule : {matricule})\n\n"
            f"• Composante : {r['composante']}\n"
            f"• Formation : {r['formation']}\n"
            f"• Niveau : {r['niveau']}\n"
            f"• Année académique : {r['annee_academique']}\n"
            f"• Statut d'inscription : {r['statut_inscription']}\n"
            f"• Date d'inscription : {r['date_inscription']}\n"
        )

        if r['statut_inscription'] == 'en_attente':
            result += "\n⚠️ L'inscription est en attente de validation. Rapprochez-vous du service de la scolarité."
        elif r['statut_inscription'] == 'rejetee':
            result += "\n❌ L'inscription a été rejetée. Contactez le service de la scolarité pour les motifs."

        return result
    finally:
        conn.close()


def consulter_paiements_etudiant(matricule: str) -> str:
    """
    Consulte l'état des paiements d'un étudiant.

    Args:
        matricule: Le matricule de l'étudiant

    Returns:
        Détail des paiements effectués et des frais restants.
    """
    matricule = matricule.strip().upper()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT nom_complet, annee_academique, type_frais, montant,
                   date_paiement, mode_paiement
            FROM vue_paiements_etudiant
            WHERE matricule = ?
            ORDER BY date_paiement DESC
        """, (matricule,)).fetchall()

        if not rows:
            return f"Aucun paiement trouvé pour le matricule {matricule}."

        nom = rows[0]['nom_complet']
        total = sum(r['montant'] for r in rows)
        result = f"💰 Paiements de {nom} ({matricule})\n\n"

        for r in rows:
            result += (
                f"• {r['type_frais'].replace('_', ' ').title()} : "
                f"{int(r['montant']):,} FCFA — {r['date_paiement']} "
                f"({r['mode_paiement']})\n"
            )

        result += f"\n📊 Total payé : {int(total):,} FCFA"
        return result
    finally:
        conn.close()


def consulter_resultats_etudiant(matricule: str) -> str:
    """
    Consulte les résultats académiques d'un étudiant.

    Args:
        matricule: Le matricule de l'étudiant

    Returns:
        Tableau des notes par UE avec statut de validation.
    """
    matricule = matricule.strip().upper()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT nom_complet, code_ue, nom_ue, credits_ects,
                   note_cc, note_examen, note_finale, session, statut_ue
            FROM vue_resultats_etudiant
            WHERE matricule = ?
            ORDER BY code_ue
        """, (matricule,)).fetchall()

        if not rows:
            return f"Aucun résultat disponible pour le matricule {matricule}."

        nom = rows[0]['nom_complet']
        result = f"📝 Résultats académiques de {nom} ({matricule})\n\n"

        total_credits_valides = 0
        total_credits = 0
        for r in rows:
            statut_symbol = "✅" if r['statut_ue'] == 'valide' else "❌"
            result += (
                f"{statut_symbol} {r['code_ue']} — {r['nom_ue']}\n"
                f"   CC: {r['note_cc']}/20 | Examen: {r['note_examen']}/20 | "
                f"Finale: {r['note_finale']}/20 | {r['credits_ects']} ECTS\n"
            )
            total_credits += r['credits_ects']
            if r['statut_ue'] == 'valide':
                total_credits_valides += r['credits_ects']

        result += f"\n📊 Crédits validés : {total_credits_valides}/{total_credits} ECTS"
        return result
    finally:
        conn.close()


def statistiques_inscriptions(annee_academique: str = "2024-2025") -> str:
    """
    Fournit les statistiques globales d'inscription pour une année académique.

    Args:
        annee_academique: L'année au format YYYY-YYYY (ex: 2024-2025)

    Returns:
        Statistiques par composante et par statut.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT c.sigle, i.statut, COUNT(*) as nombre
            FROM inscriptions i
            JOIN formations f ON i.formation_id = f.id
            JOIN departements d ON f.departement_id = d.id
            JOIN composantes c ON d.composante_id = c.id
            WHERE i.annee_academique = ?
            GROUP BY c.sigle, i.statut
            ORDER BY c.sigle, i.statut
        """, (annee_academique,)).fetchall()

        if not rows:
            return f"Aucune inscription pour {annee_academique}."

        result = f"📊 Statistiques d'inscription — {annee_academique}\n\n"
        current_sigle = None
        for r in rows:
            if r['sigle'] != current_sigle:
                current_sigle = r['sigle']
                result += f"\n{current_sigle} :\n"
            result += f"  • {r['statut'].replace('_', ' ').title()} : {r['nombre']}\n"

        total = conn.execute(
            "SELECT COUNT(*) FROM inscriptions WHERE annee_academique = ?",
            (annee_academique,)
        ).fetchone()[0]
        result += f"\n📈 Total : {total} inscriptions"
        return result
    finally:
        conn.close()


# ─── TEMPLATE @tool POUR INTÉGRATION ─────────────────────────────────
TOOL_TEMPLATE = '''
# À ajouter dans tools/uam_tools.py :

from langchain_core.tools import tool
from database.outil_requete_scolarite import (
    consulter_situation_etudiant,
    consulter_paiements_etudiant,
    consulter_resultats_etudiant,
    statistiques_inscriptions,
)

@tool
def verifier_situation_etudiant(matricule: str) -> str:
    """Vérifie la situation académique d'un étudiant de l'UAM à partir de son matricule.
    Utiliser cet outil quand un étudiant demande sa situation d'inscription,
    son statut ou des informations liées à son dossier personnel.
    Le matricule est au format UAMxxnnnn (ex: UAM240001)."""
    return consulter_situation_etudiant(matricule)

@tool
def verifier_paiements_etudiant(matricule: str) -> str:
    """Vérifie l'état des paiements de frais de scolarité d'un étudiant.
    Utiliser quand un étudiant demande s'il a bien payé ses frais,
    combien il reste à payer, ou le détail de ses paiements."""
    return consulter_paiements_etudiant(matricule)

@tool
def consulter_notes_etudiant(matricule: str) -> str:
    """Consulte les résultats académiques (notes et crédits ECTS) d'un étudiant.
    Utiliser quand un étudiant demande ses notes, ses résultats d'examen,
    ou le nombre de crédits validés."""
    return consulter_resultats_etudiant(matricule)

@tool
def obtenir_statistiques_inscriptions(annee_academique: str = "2024-2025") -> str:
    """Fournit les statistiques globales d'inscription par composante.
    Utiliser pour répondre aux questions sur le nombre d'inscrits,
    les statistiques par faculté ou le taux d'inscription."""
    return statistiques_inscriptions(annee_academique)

# Ajouter ces outils à UAM_TOOLS :
# UAM_TOOLS.extend([
#     verifier_situation_etudiant,
#     verifier_paiements_etudiant,
#     consulter_notes_etudiant,
#     obtenir_statistiques_inscriptions,
# ])
'''


if __name__ == "__main__":
    print("=" * 60)
    print("TEST DES OUTILS DE REQUÊTE SCOLARITÉ")
    print("=" * 60)

    # Trouver un matricule existant
    conn = get_connection()
    matricule_test = conn.execute("SELECT matricule FROM etudiants LIMIT 1").fetchone()['matricule']
    conn.close()

    print(f"\n--- Test 1 : Situation de {matricule_test} ---")
    print(consulter_situation_etudiant(matricule_test))

    print(f"\n--- Test 2 : Paiements de {matricule_test} ---")
    print(consulter_paiements_etudiant(matricule_test))

    # Trouver un étudiant avec des résultats
    conn = get_connection()
    mat_res = conn.execute("""
        SELECT DISTINCT e.matricule FROM etudiants e
        JOIN inscriptions i ON e.id = i.etudiant_id
        JOIN resultats r ON i.id = r.inscription_id
        LIMIT 1
    """).fetchone()
    conn.close()

    if mat_res:
        print(f"\n--- Test 3 : Résultats de {mat_res['matricule']} ---")
        print(consulter_resultats_etudiant(mat_res['matricule']))

    print(f"\n--- Test 4 : Statistiques 2024-2025 ---")
    print(statistiques_inscriptions("2024-2025"))

    print(f"\n\n{'=' * 60}")
    print("TEMPLATE @tool POUR INTÉGRATION AU CHATBOT :")
    print("=" * 60)
    print(TOOL_TEMPLATE)

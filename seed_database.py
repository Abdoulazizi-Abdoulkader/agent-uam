"""
Script de peuplement de scolarite_uam.db pour les tests d'évaluation.

Insère :
  - UAM240001 : inscription validée, paiements complets (test : "est-ce que mon inscription est validée ?")
  - UAM050023 : L1 Informatique validée, résultats S1 en cours (test : "quels cours suis-je inscrit ce semestre ?")
  - UAM010014 : inscription en_attente, scolarité impayée (test : "est-ce que j'ai des arriérés ?")
  - 5 étudiants FAST L1 supplémentaires pour les questions de statistiques 2024-2025

Idempotent : relancer le script ne duplique pas les données (ON CONFLICT IGNORE sur matricule).
"""

import sqlite3
import random
import string
from pathlib import Path
from datetime import date, timedelta

DB_PATH = Path(__file__).parent / "database" / "scolarite_uam.db"


def ref() -> str:
    return "PAY-" + "".join(random.choices(string.digits, k=6))


def seed(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # ── Étudiants ─────────────────────────────────────────────────────────────

    etudiants = [
        # UAM240001 — inscription validée, paiements complets
        {
            "matricule": "UAM240001",
            "nom": "Adamou",
            "prenom": "Moussa",
            "date_naissance": "2005-03-14",
            "lieu_naissance": "Niamey",
            "sexe": "M",
            "nationalite": "Nigérienne",
            "telephone": "90112240",
            "email": "moussa.adamou@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "D",
            "mention_bac": "Bien",
            "etablissement_origine": "Lycée Issa Béri",
        },
        # UAM050023 — quels cours ce semestre
        {
            "matricule": "UAM050023",
            "nom": "Ibrahim",
            "prenom": "Fati",
            "date_naissance": "2005-07-22",
            "lieu_naissance": "Zinder",
            "sexe": "F",
            "nationalite": "Nigérienne",
            "telephone": "91050023",
            "email": "fati.ibrahim@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "D",
            "mention_bac": "Assez Bien",
            "etablissement_origine": "Lycée Dan Kassawa",
        },
        # UAM010014 — arriérés de frais
        {
            "matricule": "UAM010014",
            "nom": "Maiga",
            "prenom": "Boubacar",
            "date_naissance": "2004-11-05",
            "lieu_naissance": "Maradi",
            "sexe": "M",
            "nationalite": "Nigérienne",
            "telephone": "96010014",
            "email": "boubacar.maiga@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2023,
            "serie_bac": "A",
            "mention_bac": "Passable",
            "etablissement_origine": "Lycée Mounkaïla",
        },
        # ── Étudiants FAST L1 supplémentaires (statistiques) ──────────────────
        {
            "matricule": "UAM240051",
            "nom": "Issoufou",
            "prenom": "Kadiatou",
            "date_naissance": "2005-01-10",
            "lieu_naissance": "Dosso",
            "sexe": "F",
            "nationalite": "Nigérienne",
            "telephone": "90240051",
            "email": "kadiatou.issoufou@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "C",
            "mention_bac": "Bien",
            "etablissement_origine": "Lycée Kountché",
        },
        {
            "matricule": "UAM240052",
            "nom": "Sidikou",
            "prenom": "Ali",
            "date_naissance": "2005-04-18",
            "lieu_naissance": "Tahoua",
            "sexe": "M",
            "nationalite": "Nigérienne",
            "telephone": "90240052",
            "email": "ali.sidikou@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "D",
            "mention_bac": "Assez Bien",
            "etablissement_origine": "Lycée Chaibou Dan Inna",
        },
        {
            "matricule": "UAM240053",
            "nom": "Garba",
            "prenom": "Aminatou",
            "date_naissance": "2005-08-30",
            "lieu_naissance": "Agadez",
            "sexe": "F",
            "nationalite": "Nigérienne",
            "telephone": "90240053",
            "email": "aminatou.garba@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "C",
            "mention_bac": "Bien",
            "etablissement_origine": "Lycée Agadez",
        },
        {
            "matricule": "UAM240054",
            "nom": "Hamidou",
            "prenom": "Oumarou",
            "date_naissance": "2004-12-15",
            "lieu_naissance": "Diffa",
            "sexe": "M",
            "nationalite": "Nigérienne",
            "telephone": "90240054",
            "email": "oumarou.hamidou@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "D",
            "mention_bac": "Passable",
            "etablissement_origine": "Lycée Diffa",
        },
        {
            "matricule": "UAM240055",
            "nom": "Moumouni",
            "prenom": "Zara",
            "date_naissance": "2005-05-25",
            "lieu_naissance": "Tillabéri",
            "sexe": "F",
            "nationalite": "Nigérienne",
            "telephone": "90240055",
            "email": "zara.moumouni@etud.uam.ne",
            "type_etudiant": "nouveau",
            "annee_bac": 2024,
            "serie_bac": "D",
            "mention_bac": "Assez Bien",
            "etablissement_origine": "Lycée Tillabéri",
        },
    ]

    for e in etudiants:
        cur.execute(
            """INSERT OR IGNORE INTO etudiants
               (matricule, nom, prenom, date_naissance, lieu_naissance, sexe,
                nationalite, telephone, email, type_etudiant, annee_bac, serie_bac,
                mention_bac, etablissement_origine)
               VALUES (:matricule, :nom, :prenom, :date_naissance, :lieu_naissance, :sexe,
                       :nationalite, :telephone, :email, :type_etudiant, :annee_bac, :serie_bac,
                       :mention_bac, :etablissement_origine)""",
            e,
        )

    # ── Récupérer les IDs nouvellement insérés ────────────────────────────────

    def eid(matricule: str) -> int:
        cur.execute("SELECT id FROM etudiants WHERE matricule=?", (matricule,))
        return cur.fetchone()[0]

    id_240001 = eid("UAM240001")
    id_050023 = eid("UAM050023")
    id_010014 = eid("UAM010014")
    id_240051 = eid("UAM240051")
    id_240052 = eid("UAM240052")
    id_240053 = eid("UAM240053")
    id_240054 = eid("UAM240054")
    id_240055 = eid("UAM240055")

    # ── Inscriptions ──────────────────────────────────────────────────────────
    # (etudiant_id, formation_id, annee_academique, date_inscription, statut, numero_recu)
    inscriptions = [
        (id_240001, 21, "2024-2025", "2024-10-01", "validee",    "REC-240001"),
        (id_050023, 21, "2024-2025", "2024-10-03", "validee",    "REC-050023"),
        (id_010014, 61, "2024-2025", "2024-10-10", "en_attente", "REC-010014"),
        (id_240051,  1, "2024-2025", "2024-10-02", "validee",    "REC-240051"),  # L1 Maths
        (id_240052,  6, "2024-2025", "2024-10-04", "validee",    "REC-240052"),  # L1 Physique
        (id_240053, 11, "2024-2025", "2024-10-05", "validee",    "REC-240053"),  # L1 Chimie
        (id_240054, 16, "2024-2025", "2024-10-06", "validee",    "REC-240054"),  # L1 Biologie
        (id_240055, 21, "2024-2025", "2024-10-07", "validee",    "REC-240055"),  # L1 Informatique (2e)
    ]

    for ins in inscriptions:
        cur.execute(
            """INSERT OR IGNORE INTO inscriptions
               (etudiant_id, formation_id, annee_academique, date_inscription, statut, numero_recu)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ins,
        )

    def ins_id(etudiant_id: int) -> int:
        cur.execute("SELECT id FROM inscriptions WHERE etudiant_id=?", (etudiant_id,))
        return cur.fetchone()[0]

    iid_240001 = ins_id(id_240001)
    iid_050023 = ins_id(id_050023)
    iid_010014 = ins_id(id_010014)
    iid_240051 = ins_id(id_240051)
    iid_240052 = ins_id(id_240052)
    iid_240053 = ins_id(id_240053)
    iid_240054 = ins_id(id_240054)
    iid_240055 = ins_id(id_240055)

    # ── Paiements ─────────────────────────────────────────────────────────────
    # UAM240001 : paiements complets
    paiements = [
        (iid_240001, "inscription",    15000, "2024-10-01", "mobile_money"),
        (iid_240001, "scolarite",      25000, "2024-10-05", "mobile_money"),
        (iid_240001, "bibliotheque",    5000, "2024-10-05", "especes"),
        (iid_240001, "carte_etudiant",  2000, "2024-10-05", "especes"),
        (iid_240001, "assurance",       3000, "2024-10-05", "especes"),
        # UAM050023 : inscription + scolarité payées
        (iid_050023, "inscription",    15000, "2024-10-03", "especes"),
        (iid_050023, "scolarite",      25000, "2024-10-08", "virement"),
        # UAM010014 : SEULEMENT inscription payée → arriérés scolarité
        (iid_010014, "inscription",    15000, "2024-10-10", "especes"),
        # Étudiants supplémentaires : paiements complets
        (iid_240051, "inscription",    15000, "2024-10-02", "mobile_money"),
        (iid_240051, "scolarite",      25000, "2024-10-06", "mobile_money"),
        (iid_240052, "inscription",    15000, "2024-10-04", "mobile_money"),
        (iid_240052, "scolarite",      25000, "2024-10-09", "mobile_money"),
        (iid_240053, "inscription",    15000, "2024-10-05", "especes"),
        (iid_240053, "scolarite",      25000, "2024-10-10", "especes"),
        (iid_240054, "inscription",    15000, "2024-10-06", "mobile_money"),
        (iid_240054, "scolarite",      25000, "2024-10-11", "mobile_money"),
        (iid_240055, "inscription",    15000, "2024-10-07", "especes"),
        (iid_240055, "scolarite",      25000, "2024-10-12", "especes"),
    ]

    for p in paiements:
        ins_id_p, type_frais, montant, date_p, mode = p
        cur.execute(
            "SELECT COUNT(*) FROM paiements WHERE inscription_id=? AND type_frais=? AND montant=?",
            (ins_id_p, type_frais, montant),
        )
        if cur.fetchone()[0] == 0:
            cur.execute(
                """INSERT INTO paiements
                   (inscription_id, type_frais, montant, date_paiement, mode_paiement, reference_paiement)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ins_id_p, type_frais, montant, date_p, mode, ref()),
            )

    # ── Résultats S1 pour UAM050023 (cours en cours, pas encore de notes finales)
    # UEs du semestre 1 de L1 Informatique : ids 1-7
    ue_s1 = [1, 2, 3, 4, 5, 6, 7]
    for ue_id in ue_s1:
        cur.execute("SELECT 1 FROM resultats WHERE inscription_id=? AND ue_id=?", (iid_050023, ue_id))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO resultats
                   (inscription_id, ue_id, note_cc, note_examen, note_finale,
                    session, statut_ue, annee_academique)
                   VALUES (?, ?, NULL, NULL, NULL, 'normale', 'en_cours', '2024-2025')""",
                (iid_050023, ue_id),
            )

    conn.commit()
    conn.close()
    print("Peuplement terminé.")


def verify(db_path: Path = DB_PATH) -> None:
    """Affiche un résumé de ce qui a été inséré pour vérification rapide."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    matricules = ["UAM240001", "UAM050023", "UAM010014",
                  "UAM240051", "UAM240052", "UAM240053", "UAM240054", "UAM240055"]

    print("\n=== Vérification du peuplement ===\n")
    for m in matricules:
        cur.execute(
            """SELECT e.matricule, e.nom||' '||e.prenom AS nom_complet,
                      f.intitule AS formation, c.sigle AS composante,
                      i.statut,
                      COALESCE((SELECT SUM(p.montant) FROM paiements p WHERE p.inscription_id=i.id),0) AS total_paye,
                      (SELECT COUNT(*) FROM resultats r WHERE r.inscription_id=i.id) AS nb_resultats
               FROM etudiants e
               JOIN inscriptions i ON i.etudiant_id=e.id
               JOIN formations f   ON f.id=i.formation_id
               JOIN departements d ON d.id=f.departement_id
               JOIN composantes c  ON c.id=d.composante_id
               WHERE e.matricule=? AND i.annee_academique='2024-2025'""",
            (m,),
        )
        row = cur.fetchone()
        if row:
            print(f"  {row['matricule']} | {row['nom_complet']:<25} | {row['formation']:<25} "
                  f"| {row['composante']} | statut={row['statut']:<10} "
                  f"| payé={int(row['total_paye']):>6} FCFA | résultats={row['nb_resultats']}")
        else:
            print(f"  {m} — NON TROUVÉ")

    # Résumé FAST L1 2024-2025
    cur.execute(
        """SELECT COUNT(*) FROM etudiants e
           JOIN inscriptions i ON i.etudiant_id=e.id
           JOIN formations f   ON f.id=i.formation_id
           JOIN departements d ON d.id=f.departement_id
           JOIN composantes c  ON c.id=d.composante_id
           WHERE c.sigle='FAST' AND f.niveau='L1' AND i.annee_academique='2024-2025'"""
    )
    total_fast = cur.fetchone()[0]
    print(f"\n  Total étudiants FAST L1 2024-2025 : {total_fast}")

    conn.close()


if __name__ == "__main__":
    seed()
    verify()

#!/usr/bin/env python3
"""
Simulation de la base de données de scolarité de l'UAM.
Crée une base SQLite avec des données réalistes pour les tests du chatbot.
Le schéma est compatible MySQL (voir schema_scolarite_uam.sql pour la version MySQL).

Usage :
    python database/simulation_scolarite.py

Produit : database/scolarite_uam.db
"""

import sqlite3
import os
import random
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scolarite_uam.db")

# ─── DONNÉES RÉALISTES ──────────────────────────────────────────────

COMPOSANTES = [
    ("FAST", "Faculté des Sciences et Techniques", "faculte"),
    ("FSS", "Faculté des Sciences Sociales", "faculte"),
    ("FLSH", "Faculté des Lettres et Sciences Humaines", "faculte"),
    ("FSEG", "Faculté des Sciences Économiques et de Gestion", "faculte"),
    ("FSJP", "Faculté des Sciences Juridiques et Politiques", "faculte"),
    ("FA", "Faculté d'Agronomie", "faculte"),
    ("ENS", "École Normale Supérieure", "ecole"),
    ("IRISH", "École Nationale d'Administration", "ecole"),
    ("IREM", "Institut de Radiologie et Imagerie Médicale", "institut"),

]

DEPARTEMENTS = {
    "FAST": ["Mathématiques", "Physique", "Chimie", "Biologie", "Informatique", "Géologie"],
    "FSS": ["Sociologie", "Histoire", "Géographie"],
    "FLSH": ["Lettres Modernes", "Philosophie", "Linguistique"],
    "FSEG": ["Économie", "Gestion", "Finance"],
    "FSJP": ["Droit Public", "Droit Privé", "Sciences Politiques"],
    "FA": ["Productions Végétales", "Productions Animales", "Eaux et Forêts"],
    "ENS": ["Sciences de l'Éducation", "Didactique des Sciences"],
}

NOMS_NIGERIENS = [
    "Abdou", "Ibrahim", "Moussa", "Amadou", "Ousmane", "Issoufou", "Mahamadou",
    "Ali", "Boubacar", "Hamidou", "Saidou", "Hassane", "Djibo", "Soumana",
    "Garba", "Adamou", "Yacouba", "Harouna", "Maman", "Issa",
    "Diallo", "Touré", "Maïga", "Seyni", "Tahirou", "Lawali", "Chaibou",
    "Balkissa", "Mariama", "Aïssatou", "Fatima", "Hadiza", "Zeinabou",
    "Rabi", "Salamatou", "Hamsatou", "Nana",
]

PRENOMS_M = [
    "Abdoulaye", "Moustapha", "Souleymane", "Mamane", "Alhousseini",
    "Oumarou", "Salissou", "Laouali", "Mahamane", "Rabiou",
    "Idrissa", "Sani", "Halidou", "Bachir", "Nouhou",
    "Youssouf", "Salifou", "Zakari", "Habibou", "Mahaman",
]

PRENOMS_F = [
    "Aïcha", "Mariama", "Fati", "Hadiza", "Balkissa",
    "Ramatou", "Zara", "Halima", "Nafissa", "Amina",
    "Rakia", "Bibata", "Haoua", "Nana", "Safia",
]

LIEUX_NAISSANCE = [
    "Niamey", "Niamey", "Niamey", "Zinder", "Maradi",
    "Tahoua", "Agadez", "Dosso", "Tillabéri", "Diffa",
    "Konni", "Tessaoua", "Mirriah", "Gaya", "Say",
]

SERIES_BAC = ["A", "C", "D", "E", "G2", "F"]

UES_INFORMATIQUE_L1 = [
    ("INF101", "Introduction à l'Informatique", 6, 1),
    ("INF102", "Algorithmique I", 6, 1),
    ("MAT101", "Analyse Mathématique I", 4, 1),
    ("MAT102", "Algèbre I", 4, 1),
    ("PHY101", "Physique Générale", 3, 1),
    ("FRA101", "Techniques d'Expression Française", 3, 1),
    ("ANG101", "Anglais I", 2, 1),
    ("INF103", "Programmation C", 6, 2),
    ("INF104", "Architecture des Ordinateurs", 4, 2),
    ("MAT103", "Analyse Mathématique II", 4, 2),
    ("MAT104", "Algèbre II", 4, 2),
    ("INF105", "Systèmes d'Exploitation", 3, 2),
    ("ANG102", "Anglais II", 2, 2),
]

FRAIS = {
    "L1": [("inscription", 15000), ("scolarite", 25000), ("bibliotheque", 5000), ("assurance", 3000), ("carte_etudiant", 2000)],
    "L2": [("inscription", 15000), ("scolarite", 25000), ("bibliotheque", 5000), ("assurance", 3000)],
    "L3": [("inscription", 15000), ("scolarite", 25000), ("bibliotheque", 5000), ("assurance", 3000)],
    "M1": [("inscription", 25000), ("scolarite", 50000), ("bibliotheque", 5000), ("assurance", 3000)],
    "M2": [("inscription", 25000), ("scolarite", 50000), ("bibliotheque", 5000), ("assurance", 3000)],
}


def create_database():
    """Crée la base SQLite avec le schéma et les données de simulation."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # ── SCHÉMA ────────────────────────────────────────────────────────
    cur.executescript("""
    CREATE TABLE composantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sigle TEXT NOT NULL UNIQUE,
        nom_complet TEXT NOT NULL,
        type_composante TEXT NOT NULL CHECK(type_composante IN ('faculte','ecole','institut')),
        doyen_directeur TEXT,
        email_contact TEXT,
        telephone TEXT,
        adresse TEXT,
        date_creation TEXT
    );

    CREATE TABLE departements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        composante_id INTEGER NOT NULL,
        nom TEXT NOT NULL,
        chef_departement TEXT,
        FOREIGN KEY (composante_id) REFERENCES composantes(id)
    );

    CREATE TABLE formations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement_id INTEGER NOT NULL,
        intitule TEXT NOT NULL,
        niveau TEXT NOT NULL CHECK(niveau IN ('L1','L2','L3','M1','M2','D1','D2','D3')),
        type_formation TEXT DEFAULT 'initiale',
        capacite_accueil INTEGER,
        duree_semestres INTEGER DEFAULT 2,
        est_active INTEGER DEFAULT 1,
        FOREIGN KEY (departement_id) REFERENCES departements(id)
    );

    CREATE TABLE etudiants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        matricule TEXT NOT NULL UNIQUE,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        date_naissance TEXT NOT NULL,
        lieu_naissance TEXT,
        sexe TEXT NOT NULL CHECK(sexe IN ('M','F')),
        nationalite TEXT DEFAULT 'Nigérienne',
        telephone TEXT,
        email TEXT,
        adresse_niamey TEXT,
        type_etudiant TEXT NOT NULL,
        annee_bac INTEGER,
        serie_bac TEXT,
        mention_bac TEXT,
        etablissement_origine TEXT
    );

    CREATE TABLE inscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etudiant_id INTEGER NOT NULL,
        formation_id INTEGER NOT NULL,
        annee_academique TEXT NOT NULL,
        date_inscription TEXT,
        statut TEXT DEFAULT 'en_attente' CHECK(statut IN ('en_attente','validee','rejetee','annulee')),
        numero_recu TEXT,
        observations TEXT,
        FOREIGN KEY (etudiant_id) REFERENCES etudiants(id),
        FOREIGN KEY (formation_id) REFERENCES formations(id),
        UNIQUE(etudiant_id, formation_id, annee_academique)
    );

    CREATE TABLE paiements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inscription_id INTEGER NOT NULL,
        type_frais TEXT NOT NULL,
        montant REAL NOT NULL,
        date_paiement TEXT NOT NULL,
        mode_paiement TEXT DEFAULT 'especes',
        reference_paiement TEXT,
        FOREIGN KEY (inscription_id) REFERENCES inscriptions(id)
    );

    CREATE TABLE unites_enseignement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        formation_id INTEGER NOT NULL,
        code_ue TEXT NOT NULL,
        intitule TEXT NOT NULL,
        credits_ects INTEGER NOT NULL DEFAULT 3,
        semestre INTEGER NOT NULL,
        coefficient REAL DEFAULT 1.0,
        type_ue TEXT DEFAULT 'fondamentale',
        FOREIGN KEY (formation_id) REFERENCES formations(id)
    );

    CREATE TABLE resultats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inscription_id INTEGER NOT NULL,
        ue_id INTEGER NOT NULL,
        note_cc REAL,
        note_examen REAL,
        note_finale REAL,
        session TEXT DEFAULT 'normale',
        statut_ue TEXT DEFAULT 'en_attente',
        annee_academique TEXT,
        FOREIGN KEY (inscription_id) REFERENCES inscriptions(id),
        FOREIGN KEY (ue_id) REFERENCES unites_enseignement(id)
    );

    CREATE TABLE documents_delivres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etudiant_id INTEGER NOT NULL,
        type_document TEXT NOT NULL,
        date_demande TEXT,
        date_delivrance TEXT,
        statut TEXT DEFAULT 'demande',
        FOREIGN KEY (etudiant_id) REFERENCES etudiants(id)
    );

    -- Vues
    CREATE VIEW vue_situation_etudiant AS
    SELECT
        e.matricule,
        e.prenom || ' ' || e.nom AS nom_complet,
        e.type_etudiant,
        c.sigle AS composante,
        f.intitule AS formation,
        f.niveau,
        i.annee_academique,
        i.statut AS statut_inscription,
        i.date_inscription
    FROM etudiants e
    JOIN inscriptions i ON e.id = i.etudiant_id
    JOIN formations f ON i.formation_id = f.id
    JOIN departements d ON f.departement_id = d.id
    JOIN composantes c ON d.composante_id = c.id;

    CREATE VIEW vue_paiements_etudiant AS
    SELECT
        e.matricule,
        e.prenom || ' ' || e.nom AS nom_complet,
        i.annee_academique,
        p.type_frais,
        p.montant,
        p.date_paiement,
        p.mode_paiement
    FROM etudiants e
    JOIN inscriptions i ON e.id = i.etudiant_id
    JOIN paiements p ON i.id = p.inscription_id;

    CREATE VIEW vue_resultats_etudiant AS
    SELECT
        e.matricule,
        e.prenom || ' ' || e.nom AS nom_complet,
        ue.code_ue,
        ue.intitule AS nom_ue,
        ue.credits_ects,
        r.note_cc,
        r.note_examen,
        r.note_finale,
        r.session,
        r.statut_ue,
        r.annee_academique
    FROM etudiants e
    JOIN inscriptions i ON e.id = i.etudiant_id
    JOIN resultats r ON i.id = r.inscription_id
    JOIN unites_enseignement ue ON r.ue_id = ue.id;
    """)

    # ── INSERTION DES DONNÉES ─────────────────────────────────────────
    random.seed(42)  # Reproductibilité

    # 1. Composantes
    for sigle, nom, type_c in COMPOSANTES:
        cur.execute("""
            INSERT INTO composantes (sigle, nom_complet, type_composante, email_contact, telephone)
            VALUES (?, ?, ?, ?, ?)
        """, (sigle, nom, type_c, f"contact@{sigle.lower()}.uam.ne",
              f"+227 20 {random.randint(31,39)} {random.randint(10,99)} {random.randint(10,99)}"))

    # 2. Départements
    dept_map = {}  # sigle -> [(dept_id, dept_name)]
    for sigle, depts in DEPARTEMENTS.items():
        comp_id = cur.execute("SELECT id FROM composantes WHERE sigle=?", (sigle,)).fetchone()[0]
        for dept in depts:
            cur.execute("INSERT INTO departements (composante_id, nom) VALUES (?, ?)",
                        (comp_id, dept))
            dept_id = cur.lastrowid
            dept_map.setdefault(sigle, []).append((dept_id, dept))

    # 3. Formations (L1-M2 pour chaque département)
    formation_ids = {}
    for sigle, depts in dept_map.items():
        for dept_id, dept_name in depts:
            for niveau in ["L1", "L2", "L3", "M1", "M2"]:
                cap = {"L1": 200, "L2": 150, "L3": 120, "M1": 30, "M2": 25}[niveau]
                intitule = f"{niveau} {dept_name}"
                cur.execute("""
                    INSERT INTO formations (departement_id, intitule, niveau, capacite_accueil)
                    VALUES (?, ?, ?, ?)
                """, (dept_id, intitule, niveau, cap))
                fid = cur.lastrowid
                formation_ids[(sigle, dept_name, niveau)] = fid

    # 4. UEs pour Informatique L1
    info_l1_fid = formation_ids[("FAST", "Informatique", "L1")]
    ue_ids = []
    for code, intitule, credits, sem in UES_INFORMATIQUE_L1:
        cur.execute("""
            INSERT INTO unites_enseignement (formation_id, code_ue, intitule, credits_ects, semestre)
            VALUES (?, ?, ?, ?, ?)
        """, (info_l1_fid, code, intitule, credits, sem))
        ue_ids.append(cur.lastrowid)

    # 5. Étudiants (50 étudiants simulés)
    etudiants = []
    for i in range(50):
        sexe = random.choice(["M"] * 6 + ["F"] * 4)  # ratio réaliste
        nom = random.choice(NOMS_NIGERIENS)
        prenom = random.choice(PRENOMS_M if sexe == "M" else PRENOMS_F)
        annee_naiss = random.randint(1998, 2006)
        mois = random.randint(1, 12)
        jour = random.randint(1, 28)
        dn = f"{annee_naiss}-{mois:02d}-{jour:02d}"
        lieu = random.choice(LIEUX_NAISSANCE)
        matricule = f"UAM{annee_naiss % 100:02d}{i + 1:04d}"

        type_etud = random.choices(
            ["nouveau_bachelier", "reinscription", "candidat_master", "etudiant_etranger",
             "transfert_externe", "candidat_doctorat"],
            weights=[35, 40, 10, 5, 5, 5]
        )[0]

        annee_bac = random.randint(2018, 2024)
        serie = random.choice(SERIES_BAC)
        mention = random.choice(["Passable", "Passable", "Assez Bien", "Bien", "Très Bien"])
        nationalite = random.choice(["Nigérienne"] * 9 + ["Béninoise", "Togolaise", "Burkinabè"])

        cur.execute("""
            INSERT INTO etudiants
            (matricule, nom, prenom, date_naissance, lieu_naissance, sexe,
             nationalite, telephone, email, type_etudiant, annee_bac, serie_bac, mention_bac)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (matricule, nom, prenom, dn, lieu, sexe, nationalite,
              f"+227 {random.choice(['90','96','97'])}{random.randint(10,99)}{random.randint(1000,9999)}",
              f"{prenom.lower()}.{nom.lower()}@uam.ne",
              type_etud, annee_bac, serie, mention))
        etudiants.append((cur.lastrowid, matricule, type_etud))

    # 6. Inscriptions
    all_formations = list(formation_ids.items())
    inscriptions = []
    for etud_id, matricule, type_etud in etudiants:
        # Choisir une formation aléatoire cohérente
        if type_etud == "candidat_master":
            niveaux_ok = ["M1", "M2"]
        elif type_etud == "candidat_doctorat":
            niveaux_ok = ["M2"]  # en train de finir M2
        else:
            niveaux_ok = ["L1", "L2", "L3"]

        candidates = [(k, v) for k, v in formation_ids.items() if k[2] in niveaux_ok]
        if not candidates:
            candidates = [(k, v) for k, v in formation_ids.items() if k[2] == "L1"]
        key, fid = random.choice(candidates)

        annee_acad = random.choice(["2023-2024", "2024-2025"])
        statut = random.choices(
            ["validee", "en_attente", "rejetee"],
            weights=[70, 20, 10]
        )[0]
        date_insc = f"2024-{random.randint(9,11):02d}-{random.randint(1,28):02d}"

        cur.execute("""
            INSERT INTO inscriptions (etudiant_id, formation_id, annee_academique,
                                      date_inscription, statut, numero_recu)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (etud_id, fid, annee_acad, date_insc, statut,
              f"REC-{annee_acad[:4]}-{random.randint(1000,9999)}"))
        insc_id = cur.lastrowid
        inscriptions.append((insc_id, etud_id, key[2], statut))

    # 7. Paiements
    for insc_id, etud_id, niveau, statut in inscriptions:
        if statut in ("validee", "en_attente"):
            frais_niveau = FRAIS.get(niveau, FRAIS["L1"])
            nb_payes = random.randint(1, len(frais_niveau))
            for type_f, montant in frais_niveau[:nb_payes]:
                dt = f"2024-{random.randint(9,12):02d}-{random.randint(1,28):02d}"
                cur.execute("""
                    INSERT INTO paiements (inscription_id, type_frais, montant,
                                           date_paiement, mode_paiement, reference_paiement)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (insc_id, type_f, montant, dt,
                      random.choice(["especes", "mobile_money", "virement"]),
                      f"PAY-{random.randint(100000,999999)}"))

    # 8. Résultats (pour étudiants en L1 Informatique FAST avec inscription validée)
    info_inscs = [
        (insc_id, etud_id)
        for insc_id, etud_id, niveau, statut in inscriptions
        if statut == "validee" and niveau == "L1"
    ][:10]  # max 10 étudiants avec résultats

    for insc_id, etud_id in info_inscs:
        for ue_id in ue_ids:
            note_cc = round(random.uniform(5, 18), 2)
            note_exam = round(random.uniform(4, 19), 2)
            note_finale = round(0.4 * note_cc + 0.6 * note_exam, 2)
            statut_ue = "valide" if note_finale >= 10 else "non_valide"
            cur.execute("""
                INSERT INTO resultats (inscription_id, ue_id, note_cc, note_examen,
                                       note_finale, session, statut_ue, annee_academique)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (insc_id, ue_id, note_cc, note_exam, note_finale,
                  "normale", statut_ue, "2024-2025"))

    conn.commit()

    # ── STATISTIQUES ──────────────────────────────────────────────────
    stats = {
        "composantes": cur.execute("SELECT COUNT(*) FROM composantes").fetchone()[0],
        "departements": cur.execute("SELECT COUNT(*) FROM departements").fetchone()[0],
        "formations": cur.execute("SELECT COUNT(*) FROM formations").fetchone()[0],
        "etudiants": cur.execute("SELECT COUNT(*) FROM etudiants").fetchone()[0],
        "inscriptions": cur.execute("SELECT COUNT(*) FROM inscriptions").fetchone()[0],
        "paiements": cur.execute("SELECT COUNT(*) FROM paiements").fetchone()[0],
        "ues": cur.execute("SELECT COUNT(*) FROM unites_enseignement").fetchone()[0],
        "resultats": cur.execute("SELECT COUNT(*) FROM resultats").fetchone()[0],
    }

    conn.close()

    print(f"Base de données créée : {DB_PATH}")
    print(f"\nStatistiques :")
    for table, count in stats.items():
        print(f"  {table:20s} : {count:>5d} enregistrements")

    # Exemples de requêtes chatbot
    conn = sqlite3.connect(DB_PATH)
    print("\n─── Exemples de requêtes chatbot ───")

    print("\n1. Situation d'un étudiant par matricule :")
    row = conn.execute("SELECT * FROM vue_situation_etudiant LIMIT 1").fetchone()
    print(f"   {row}")

    print("\n2. Paiements d'un étudiant :")
    row = conn.execute("SELECT * FROM vue_paiements_etudiant LIMIT 1").fetchone()
    print(f"   {row}")

    print("\n3. Étudiants en attente d'inscription :")
    count = conn.execute("SELECT COUNT(*) FROM inscriptions WHERE statut='en_attente'").fetchone()[0]
    print(f"   {count} inscriptions en attente")

    print("\n4. Résultats d'un étudiant :")
    row = conn.execute("SELECT * FROM vue_resultats_etudiant LIMIT 1").fetchone()
    print(f"   {row}")

    conn.close()
    return DB_PATH


if __name__ == "__main__":
    create_database()

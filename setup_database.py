"""
Script d'initialisation et de peuplement de la base de données UAM
Basé sur les données du fichier Info.txt
"""

import sqlite3
from pathlib import Path
import os


def create_database_schema(db_path: str = "./uam_database.db"):
    """Crée le schéma de la base de données UAM"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Création du schéma de la base de données...")
    
    # Table des structures (Facultés, Écoles, Instituts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS structures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            type TEXT NOT NULL,
            mission TEXT,
            composition TEXT,
            objectifs TEXT
        )
    """)
    
    # Table des formations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS formations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            structure_id INTEGER NOT NULL,
            nom TEXT NOT NULL,
            niveau TEXT NOT NULL,
            conditions_acces TEXT,
            pieces_requises TEXT,
            objectifs TEXT,
            FOREIGN KEY (structure_id) REFERENCES structures(id)
        )
    """)
    
    # Table des filières
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filieres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formation_id INTEGER NOT NULL,
            nom TEXT NOT NULL,
            description TEXT,
            debouches TEXT,
            FOREIGN KEY (formation_id) REFERENCES formations(id)
        )
    """)
    
    # Table des horaires de service
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS horaires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            jours TEXT NOT NULL,
            heures_ouverture TEXT NOT NULL,
            heures_fermeture TEXT NOT NULL,
            notes TEXT
        )
    """)
    
    # Table des frais de scolarité
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scolarite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_inscription TEXT NOT NULL,
            niveau TEXT NOT NULL,
            frais_inscription INTEGER DEFAULT 0,
            frais_scolarite INTEGER DEFAULT 0,
            frais_labo INTEGER DEFAULT 0,
            periode TEXT
        )
    """)
    
    conn.commit()
    print("✓ Schéma de la base de données créé avec succès!")
    
    return conn, cursor


def populate_database(db_path: str = "./uam_database.db"):
    """Remplit la base de données avec les données UAM"""
    
    # Créer le schéma si nécessaire
    conn, cursor = create_database_schema(db_path)
    
    # Vérifier si les données existent déjà
    cursor.execute("SELECT COUNT(*) FROM structures")
    if cursor.fetchone()[0] > 0:
        print("⚠️ La base de données contient déjà des données.")
        response = input("Voulez-vous réinitialiser la base de données? (oui/non): ")
        if response.lower() in ['oui', 'o', 'yes', 'y']:
            cursor.execute("DELETE FROM filieres")
            cursor.execute("DELETE FROM formations")
            cursor.execute("DELETE FROM structures")
            cursor.execute("DELETE FROM horaires")
            cursor.execute("DELETE FROM scolarite")
            conn.commit()
            print("✓ Base de données réinitialisée")
        else:
            print("Opération annulée.")
            conn.close()
            return
    
    print("\nPeuplement de la base de données UAM...")

    # ========================================================================
    # 1. STRUCTURES (Facultés, Écoles, Instituts)
    # ========================================================================
    # Ordre d'insertion → IDs auto-incrémentés :
    # 1=FAST  2=FA  3=FLSH  4=FSS  5=FSEG  6=FSJP  7=ENS  8=IRSH  9=IREM  10=IRI
    # Note : FSEJ (Faculté des Sciences Économiques et Juridiques) a été scindée
    # en 2016 en FSEG (économie/gestion) et FSJP (droit/sciences politiques).

    structures = [
        (
            "Faculté des Sciences et Techniques (FAST)",
            "Faculté",
            "Assurer la formation d'enseignants et de chercheurs dans le domaine des sciences et techniques, "
            "le recyclage des cadres pour différents types d'activités scientifiques et techniques, "
            "la préparation à l'entrée aux grandes écoles, et promouvoir des activités de recherche fondamentale et appliquée.",
            "Décanat, Vice-Doyen, Secrétaire Principal. Départements : Mathématiques et Informatique, Physique, "
            "Chimie, Biologie, Géologie. Services : Financier, Personnel, Scolarité et examens, Bibliothèque.",
            "Formation d'enseignants, chercheurs et cadres scientifiques de haut niveau"
        ),
        (
            "Faculté d'Agronomie (FA)",
            "Faculté",
            "Former, perfectionner et recycler des Ingénieurs d'application, Ingénieurs de conception et Cadres "
            "supérieurs dans les domaines du développement rural, des industries alimentaires, des biotechnologies "
            "et des activités connexes.",
            "Décanat, Secrétaire Principal. 7 Départements : Productions Animales (DPA), Productions Végétales (DPV), "
            "Génie Rural/Eaux et Forêts (D/GREF), Sciences du Sol (DSS), Sociologie et Économie Rurales (DSER), "
            "Sciences Fondamentales (DSF), Formation Pratique (DFP). "
            "Centres d'excellence : CRESA, CERPP. Services : Scolarité, Finances, Bibliothèque, Informatique.",
            "Sécurité alimentaire, agriculture durable, développement rural"
        ),
        (
            "Faculté des Lettres et Sciences Humaines (FLSH)",
            "Faculté",
            "Assurer la formation générale et professionnelle en lettres et sciences humaines, la formation des "
            "enseignants du secondaire et supérieur, le recyclage des cadres et la promotion de la recherche "
            "fondamentale et appliquée dans les domaines des lettres et sciences sociales.",
            "Décanat, 8 Départements (Lettres Modernes, Anglais, Histoire, Géographie, Philosophie-Sociologie, "
            "Langues nationales, etc.). Centre de Langues. Services : Scolarité, Bibliothèque.",
            "Culture, patrimoine, recherche en lettres et sciences humaines"
        ),
        (
            "Faculté des Sciences de la Santé (FSS)",
            "Faculté",
            "Assurer la promotion constante de la santé individuelle, familiale et collective et le progrès des "
            "sciences de la santé dans la région sahélienne. Former le personnel de santé de toutes catégories "
            "pour le rendre pleinement opérationnel, capable de travailler en équipe et ouvert à la formation permanente.",
            "Décanat, Vice-Doyen. Départements : Médecine et Spécialités Médicales, Chirurgie et Spécialités "
            "Chirurgicales, Sciences Fondamentales et Mixtes, Santé Publique, Sciences physico-chimiques et "
            "pharmaceutiques, Sciences biologiques Appliquées, Spécialités cliniques dentaires.",
            "Excellence médicale, santé publique, recherche biomédicale"
        ),
        (
            "Faculté des Sciences Économiques et de Gestion (FSEG)",
            "Faculté",
            "Offrir des formations adaptées aux besoins de la société dans les domaines de l'économie et de la gestion, "
            "promouvoir la recherche fondamentale et appliquée, et développer des services de qualité. "
            "La FSEG est issue de la scission de la FSEJ en 2016 (décret n°2016-308/PRN/MESR/I du 29 juin 2016).",
            "Décanat, Secrétariat Principal. Départements : Économie, Gestion. "
            "Services : Personnel et Matériel, Financier, Scolarité, Documentation, Courrier, TICE.",
            "Développement économique, bonne gouvernance, entrepreneuriat"
        ),
        (
            "Faculté des Sciences Juridiques et Politiques (FSJP)",
            "Faculté",
            "Assurer la formation des cadres pour les activités juridiques et politiques, des enseignants pour "
            "l'enseignement secondaire et supérieur en matière juridique et politique, et des chercheurs dans ces domaines. "
            "La FSJP est issue de la scission de la FSEJ en 2016 (décret n°2016-308/PRN/MESR/I du 29 juin 2016).",
            "Décanat. Départements : Droit Privé, Droit Public, Science Politique. "
            "Services : Secrétariat Principal, Financier, Personnel et Matériel, Scolarité, TICE, Documentation, Courrier.",
            "État de droit, sciences politiques, administration publique"
        ),
        (
            "École Normale Supérieure (ENS)",
            "École",
            "Formation initiale professionnelle théorique et pratique des formateurs et cadres de contrôle et "
            "d'animation pédagogique pour l'Enseignement de Base 1, de l'éducation non formelle, des Cycles de "
            "Base 2 et Moyen, et de l'Enseignement Professionnel et Technique. Formation continue et recyclage du "
            "personnel enseignant. Formation en administration de l'éducation. Recherche scientifique fondamentale et appliquée.",
            "Direction, Vice-direction, Secrétaire Principal. 9 Départements opérationnels : Anglais, Chimie, "
            "Français, Géographie, Histoire, Mathématiques, Physique, Sciences de l'éducation, SVT. "
            "4 départements en création : Philosophie, Arabe, Linguistique et langues nationales, Enseignement "
            "Professionnel et Technique. Laboratoires : Chimie, Physique, SVT. "
            "Centres : CEA/IEA-MS4SSA. Services : Scolarité, Bibliothèque, Personnel, Matériel, Financier, Audiovisuel, Stages.",
            "Excellence pédagogique, formation des formateurs, recherche en éducation"
        ),
        (
            "Institut de Recherches en Sciences Humaines (IRSH)",
            "Institut",
            "Effectuer des travaux de recherches en sciences humaines et sociales sur le Niger et l'Afrique, "
            "notamment en paléontologie et paléoanthropologie. Contribuer à la formation des chercheurs et étudiants "
            "en sciences humaines. Participer à la sauvegarde et la revalorisation du patrimoine culturel nigérien. "
            "Rechercher des solutions aux problèmes de développement.",
            "6 Départements scientifiques : Art et Archéologie (DARA), Histoire et Traditions Populaires (HISTRA), "
            "Langues nationales et linguistique (LILAN), Sociologie du Développement (SODEV), "
            "Géographie et Aménagement de l'Espace (GAME), Manuscrits Arabes et Ajami (MARA). "
            "3 Services Techniques : Documentation (SEDO), Audiovisuel (SERVA), Archives (SERAR). "
            "Bibliothèque : ~30 000 volumes, 250 titres de périodiques. Bases à Agadez et Maradi.",
            "Recherche en sciences humaines, sauvegarde du patrimoine culturel nigérien"
        ),
        (
            "Institut de Recherches sur l'Enseignement des Mathématiques (IREM)",
            "Institut",
            "Formation continue des enseignants de mathématiques du secondaire. Recherche-développement sur "
            "l'enseignement des mathématiques. Rénovation et adaptation constante des programmes. "
            "Conception et production de supports didactiques. Promotion de la culture mathématique.",
            "Direction, Secrétariat Principal. 4 chercheurs, 3 PAT. "
            "Institut Geogebra (2e en Afrique). Participation aux réseaux IREM internationaux, EMF, CANP.",
            "Formation continue des enseignants, recherche didactique, culture mathématique"
        ),
        (
            "Institut des Radio-Isotopes (IRI)",
            "Institut",
            "Entreprendre et promouvoir des activités de recherche appliquée et fondamentale sur l'utilisation "
            "pacifique des radio-isotopes et des techniques nucléaires. Assurer des enseignements et des recherches "
            "spécifiques et la formation des personnels dans ce domaine. Entretenir et mettre à disposition un "
            "appareillage nucléaire. Assurer les prestations techniques demandées par les ministères et organismes.",
            "Départements : Radio-Agronomie et Écophysiologie Végétale, Physique et Chimie Nucléaires, Médecine Nucléaire. "
            "Laboratoires : Fertilité des Sols, Biotechnologie et Amélioration des Plantes, Biosécurité, "
            "Fluorescence X, Datation C14, Azote liquide. Unités : Scintigraphie, Radio-immunoanalyse, Irathérapie. "
            "12 chercheurs, 18 PAT.",
            "Recherche nucléaire appliquée, médecine nucléaire, radio-agronomie"
        ),
    ]

    cursor.executemany("""
        INSERT INTO structures (nom, type, mission, composition, objectifs)
        VALUES (?, ?, ?, ?, ?)
    """, structures)

    # ========================================================================
    # 2. FORMATIONS
    # IDs auto-incrémentés — l'ordre d'insertion définit les formation_id utilisés
    # dans la table filieres ci-dessous. Ne pas réordonner sans mettre à jour filieres.
    #
    # FAST (1) : ids 1-17
    # FA   (2) : ids 18-27
    # FLSH (3) : ids 28-32
    # FSS  (4) : ids 33-55
    # FSEG (5) : ids 56-59
    # FSJP (6) : ids 60-64
    # ENS  (7) : ids 65-69
    # ========================================================================

    formations = [
        # ── FAST — Faculté des Sciences et Techniques (structure_id=1) ──────
        # Licences (ids 1-6)
        (1, "Licence en Mathématiques", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des mathématiciens polyvalents pour la recherche et l'enseignement"),
        (1, "Licence en Informatique", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des informaticiens polyvalents pour l'industrie et la recherche"),
        (1, "Licence en Physique Fondamentale", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des physiciens de haut niveau"),
        (1, "Licence en Chimie Fondamentale", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des chimistes de haut niveau"),
        (1, "Licence en Géologie", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des géologues pour les secteurs minier, pétrolier et environnemental"),
        (1, "Licence SVT (Sciences de la Vie et de la Terre)", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des biologistes et écologistes"),
        # Masters (ids 7-16)
        (1, "Master Recherche : Structure de la Matière et Rayonnement", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés L1-L3, CV, lettre de motivation, 4 photos",
            "Former des experts en physique fondamentale : particules, interactions électrofaibles, chromodynamique quantique"),
        (1, "Master Recherche : Énergies Renouvelables", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés L1-L3, CV, lettre de motivation",
            "Former des experts en conversions photovoltaïque, éolienne, bioénergétique et dimensionnement d'installations"),
        (1, "Master Recherche : Physique de l'Atmosphère et Climat", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés L1-L3, CV, lettre de motivation",
            "Former des experts en physique des nuages, dynamique des systèmes convectifs et chimie atmosphérique"),
        (1, "Master Recherche : Électronique-Électrotechnique-Automatique (EEA)", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés L1-L3, CV, lettre de motivation",
            "Former des experts en électronique, électrotechnique, automatique et informatique industrielle"),
        (1, "Master Recherche : Informatique Fondamentale et Appliquée", "Master",
            "Licence ou Bachelor en Informatique avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés complets, CV, lettre de motivation",
            "Formation scientifique de haut niveau en informatique pour insertion professionnelle et/ou préparation de thèse"),
        (1, "Master Professionnel : MIAGE (Méthodes Informatiques Appliquées à la Gestion des Entreprises)", "Master",
            "Licence en Informatique, Mathématiques, Économie ou Gestion",
            "Diplôme de Licence, relevés complets, CV",
            "Former des professionnels en informatique, réseaux et gestion financière/comptable"),
        (1, "Master Recherche : Mathématiques — Géométrie et Algèbre", "Master",
            "Licence ou Bachelor en Mathématiques",
            "Diplôme de Licence, relevés complets, CV",
            "Initier à la recherche en mathématiques : géométrie, algèbre, applications industrielles"),
        (1, "Master Recherche et Professionnel : Géoressources", "Master",
            "Licence en Géosciences avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés complets, CV, lettre de motivation",
            "Former des experts en géologie minière et pétrolière, valorisation des ressources"),
        (1, "Master Recherche : Géosciences de l'Environnement (MISE)", "Master",
            "Licence en Bio/Géosciences (Biologie, Géologie, Pédologie, Agronomie, Géographie physique)",
            "Diplôme de Licence, relevés complets, CV",
            "Gestion durable des écosystèmes terrestres, audit et évaluation environnementale"),
        (1, "Master Recherche : Biologie des Organismes et des Populations — Entomologie Appliquée", "Master",
            "Licence en Sciences Biologiques",
            "Diplôme de Licence, relevés complets, CV",
            "Former des experts en biologie et gestion des insectes (agriculture et santé)"),
        # Doctorat (id 17)
        (1, "Doctorat en Sciences", "Doctorat",
            "Master recherche avec mention Bien ou Très Bien, projet de thèse accepté par un directeur",
            "Diplôme de Master, relevés complets, projet de recherche, 2 lettres de recommandation",
            "Former des chercheurs et enseignants-chercheurs de haut niveau"),

        # ── FA — Faculté d'Agronomie (structure_id=2) ───────────────────────
        # (ids 18-27)
        (2, "Licence Générale ès Sciences Agronomiques", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original, relevés du Bac, certificat médical, 4 photos, acte de naissance",
            "Former des techniciens agricoles polyvalents"),
        (2, "Master 1 ès Sciences Agronomiques", "Master",
            "Licence en Agronomie ou diplôme équivalent",
            "Diplôme de Licence, relevés complets, CV",
            "Approfondissement scientifique en agronomie — socle du Master 2"),
        (2, "Master 2 : CRESA — Protection de l'Environnement", "Master",
            "Master 1 en Agronomie ou diplôme équivalent avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des experts en protection de l'environnement et gestion durable des ressources — depuis 1989"),
        (2, "Master 2 : Phytotechnie", "Master",
            "Master 1 en Agronomie ou diplôme équivalent avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des ingénieurs agronomes spécialisés en production végétale et amélioration varietale — depuis 2010"),
        (2, "Master 2 : Économie Rurale", "Master",
            "Master 1 en Agronomie, Économie ou Gestion avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des spécialistes en économie agricole et développement rural — depuis 2010"),
        (2, "Master 2 : Gestion Intégrée des Sols et des Eaux", "Master",
            "Master 1 en Agronomie, Géologie ou Environnement avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des experts en conservation et gestion durable des ressources sol et eau — depuis 2013"),
        (2, "Master 2 : Nutrition Humaine et Technologies Agroalimentaires", "Master",
            "Master 1 en Agronomie, Biologie, Biochimie ou diplôme d'ingénieur des techniques agricoles",
            "Diplôme de Master 1, relevés complets, CV",
            "Former des experts en nutrition, sciences des aliments et technologie agroalimentaire — depuis 2013"),
        (2, "Master 2 : Foresterie et Gestion Durable des Ressources Naturelles", "Master",
            "Master 1 en Agronomie, Environnement ou Foresterie avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des spécialistes en foresterie et gestion durable des ressources naturelles — depuis 2018"),
        (2, "Master 2 : Productions Animales (CERPP)", "Master",
            "Master 1 en Agronomie, Sciences Animales ou Vétérinaire avec moyenne ≥ 11/20",
            "Diplôme de Master 1, relevés complets, CV, lettre de motivation",
            "Former des spécialistes en productions pastorales (lait, viande, cuirs) — Centre d'Excellence Régional CERPP"),
        (2, "Licence Professionnelle en Génie Rural", "Licence",
            "Baccalauréat technique ou scientifique, ou BTS en génie rural ou équivalent",
            "Diplôme requis, relevés, CV, acte de naissance, 4 photos",
            "Former des techniciens supérieurs en aménagement rural et gestion de l'eau — depuis 2021"),

        # ── FLSH — Faculté des Lettres et Sciences Humaines (structure_id=3) ─
        # (ids 28-32)
        (3, "Licence en Lettres Modernes", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des spécialistes en littérature et langue françaises"),
        (3, "Licence en Anglais", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des spécialistes en langue et civilisation anglaises"),
        (3, "Licence en Histoire", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des historiens et chercheurs en histoire africaine et mondiale"),
        (3, "Licence en Géographie", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des géographes et aménageurs du territoire"),
        (3, "Master Recherche : Histoire Africaine", "Master",
            "Licence en Histoire ou Histoire-Géographie avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés complets, CV, projet de recherche",
            "Former des historiens-chercheurs spécialisés en histoire de l'Afrique"),

        # ── FSS — Faculté des Sciences de la Santé (structure_id=4) ─────────
        # Formations initiales (ids 33-34)
        (4, "Doctorat d'État en Médecine (Médecine Générale)", "Doctorat",
            "Baccalauréat série C ou D avec mention Bien minimum, OU diplôme d'infirmier/sage-femme + concours spécial. Concours d'entrée réussi.",
            "Bac original certifié OU diplôme infirmier/sage-femme, certificat médical complet, 6 photos, casier judiciaire, certificat de visite et contre-visite",
            "Former des médecins généralistes compétents — 7 ans (14 semestres)"),
        (4, "Doctorat d'État en Pharmacie", "Doctorat",
            "Baccalauréat série C, D ou E ou diplôme équivalent",
            "Bac original certifié, relevés du Bac, certificat de nationalité, 4 photos, acte de naissance",
            "Former des pharmaciens généralistes — 6 ans (12 semestres)"),
        # DES — Diplômes d'Études Spécialisées (ids 35-46)
        (4, "DES : Chirurgie Générale (DES-CHG)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des chirurgiens généralistes — 5 ans"),
        (4, "DES : Gynécologie-Obstétrique (DES-GYO)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des gynécologues-obstétriciens — 4 ans"),
        (4, "DES : Médecine Interne (DES-MIN)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des médecins internistes — 4 ans"),
        (4, "DES : Pédiatrie (DES-PED)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des pédiatres — 4 ans"),
        (4, "DES : Cardiologie (DES-CAR)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des cardiologues — 4 ans"),
        (4, "DES : Neurochirurgie (DES-NRC)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des neurochirurgiens — 5 ans"),
        (4, "DES : Chirurgie Pédiatrique (DES-CPD)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des chirurgiens pédiatriques — 5 ans"),
        (4, "DES : Ophtalmologie (DES-OPH)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des ophtalmologistes — 4 ans"),
        (4, "DES : Orthopédie-Traumatologie (DES-COT)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des chirurgiens orthopédistes-traumatologues — 5 ans"),
        (4, "DES : Biologie Clinique (DES-BIO)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des biologistes cliniques — 4 ans"),
        (4, "DES : Anesthésie-Réanimation (DES-ANR)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des anesthésistes-réanimateurs — 4 ans"),
        (4, "DES : Anatomie Pathologique (DES-ANP)", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, attestations de service",
            "Former des anatomopathologistes — 4 ans"),
        # Licences paramédicales (ids 47-52)
        (4, "Licence Professionnelle : Techniciens Supérieurs en Chirurgie et Gynéco-Obstétrique (CGO)", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en chirurgie et gynécologie-obstétrique — 3 ans"),
        (4, "Licence Professionnelle : Techniciens Supérieurs en Anesthésie-Réanimation", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en anesthésie-réanimation — 3 ans"),
        (4, "Licence Professionnelle : Techniciens Supérieurs en Radiologie", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en radiologie médicale — 3 ans"),
        (4, "Licence Professionnelle : Techniciens Supérieurs en Ophtalmologie", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en ophtalmologie — 3 ans"),
        (4, "Licence Professionnelle : Techniciens Supérieurs en ORL (Oto-Rhino-Laryngologie)", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en ORL — 3 ans"),
        (4, "Licence Professionnelle : Techniciens Supérieurs en Santé Mentale", "Licence",
            "Diplôme d'infirmier ou de sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, attestation de service, 4 photos",
            "Former des techniciens supérieurs en santé mentale — 3 ans"),
        # Masters paramédicaux (ids 53-54)
        (4, "Master Professionnel : Chirurgie et Gynécologie-Obstétrique (CGO)", "Master",
            "Licence générale dans le domaine de la santé OU licence professionnelle avec 2 ans d'expérience",
            "Diplôme de Licence, relevés complets, CV, attestation d'expérience",
            "Former des techniciens supérieurs en CGO — 2 ans (4 semestres)"),
        (4, "Master Professionnel : Anesthésie et Réanimation", "Master",
            "Licence générale dans le domaine de la santé OU licence professionnelle avec 2 ans d'expérience",
            "Diplôme de Licence, relevés complets, CV, attestation d'expérience",
            "Former des techniciens supérieurs en anesthésie-réanimation — 2 ans (4 semestres)"),
        # Licence sciences infirmières (id 55)
        (4, "Licence en Sciences Infirmières", "Licence",
            "Baccalauréat série C, D ou équivalent, concours d'entrée",
            "Bac certifié, certificat médical, 4 photos, acte de naissance",
            "Former des infirmiers diplômés d'État"),

        # ── FSEG — Faculté des Sciences Économiques et de Gestion (structure_id=5)
        # (ids 56-59)
        (5, "Licence en Gestion", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des gestionnaires d'entreprise et de l'administration"),
        (5, "Licence en Économie — Analyse des Politiques Économiques", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des économistes analystes pour le secteur public et privé"),
        (5, "Master Professionnel : Finance", "Master",
            "Licence en Gestion, Économie ou Finance avec moyenne ≥ 11/20",
            "Diplôme de Licence, relevés complets, CV, lettre de motivation",
            "Former des experts en finance d'entreprise, comptabilité et audit"),
        (5, "DESS Professionnel : Gestion Macroéconomique", "DESS",
            "Maîtrise ou Master 1 en Économie",
            "Diplôme, relevés complets, CV",
            "Former des experts en gestion macroéconomique et politiques économiques"),

        # ── FSJP — Faculté des Sciences Juridiques et Politiques (structure_id=6)
        # (ids 60-64)
        (6, "Capacité en Droit", "Capacité",
            "Niveau baccalauréat ou équivalent",
            "Copie relevés scolaires, 4 photos, acte de naissance",
            "Diplôme de base en droit accessible sans baccalauréat — 2 ans"),
        (6, "Licence en Droit — Carrières Judiciaires", "Licence",
            "Baccalauréat série A, B, G ou équivalent OU Capacité en Droit avec moyenne ≥ 12/20",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des juristes pour les carrières judiciaires (magistrature, barreau, notariat)"),
        (6, "Licence en Droit — Carrières Internationales", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des juristes spécialisés en droit international et relations internationales"),
        (6, "Licence en Droit Public", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, relevés du Bac, 4 photos, acte de naissance",
            "Former des juristes spécialisés en droit public et administration"),
        (6, "DESS Professionnel : Droit et Administration des Collectivités Territoriales", "DESS",
            "Maîtrise ou Master 1 en Droit",
            "Diplôme, relevés complets, CV",
            "Former des experts en administration territoriale et droit des collectivités"),

        # ── ENS — École Normale Supérieure (structure_id=7) ─────────────────
        # (ids 65-69)
        (7, "DAP/CEG — Diplôme d'Aptitude au Professorat des Collèges d'Enseignement Général", "Diplôme",
            "Baccalauréat ou équivalent (concours ou sélection de dossier)",
            "Bac original, relevés, 4 photos, acte de naissance",
            "Former des professeurs de CEG dans les disciplines scientifiques et littéraires — 2 ans"),
        (7, "Formation des Conseillers Pédagogiques de l'Enseignement de Base 1", "Diplôme",
            "Instituteurs de l'Enseignement de Base 1 (concours professionnel)",
            "Diplôme d'instituteur, attestation de service, 4 photos",
            "Former des conseillers pédagogiques pour l'Enseignement de Base 1 — 2 ans"),
        (7, "Professeurs Certifiés (CAPES — Certificat d'Aptitude au Professorat de l'Enseignement Secondaire)", "Diplôme",
            "Titulaire d'une Maîtrise (Bac+4)",
            "Diplôme de Maîtrise, relevés complets, CV",
            "Former des professeurs certifiés pour les lycées — 1 an"),
        (7, "Master Francophone : Métiers de la Formation", "Master",
            "Licence (Bac+3) ou Maîtrise (Bac+4)",
            "Diplôme, relevés complets, CV",
            "Master en partenariat avec RIFEFF et AUF — formation en semi-présentiel"),
        (7, "Master ICGAE — Ingénierie, Conception et Gestion des Alternatives Éducatives", "Master",
            "Licence (Bac+3) ou Maîtrise (Bac+4)",
            "Diplôme, relevés complets, CV",
            "Former des ingénieurs en innovation pédagogique et gestion des systèmes éducatifs — en partenariat avec la Coopération Suisse"),
    ]

    cursor.executemany("""
        INSERT INTO formations (structure_id, nom, niveau, conditions_acces, pieces_requises, objectifs)
        VALUES (?, ?, ?, ?, ?, ?)
    """, formations)

    # ========================================================================
    # 3. FILIÈRES
    # Les formation_id correspondent aux positions dans la liste formations ci-dessus.
    # ========================================================================

    filieres = [
        # FAST — Licence Mathématiques (formation_id=1)
        (1,  "Mathématiques Fondamentales",    "Algèbre, analyse et géométrie",                        "Recherche, enseignement, actuariat"),
        (1,  "Mathématiques Appliquées",        "Modélisation mathématique et calcul scientifique",     "Ingénierie, statistiques, data science"),
        # FAST — Licence Informatique (formation_id=2)
        (2,  "Génie Logiciel",                  "Développement d'applications et systèmes",             "Développeur, chef de projet, architecte logiciel"),
        (2,  "Réseaux et Systèmes",              "Administration et sécurité des réseaux",               "Administrateur réseau, ingénieur cybersécurité"),
        (2,  "Intelligence Artificielle",        "Machine learning et traitement de données",            "Data scientist, ingénieur IA, chercheur"),
        # FA — Licence Agronomie (formation_id=18)
        (18, "Agronomie Générale",              "Production agricole durable",                           "Agronome, conseiller agricole, chef d'exploitation"),
        (18, "Génie Rural",                     "Hydraulique agricole, aménagement rural",               "Ingénieur en génie rural, responsable irrigation"),
        # FA — Master Phytotechnie (formation_id=21)
        (21, "Phytotechnie",                    "Culture des plantes et amélioration variétale",         "Ingénieur agronome, sélectionneur, chercheur"),
        # FA — Master Économie Rurale (formation_id=22)
        (22, "Économie Agricole",               "Analyse économique des filières agricoles",             "Économiste agricole, analyste de politiques rurales"),
        # FSEG — Licence Gestion (formation_id=56)
        (56, "Comptabilité-Gestion",            "Techniques comptables et contrôle de gestion",         "Comptable, auditeur, contrôleur de gestion"),
        (56, "Management des Organisations",    "Direction et organisation des entreprises",             "Manager, responsable RH, consultant"),
        # FSEG — Master Finance (formation_id=58)
        (58, "Finance d'Entreprise",            "Gestion financière et investissements",                 "Analyste financier, trésorier, gestionnaire de portefeuille"),
        (58, "Audit et Contrôle de Gestion",    "Audit interne, contrôle et reporting",                  "Auditeur, contrôleur de gestion, directeur financier"),
        # FSJP — Licence Droit Judiciaire (formation_id=61)
        (61, "Droit Privé",                     "Droit civil, commercial et des affaires",               "Avocat, notaire, juriste d'entreprise"),
        (61, "Droit Pénal",                     "Procédure pénale et criminologie",                      "Magistrat, avocat pénaliste, juriste de sécurité"),
        # FSJP — Licence Droit Public (formation_id=63)
        (63, "Droit Administratif",             "Droit public, contentieux administratif",               "Fonctionnaire, juriste administratif, magistrat administratif"),
        (63, "Science Politique",               "Institutions politiques, relations internationales",    "Politologue, diplomate, chercheur en sciences politiques"),
    ]

    cursor.executemany("""
        INSERT INTO filieres (formation_id, nom, description, debouches)
        VALUES (?, ?, ?, ?)
    """, filieres)
    
    # ========================================================================
    # 4. HORAIRES DE SERVICE
    # ========================================================================
    
    horaires = [
        ("Scolarité Centrale (ENS)", "Lundi-Vendredi", "07h30", "15h30", "BP 237/10 896 Niamey, Tel: 20 74 06 61"),
        ("Secrétariat FAST", "Lundi-Vendredi", "08h00", "16h00", "BP 10662 Niamey, Tel: 20 31 50 72"),
        ("Secrétariat FA", "Lundi-Vendredi", "08h00", "15h00", "BP 10960 Niamey, Tel: 20 31 52 37"),
        ("Secrétariat FLSH", "Lundi-Vendredi", "07h30", "15h30", "BP 418 Niamey, Tel: 20 31 72 55 / 20 31 56 90"),
        ("Secrétariat FSEG", "Lundi-Vendredi", "08h00", "16h00", "BP 12 442 Niamey, Tel: 20 74 09 41"),
        ("Secrétariat FSJP", "Lundi-Vendredi", "08h00", "16h00", "BP 12 442 Niamey"),
        ("Secrétariat FSS", "Lundi-Vendredi", "08h00", "16h00", "BP 10896 Niamey, Tel: 20 31 57 26 / 20 31 57 27"),
        ("Secrétariat ENS", "Lundi-Vendredi", "08h00", "16h00", "BP 10963 Niamey, Tel: 20 31 53 45"),
        ("Bibliothèque Universitaire Centrale (BUC)", "Lundi-Samedi", "08h00", "21h00", "BP 237/10 896 Niamey, Tel: 20 74 12 73. Dimanche: 09h00-13h00"),
        ("Service des Diplômes", "Lundi-Jeudi", "08h00", "14h00", "Vendredi: 08h00-12h00"),
        ("Service des Relations Extérieures", "Lundi-Vendredi", "08h00", "16h00", "BP 237 Niamey, Tel: 20 31 55 31"),
        ("Service Central des Équivalences", "Lundi-Vendredi", "08h00", "16h00", "BP 237/10 896 Niamey"),
        ("CNOU - Restaurant Universitaire", "7 jours/7", "07h00", "20h00", "Petit déjeuner: 7h-8h, Déjeuner: 11h30-14h (11h-13h vendredi), Dîner: 18h-20h"),
        ("CNOU - Service Médical", "Lundi-Vendredi", "07h30", "18h00", "Urgences 24h/24, BP 13569 Niamey, Tel: 20 31 51 66/67"),
        ("CNOU - Transport Universitaire", "Lundi-Vendredi", "06h30", "19h30", "Navette campus-ville"),
        ("Campus Numérique Francophone", "Lundi-Vendredi", "08h00", "18h00", "Faculté d'Agronomie, Tel: 20 31 70 20"),
        ("IRSH", "Lundi-Vendredi", "08h00", "16h00", "68 rue de l'institut, BP 318 Niamey, Tel: 20 73 55 39"),
        ("IRI", "Lundi-Vendredi", "08h00", "16h00", "BP 10727 Niamey, Tel: 20 31 58 50"),
        ("IREM", "Lundi-Vendredi", "08h00", "16h00", "BP 237 Niamey, Tel: 20 31 57 72")
    ]
    
    cursor.executemany("""
        INSERT INTO horaires (service, jours, heures_ouverture, heures_fermeture, notes)
        VALUES (?, ?, ?, ?, ?)
    """, horaires)
    
    # ========================================================================
    # 5. FRAIS DE SCOLARITÉ
    # ========================================================================
    
    scolarite = [
        # Frais d'inscription — 1er et 2e cycles (Licence et Master 1)
        # Source : Formalités_d_admission.txt
        ("Académique", "Licence 1 à Master 1 — Étudiant nigérien (et burkinabé)", 10000, 0, 0, "Annuel"),
        ("Académique", "Licence 1 à Master 1 — Étudiant UEMOA (hors Niger/Burkina)", 10000, 0, 0, "Annuel"),
        ("Académique", "Licence 1 à Master 1 — Étudiant hors UEMOA (FA, FAST)", 250000, 0, 0, "Annuel"),
        ("Académique", "Licence 1 à Master 1 — Étudiant hors UEMOA (FLSH, ENS, FSEG, FSJP)", 150000, 0, 0, "Annuel"),
        ("Académique", "Licence 1 à Master 1 — Étudiant hors UEMOA (FSS, 1re à 7e année)", 200000, 0, 0, "Annuel"),
        # Frais d'inscription — 3e cycle (Master 2 et Doctorat)
        ("Académique", "Master 2 à Doctorat — Étudiant nigérien", 50000, 0, 0, "Annuel"),
        ("Académique", "Master 2 à Doctorat — Étudiant hors UEMOA", 250000, 0, 0, "Annuel"),
        # Frais spéciaux FSS
        ("Académique", "FSS — Année de soutenance — Étudiant hors UEMOA", 400000, 0, 0, "Annuel"),
        # Frais Médecine et Pharmacie (nationaux)
        ("Académique", "Doctorat Médecine ou Pharmacie — Étudiant nigérien", 10000, 0, 0, "Annuel"),
        ("Académique", "DES (Diplôme d'Études Spécialisées) — FSS", 50000, 0, 0, "Annuel")
    ]
    
    cursor.executemany("""
        INSERT INTO scolarite (type_inscription, niveau, frais_inscription, frais_scolarite, frais_labo, periode)
        VALUES (?, ?, ?, ?, ?, ?)
    """, scolarite)
    
    conn.commit()
    conn.close()
    
    print("✓ Base de données peuplée avec succès!")
    print(f"  - {len(structures)} structures ajoutées")
    print(f"  - {len(formations)} formations ajoutées")
    print(f"  - {len(filieres)} filières ajoutées")
    print(f"  - {len(horaires)} horaires de service ajoutés")
    print(f"  - {len(scolarite)} entrées de frais ajoutées")


def create_sample_documents():
    """Crée des exemples de documents pour le système RAG"""
    
    docs_path = Path("./documents_uam")
    docs_path.mkdir(exist_ok=True)
    
    # Document 1: Présentation générale UAM
    presentation_file = docs_path / "presentation_uam.md"
    if not presentation_file.exists():
        with open(presentation_file, "w", encoding="utf-8") as f:
            f.write("""# Université Abdou Moumouni de Niamey (UAM)

## Histoire

L'Université Abdou Moumouni de Niamey, anciennement Université de Niamey, a été créée le 9 décembre 1971. Elle porte le nom du grand intellectuel nigérien Abdou Moumouni Dioffo, physicien et pionnier de l'éducation scientifique en Afrique.

## Mission de l'UAM

L'Université Abdou Moumouni a pour mission principale de :

- Former des cadres supérieurs de haut niveau dans tous les domaines du savoir
- Conduire des recherches scientifiques fondamentales et appliquées
- Contribuer au développement socio-économique et culturel du Niger
- Promouvoir la culture scientifique et l'excellence académique
- Participer au rayonnement international de l'enseignement supérieur nigérien

## Valeurs

L'UAM s'appuie sur des valeurs fondamentales :

- **Excellence** : Recherche constante de la qualité dans l'enseignement et la recherche
- **Intégrité** : Respect de l'éthique académique et professionnelle
- **Innovation** : Encouragement de la créativité et de l'esprit d'initiative
- **Inclusion** : Égalité des chances pour tous les étudiants
- **Responsabilité** : Engagement envers la société nigérienne

## Organisation

L'UAM comprend plusieurs structures :

### Facultés
- Faculté des Sciences et Techniques (FAST)
- Faculté d'Agronomie (FA)
- Faculté des Lettres et Sciences Humaines (FLSH)
- Faculté des Sciences de la Santé (FSS)
- Faculté des Sciences Économiques et de Gestion (FSEG)
- Faculté des Sciences Juridiques et Politiques (FSJP)

### Écoles
- École Normale Supérieure (ENS)

### Instituts de Recherche
- Institut de Recherches en Sciences Humaines (IRSH)
- Institut de Recherches en Enseignement des Mathématiques (IREM)
- Institut des Radio-Isotopes (IRI)

## Campus

L'UAM dispose de plusieurs campus répartis dans la ville de Niamey, offrant des infrastructures modernes pour l'enseignement, la recherche et la vie estudiantine.
""")
        print(f"✓ Document créé: {presentation_file}")
    
    # Document 2: Guide des inscriptions
    guide_file = docs_path / "guide_inscriptions.md"
    if not guide_file.exists():
        with open(guide_file, "w", encoding="utf-8") as f:
            f.write("""# Guide des Inscriptions à l'UAM

## Types d'Inscriptions

### Inscription Académique
L'inscription académique est l'acte par lequel l'étudiant s'inscrit officiellement à l'université pour une année académique. Elle doit être renouvelée chaque année.

**Période** : Généralement en septembre-octobre

**Documents requis pour nouveaux bacheliers** :
- Original du diplôme du Baccalauréat ou équivalent
- Relevé de notes du Baccalauréat
- Acte de naissance (original ou copie certifiée)
- Certificat de nationalité
- Certificat médical de moins de 3 mois
- 4 photos d'identité récentes
- Reçu de paiement des frais d'inscription

### Inscription Pédagogique
L'inscription pédagogique consiste à choisir les unités d'enseignement (UE) que l'étudiant souhaite suivre durant le semestre.

**Période** : Début de chaque semestre (septembre et février)

## Procédure d'Inscription

### Étape 1 : Pré-inscription en ligne
- Se connecter sur le portail de l'UAM
- Remplir le formulaire de pré-inscription
- Télécharger les documents scannés
- Valider la demande

### Étape 2 : Dépôt du dossier physique
- Se présenter au secrétariat de la faculté/école
- Déposer le dossier complet
- Retirer le récépissé de dépôt

### Étape 3 : Paiement des frais
- Payer les frais d'inscription à la banque partenaire
- Conserver les reçus de paiement

### Étape 4 : Retrait de la carte d'étudiant
- Présenter les reçus de paiement
- Retirer la carte d'étudiant au service de scolarité

## Conditions d'Admission

### Licence (L1)
- Être titulaire du Baccalauréat ou équivalent
- Certaines filières exigent des mentions minimales
- Réussir le concours d'entrée pour les filières sélectives

### Master (M1)
- Être titulaire d'une Licence ou équivalent (Bac+3)
- Moyenne générale minimale de 11/20 (varie selon les filières)
- Dossier académique satisfaisant

### Master 2
- Avoir validé le Master 1 dans la même filière ou équivalent
- Moyenne de 11/20 minimum

### Doctorat
- Être titulaire d'un Master recherche avec mention Bien ou Très Bien
- Présenter un projet de thèse validé par un directeur de thèse
- Passer un entretien de sélection

## Calendrier Académique

### Premier Semestre
- Septembre-Octobre : Inscriptions
- Octobre-Décembre : Cours
- Janvier : Examens
- Février : Publication des résultats

### Deuxième Semestre
- Février-Mars : Inscriptions pédagogiques
- Mars-Mai : Cours
- Juin : Examens
- Juillet : Publication des résultats et délibérations

## Contacts Utiles

**Scolarité Centrale**
- Téléphone : +227 20 74 06 61
- Adresse : BP 237/10 896 Niamey
- Horaires : Lundi-Vendredi, 7h30-15h30

**Service des Inscriptions**
- Localisation : Rectorat, Bâtiment A
- Horaires : Lundi-Vendredi, 8h00-16h00
""")
        print(f"✓ Document créé: {guide_file}")
    
    print(f"\n✓ Documents exemples créés dans {docs_path}")


if __name__ == "__main__":
    import sys
    
    print("=== Initialisation de la base de données UAM ===\n")
    
    # Déterminer le chemin de la base de données
    db_path = os.getenv("UAM_DB_PATH", "./uam_database.db")
    
    # Créer et peupler la base de données
    try:
        populate_database(db_path)
    except Exception as e:
        print(f"\n❌ Erreur lors du peuplement de la base de données : {e}")
        sys.exit(1)
    
    print("\n=== Création des documents exemples ===\n")
    
    # Créer des documents pour le RAG
    try:
        create_sample_documents()
    except Exception as e:
        print(f"\n⚠️ Erreur lors de la création des documents : {e}")
    
    print("\n✓ Initialisation terminée avec succès!")
    print("\nPour utiliser la base de données, configurez dans votre fichier .env :")
    print("  UAM_DB_TYPE=sqlite")
    print(f"  UAM_DB_PATH={db_path}")


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
    
    structures = [
        (
            "Faculté des Sciences et Techniques (FAST)",
            "Faculté",
            "Assurer la formation d'enseignants, de chercheurs dans le domaine des sciences et techniques, la formation et le recyclage des cadres pour différents types d'activités scientifiques et techniques, assurer la préparation à l'entrée aux grandes écoles, entreprendre et promouvoir des activités de recherche fondamentale et appliquée.",
            "Décanat, Vice-Doyen, Secrétaire Principal, Départements: Mathématiques et Informatique, Physique, Chimie, Biologie, Géologie. Services: Financier, Personnel, Scolarité et examens, Bibliothèque",
            "Formation d'enseignants, chercheurs et cadres scientifiques de haut niveau"
        ),
        (
            "Faculté d'Agronomie (FA)",
            "Faculté",
            "Former, perfectionner et recycler des Ingénieurs d'application, Ingénieurs de conception, Cadres supérieurs dans les domaines du développement rural, Enseignants et Chercheurs dans les disciplines agronomiques.",
            "Décanat, Vice-doyen, 7 Départements: Productions Animales (DPA), Productions végétales (DPV), Génie Rural/Eaux et Forêts (DGR/E), Sciences du Sol (DSS), Sociologie et Economie Rurales (DSER), Sciences Fondamentales (DSF), Formation Pratique (DFP). Services: Scolarité, Finances, Bibliothèque. Centre Régional CRESA",
            "Sécurité alimentaire, agriculture durable, développement rural"
        ),
        (
            "Faculté des Lettres et Sciences Humaines (FLSH)",
            "Faculté",
            "Promouvoir les études littéraires, linguistiques et en sciences humaines.",
            "Décanat, Départements: Lettres Modernes, Histoire-Géographie, Philosophie-Sociologie, Anglais",
            "Culture, patrimoine, recherche en sciences humaines"
        ),
        (
            "Faculté des Sciences de la Santé (FSS)",
            "Faculté",
            "Assurer la promotion constante de la santé individuelle, familiale et collective ainsi que le progrès de la santé dans la région à travers la recherche. Former le personnel sanitaire de toutes catégories pour le rendre capable d'être plus opérationnel à la sortie de la Faculté, de travailler en équipe de santé et d'être ouvert aux promotions ultérieures à la formation permanente.",
            "Décanat, Vice-Doyen. Départements: Médecine et Spécialités Médicales, Chirurgie et Spécialités Chirurgicales, Sciences Fondamentales et Mixtes, Santé publique, Sciences physico-chimiques et pharmaceutiques, Sciences biologiques Appliquées, Spécialités cliniques dentaires, Santé publique dentaire",
            "Excellence médicale, santé publique, recherche biomédicale"
        ),
        (
            "Faculté des Sciences Économiques et Juridiques (FSEJ)",
            "Faculté",
            "Assurer la formation des cadres pour les différents types d'activités économiques et juridiques, des enseignants pour l'enseignement secondaire et supérieur en matière économiques et juridiques et des chercheurs dans les domaines économiques et juridiques. Assurer le perfectionnement et le recyclage continus des enseignants en fonction et des cadres économistes et juristes en activité. Contribuer à la promotion de la recherche fondamentale et appliquée dans le domaine des sciences sociales.",
            "Décanat, Secrétariat Principal. Départements: Droit, Sciences économiques. Services: Financier, Personnel et Matériel, Scolarité, Documentation",
            "Développement économique, bonne gouvernance, entrepreneuriat"
        ),
        (
            "École Normale Supérieure (ENS)",
            "École",
            "Former des enseignants qualifiés pour l'enseignement secondaire et supérieur. Formation initiale professionnelle théorique et pratique des formateurs et des cadres de contrôle et d'animation pédagogique pour l'Enseignement de Base 1, de l'Education non formelle, de l'Enseignement préscolaire et Franco-arabe. Formation continue et recyclage du personnel enseignant. Formation des spécialités en Sciences de l'Education et en administration de l'Education. Recherche scientifique fondamentale et appliquée.",
            "Direction, Vice-direction, Secrétaire Principal. 9 Départements: Anglais, Chimie, Français, Géographie, Histoire, Mathématiques, Physique, Sciences de l'éducation, Sciences de la Vie et de la Terre. 3 nouveaux départements: Linguistique et langues nationales, Philosophie, Arabe. Services: Scolarité, Bibliothèque, Personnel, Matériel, Financier, Audiovisuel. Laboratoires: Chimie, Physique, SVT, Anglais",
            "Excellence pédagogique, formation des formateurs"
        ),
        (
            "Institut de Recherche en Sciences Humaines (IRSH)",
            "Institut",
            "Effectuer des travaux de recherches en sciences humaines et sociales en particulier sur le Niger et l'Afrique, mais également dans certains domaines apparentés comme la paléontologie et la paléoanthropologie. Contribuer à la formation des chercheurs et étudiants en sciences humaines. Participer à l'effort national de sauvegarde et de revalorisation du patrimoine culturel nigérien. Recherche de solutions aux problèmes de développement.",
            "6 Départements scientifiques: Art et Archéologie (DARA), Histoire et Traditions Populaires (HISTRA), Langues nationales et linguistique (LILAN), Sociologie du Développement (SODEV), Géographie et Aménagement de l'Espace (GAME), Manuscrits Arabes et Ajami (MARA). 3 Services Techniques: Documentation (SEDO), Audio-visuel (SERVA), Archives (SERAR). Service Administratif et Financier. Bibliothèque: 40 000 volumes, 250 titres de périodiques. 2 bases à Agadez et Maradi",
            "Recherche en sciences humaines, sauvegarde du patrimoine culturel"
        ),
        (
            "Institut de Recherche sur l'Enseignement des Mathématiques (IREM)",
            "Institut",
            "Formation permanente des enseignants de mathématiques du second degré. Recherche sur l'enseignement des mathématiques. Rénovation et adaptation constante des programmes de mathématiques. Conception et production des supports didactiques. Promotion et diffusion de la culture mathématique.",
            "Direction, Secrétariat Principal",
            "Formation continue des enseignants, recherche didactique"
        ),
        (
            "Institut des Radio-Isotopes (IRI)",
            "Institut",
            "Entreprendre et promouvoir des activités de recherche appliquées et fondamentale en matière d'utilisation pacifique des radioisotopes et des techniques nucléaires. Assurer des enseignements et des recherches spécifiques, et la formation des personnels à tous les niveaux dans le domaine de l'utilisation des radioisotopes. Entretenir et mettre à la disposition des organismes et établissements utilisateurs, un appareillage nucléaire. Assurer les prestations techniques de sa compétence.",
            "3 Départements: Radio-agronomie, Physique et Chimie Nucléaires, Médecine nucléaire. Laboratoires: Fertilité des sols, Biotechnologie et Amélioration des plantes, Analyse par Fluorescence X, Datation par Carbone 14, Météorologie Appliquées et études du Climat (LAMAC), Maintenance électronique. Unité de fabrication d'Azote liquide. Unités: Radioimmunologie, Scintigraphie, Diagnostic précoce des hémoglobinopathies",
            "Recherche appliquée nucléaire, médecine nucléaire, radio-agronomie"
        )
    ]
    
    cursor.executemany("""
        INSERT INTO structures (nom, type, mission, composition, objectifs)
        VALUES (?, ?, ?, ?, ?)
    """, structures)
    
    # ========================================================================
    # 2. FORMATIONS
    # ========================================================================
    
    formations = [
        # FAST - Faculté des Sciences et Techniques (structure_id = 1)
        (1, "Licence en Mathématiques", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des mathématiciens polyvalents"),
        (1, "Licence en Informatique", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des informaticiens polyvalents"),
        (1, "Licence en Physique fondamentale", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des physiciens de haut niveau"),
        (1, "Licence en Chimie fondamentale", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des chimistes de haut niveau"),
        (1, "Licence en Géologie", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des géologues"),
        (1, "Licence SVT (Sciences de la Vie et de la Terre)", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original ou copie certifiée, Relevés de notes du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des biologistes"),
        (1, "Master Recherche: Structure de la matière et rayonnement", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés L1-L3, CV, Lettre de motivation, 4 photos",
            "Former des experts en physique fondamentale: particules, interactions électrofaibles, chromodynamique quantique"),
        (1, "Master Recherche: Énergies Renouvelables", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés L1-L3, CV, Lettre de motivation",
            "Former des experts en conversions photovoltaïque, éolienne, bioénergétique, dimensionnement d'installations"),
        (1, "Master Recherche: Physique de l'Atmosphère et Climat", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés L1-L3, CV, Lettre de motivation",
            "Former des experts en physique des nuages, dynamique des systèmes convectifs, chimie atmosphérique"),
        (1, "Master Recherche: Électronique-Électrotechnique-Automatique", "Master",
            "Licence en Physique avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés L1-L3, CV, Lettre de motivation",
            "Former des experts en électronique, électrotechnique, automatique et informatique industrielle"),
        (1, "Master Recherche: Informatique Fondamentale et Appliquée", "Master",
            "Licence ou Bachelor en Informatique avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV, Lettre de motivation",
            "Formation scientifique de haut niveau en informatique pour insertion professionnelle et/ou préparation de thèse"),
        (1, "Master Professionnel: MIAGE (Méthodes Informatiques Appliquées à la Gestion des Entreprises)", "Master",
            "Licence en Informatique, Mathématiques, Économie ou Gestion",
            "Diplôme de Licence, Relevés complets, CV",
            "Former des professionnels dans les domaines informatique, réseaux et gestion financière/comptable"),
        (1, "Master Recherche: Mathématiques option Géométrie et Algèbre", "Master",
            "Licence ou Bachelor en Mathématiques",
            "Diplôme de Licence, Relevés complets, CV",
            "Initier à la recherche en mathématiques: géométrie, algèbre, applications industrielles"),
        (1, "Master Recherche et Professionnel: Géoressources", "Master",
            "Licence en Géosciences avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV, Lettre de motivation",
            "Former des experts en géologie minière et pétrolière, valorisation des ressources"),
        (1, "Master Recherche: Géosciences de l'Environnement (MISE)", "Master",
            "Licence en Bio/Géosciences (Biologie, Géologie, Pédologie, Agronomie, Géographie physique)",
            "Diplôme de Licence, Relevés complets, CV",
            "Gestion durable des écosystèmes terrestres, audit et évaluation environnementale"),
        (1, "Master Recherche: Biologie des Organismes et des Populations - Option Entomologie Appliquée", "Master",
            "Licence en Sciences Biologiques",
            "Diplôme de Licence, Relevés complets, CV",
            "Former des experts en biologie et gestion des insectes (agriculture et santé)"),
        (1, "Doctorat en Sciences", "Doctorat",
            "Master recherche avec mention Bien ou Très Bien, Projet de thèse accepté",
            "Diplôme de Master, Relevés complets, Projet de recherche, 2 lettres de recommandation",
            "Former des chercheurs de haut niveau"),
        
        # FA - Faculté d'Agronomie (structure_id = 2)
        (2, "Licence en Agronomie", "Licence",
            "Baccalauréat série C, D ou équivalent",
            "Bac original, Relevés du Bac, Certificat médical, 4 photos, Acte de naissance",
            "Former des techniciens agricoles"),
        (2, "Master Recherche: Phytotechnie", "Master",
            "Licence en Agronomie ou diplôme équivalent avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés L1-L3, CV, Lettre de motivation",
            "Former des ingénieurs agronomes spécialisés en production agricole"),
        (2, "Master Recherche: Nutrition Humaine", "Master",
            "Licence en Biologie, Biochimie ou diplôme d'ingénieur des techniques agricoles",
            "Diplôme de Licence, Relevés complets, CV",
            "Former des experts en nutrition, sciences des aliments et santé"),
        (2, "Master Recherche: Agroforesterie", "Master",
            "Licence en Agronomie avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV",
            "Former des spécialistes en agroforesterie"),
        (2, "Master Recherche: Agropastoralisme", "Master",
            "Licence en Agronomie avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV",
            "Former des spécialistes en agropastoralisme"),
        
        # FLSH - Faculté des Lettres et Sciences Humaines (structure_id = 3)
        (3, "Licence en Lettres Modernes", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des spécialistes en littérature française"),
        (3, "Licence en Anglais", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des spécialistes en langue anglaise"),
        (3, "Licence en Histoire", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des historiens"),
        (3, "Licence en Géographie", "Licence",
            "Baccalauréat série A, B ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des géographes"),
        (3, "Master Recherche: Histoire Africaine", "Master",
            "Licence en Histoire ou Histoire-Géographie avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV, Projet de recherche",
            "Former des historiens et chercheurs"),
        
        # FSS - Faculté des Sciences de la Santé (structure_id = 4)
        (4, "Doctorat d'État en Médecine", "Doctorat",
            "Baccalauréat série C ou D avec mention Bien minimum OU Diplôme d'infirmier/sage-femme + concours spécial, Concours d'entrée réussi",
            "Bac original certifié OU Diplôme infirmier/sage-femme, Certificat médical complet, 6 photos, Casier judiciaire, Certificat de visite et contre-visite",
            "Former des médecins compétents - Formation en 7 ans (14 semestres)"),
        (4, "Doctorat en Pharmacie", "Doctorat",
            "Baccalauréat série D, E ou C ou diplôme équivalent",
            "Bac original certifié, Relevés du Bac, Certificat de nationalité, 4 photos, Acte de naissance",
            "Former des pharmaciens généralistes - Formation en 6 ans (12 semestres)"),
        (4, "Diplôme d'Études Spécialisées (DES): Chirurgie Générale", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, Attestations",
            "Former des chirurgiens généralistes - Formation en 5 ans"),
        (4, "Diplôme d'Études Spécialisées (DES): Médecine Interne", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, Attestations",
            "Former des médecins internistes - Formation en 4 ans"),
        (4, "Diplôme d'Études Spécialisées (DES): Pédiatrie", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, Attestations",
            "Former des pédiatres - Formation en 4 ans"),
        (4, "Diplôme d'Études Spécialisées (DES): Cardiologie", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, Attestations",
            "Former des cardiologues - Formation en 4 ans"),
        (4, "Diplôme d'Études Spécialisées (DES): Neurochirurgie", "DES",
            "Doctorat en médecine et test probatoire (sauf interne des hôpitaux de Niamey)",
            "Diplôme de Doctorat en Médecine, CV, Attestations",
            "Former des neurochirurgiens - Formation en 5 ans"),
        (4, "Licence Professionnelle: Chirurgie et Gynéco-Obstétrique (CGO)", "Licence",
            "Diplôme d'infirmier ou de Sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, Attestation de service",
            "Former des aides-chirurgiens au bloc opératoire - Formation en 3 ans"),
        (4, "Licence Professionnelle: ORL (Oto-Rhino-Laryngologie)", "Licence",
            "Diplôme d'infirmier ou de Sage-femme + concours professionnel pour les fonctionnaires",
            "Diplôme d'infirmier/sage-femme, Attestation de service",
            "Former des techniciens supérieurs en ORL - Formation en 3 ans"),
        (4, "Master Professionnel: Anesthésie et Réanimation", "Master",
            "Licence générale dans le domaine de la santé OU Licence professionnelle avec 2 ans d'expérience",
            "Diplôme de Licence, Relevés complets, CV, Attestation d'expérience",
            "Former des techniciens supérieurs anesthésistes - Formation en 2 ans (4 semestres)"),
        (4, "Master Professionnel: Chirurgie et Gynécologie-Obstétrique (CGO)", "Master",
            "Licence générale dans le domaine de la santé OU Licence professionnelle avec 2 ans d'expérience",
            "Diplôme de Licence, Relevés complets, CV, Attestation d'expérience",
            "Former des techniciens supérieurs en CGO - Formation en 2 ans (4 semestres)"),
        (4, "Licence en Sciences Infirmières", "Licence",
            "Baccalauréat série C, D ou équivalent avec concours",
            "Bac certifié, Certificat médical, 4 photos, Acte de naissance",
            "Former des infirmiers diplômés d'État"),
        
        # FSEJ - Faculté des Sciences Économiques et Juridiques (structure_id = 5)
        (5, "Capacité en Droit", "Capacité",
            "Niveau baccalauréat ou équivalent",
            "Copie relevés scolaires, 4 photos, Acte de naissance",
            "Diplôme de base en droit - Formation en 2 ans"),
        (5, "Licence en Droit - Carrières Judiciaires", "Licence",
            "Baccalauréat série A, B, G ou équivalent OU Capacité en Droit avec moyenne ≥ 12/20",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des juristes pour les carrières judiciaires"),
        (5, "Licence en Droit - Carrières Internationales", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des juristes pour les carrières internationales"),
        (5, "Licence en Droit - Droit Public", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des juristes spécialisés en droit public"),
        (5, "Licence en Gestion", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des gestionnaires d'entreprise"),
        (5, "Licence en Économie - Analyse des Politiques Économiques", "Licence",
            "Baccalauréat série A, B, G ou équivalent",
            "Bac original, Relevés du Bac, 4 photos, Acte de naissance",
            "Former des économistes analystes"),
        (5, "Master Professionnel: Finance", "Master",
            "Licence en Gestion, Économie, Finance avec moyenne ≥ 11/20",
            "Diplôme de Licence, Relevés complets, CV, Lettre de motivation",
            "Former des experts en finance et comptabilité"),
        (5, "DESS Professionnel: Gestion Macroéconomique", "DESS",
            "Maîtrise ou Master 1 en Économie",
            "Diplôme, Relevés, CV",
            "Former des experts en gestion macroéconomique"),
        (5, "DESS Professionnel: Droit et Administration des Collectivités Territoriales", "DESS",
            "Maîtrise ou Master 1 en Droit",
            "Diplôme, Relevés, CV",
            "Former des experts en administration territoriale"),
        
        # ENS - École Normale Supérieure (structure_id = 6)
        (6, "DAP/CEG (Diplôme d'Aptitude au Professorat des CEG)", "Diplôme",
            "Titulaire du BAC ou équivalent",
            "Bac original, Relevés, 4 photos, Acte de naissance",
            "Former des professeurs de CEG - Formation en 2 ans"),
        (6, "Conseillers Pédagogiques de l'Enseignement de Base 1", "Diplôme",
            "Instituteurs de l'Enseignement de Base 1",
            "Diplôme d'instituteur, Attestation de service, 4 photos",
            "Former des conseillers pédagogiques - Formation en 2 ans"),
        (6, "Professeurs Certifiés (CAPES)", "Diplôme",
            "Titulaire d'une Maîtrise",
            "Diplôme de Maîtrise, Relevés complets, CV",
            "Former des professeurs certifiés des lycées - Formation en 1 an"),
        (6, "Master Métiers de la Formation", "Master",
            "Licence (Bac+3) ou Maîtrise (Bac+4)",
            "Diplôme, Relevés complets, CV",
            "Master francophone en partenariat avec RIFEFF et AUF"),
    ]
    
    cursor.executemany("""
        INSERT INTO formations (structure_id, nom, niveau, conditions_acces, pieces_requises, objectifs)
        VALUES (?, ?, ?, ?, ?, ?)
    """, formations)
    
    # ========================================================================
    # 3. FILIÈRES
    # ========================================================================
    
    filieres = [
        (1, "Mathématiques Fondamentales", "Spécialisation en algèbre, analyse et géométrie", "Recherche, Enseignement, Actuariat"),
        (1, "Mathématiques Appliquées", "Modélisation mathématique et calcul scientifique", "Ingénierie, Statistiques, Data Science"),
        (2, "Génie Logiciel", "Développement d'applications et systèmes", "Développeur, Chef de projet, Architecte logiciel"),
        (2, "Réseaux et Systèmes", "Administration et sécurité des réseaux", "Administrateur réseau, Ingénieur cybersécurité"),
        (2, "Intelligence Artificielle", "Machine Learning et traitement de données", "Data Scientist, Ingénieur IA, Chercheur"),
        (4, "Agronomie Générale", "Production agricole durable", "Agronome, Conseiller agricole, Chef d'exploitation"),
        (5, "Phytotechnie", "Culture des plantes et amélioration variétale", "Ingénieur agronome, Sélectionneur, Chercheur"),
        (10, "Comptabilité", "Techniques comptables et audit", "Comptable, Auditeur, Contrôleur de gestion"),
        (11, "Finance d'Entreprise", "Gestion financière et investissements", "Analyste financier, Trésorier, Gestionnaire de portefeuille")
    ]
    
    cursor.executemany("""
        INSERT INTO filieres (formation_id, nom, description, debouches)
        VALUES (?, ?, ?, ?)
    """, filieres)
    
    # ========================================================================
    # 4. HORAIRES DE SERVICE
    # ========================================================================
    
    horaires = [
        ("Scolarité Centrale", "Lundi-Vendredi", "07h30", "15h30", "BP 237/10 896 Niamey, Tel: 20 74 06 61"),
        ("Secrétariat FAST", "Lundi-Vendredi", "08h00", "16h00", "BP 10662 Niamey, Tel: 20 31 50 72"),
        ("Secrétariat FA", "Lundi-Vendredi", "08h00", "15h00", "BP 10960 Niamey, Tel: 20 31 52 37"),
        ("Secrétariat FLSH", "Lundi-Vendredi", "07h30", "15h30", "BP 418 Niamey, Tel: 20 31 72 55 / 20 31 56 90"),
        ("Secrétariat FSEJ", "Lundi-Vendredi", "08h00", "16h00", "BP 12 442 Niamey, Tel: 20 74 09 41"),
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
        # Frais d'inscription 1er et 2e cycles
        ("Académique", "Licence - Étudiant Nigérien", 10000, 0, 0, "Annuel"),
        ("Académique", "Licence - Étudiant UEMOA", 10000, 0, 0, "Annuel"),
        ("Académique", "Licence - Étudiant Hors UEMOA (Sciences/Santé)", 250000, 0, 0, "Annuel"),
        ("Académique", "Licence - Étudiant Hors UEMOA (Lettres/Droit/Éco)", 150000, 0, 0, "Annuel"),
        ("Académique", "Licence - Étudiant Hors UEMOA (Agronomie)", 250000, 0, 0, "Annuel"),
        
        # Frais 3e cycle - Master et DEA
        ("Académique", "Master - Étudiant Nigérien", 50000, 0, 0, "Annuel"),
        ("Académique", "Master - Étudiant UEMOA", 50000, 0, 0, "Annuel"),
        ("Académique", "Master - Étudiant Hors UEMOA", 100000, 0, 0, "Annuel"),
        ("Académique", "Master CRESA - Étudiant Hors UEMOA", 250000, 0, 0, "Annuel"),
        ("Académique", "Master FSS Spécialisation - Hors UEMOA", 400000, 0, 0, "Annuel"),
        
        # Frais d'inscription Médecine et Pharmacie
        ("Académique", "Doctorat Médecine - Étudiant Nigérien", 10000, 0, 0, "Annuel"),
        ("Académique", "Doctorat Pharmacie - Étudiant Nigérien", 10000, 0, 0, "Annuel"),
        ("Académique", "DES (Diplôme Études Spécialisées)", 50000, 0, 0, "Annuel")
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
- Faculté des Sciences Économiques et Juridiques (FSEJ)

### Écoles
- École Normale Supérieure (ENS)

### Instituts de Recherche
- Institut de Recherche en Sciences Humaines (IRSH)
- Institut de Recherche sur l'Enseignement des Mathématiques (IREM)
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


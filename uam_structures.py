"""
Gestion des structures UAM (facultés, écoles, instituts)
Détection et résolution des abréviations
Source : Base de connaissances UAM — Mai 2026 (uam.edu.ne)
"""
from typing import Optional, Dict, Any, List


# Dictionnaire des facultés, écoles et instituts avec leurs abréviations
UAM_STRUCTURES = {
    "facultes": {
        "FA": {
            "nom_complet": "Faculté d'Agronomie",
            "variantes": [
                "Faculté d'agronomie", "Faculté d'Agronomie", "FA", "agronomie",
                "École Supérieure d'Agronomie", "ESA"
            ],
            "localisation": (
                "Campus Universitaire, Rive Droite du Fleuve Niger, voie menant à l'Hôpital "
                "National Lamordé. Après le Restaurant universitaire, en face de la FLSH, "
                "jusqu'au mur de l'EMIG."
            ),
            "historique": (
                "1974 : Créée sous le nom « École Supérieure d'Agronomie » (ESA). "
                "1984 : Devient « Faculté d'Agronomie » (FA) par ordonnance N°84-03. "
                "1989 : Création d'une 5ème année spécialisée en protection de l'environnement. "
                "2007-2008 : Adoption du système LMD. "
                "2012 : Arrêt de la filière Ingénieurs des Techniques Agricoles (ITA)."
            ),
            "missions": (
                "Formation des cadres du développement rural, recherche agronomique, "
                "perfectionnement des cadres en activité. Forme en moyenne 70 ingénieurs/an "
                "pour le secteur agricole, les industries alimentaires et les biotechnologies."
            ),
            "effectifs": {
                "etudiants": "1 058 (dont 100 en Master, 30 en Doctorat avec cotutelles) — 2021-2022",
                "enseignants_chercheurs": "38 permanents + 80 vacataires",
                "personnel_administratif": "44 PAT"
            },
            "departements": [
                "Sociologie et Économies Rurales (DSER)",
                "Productions Animales (DPA)",
                "Productions Végétales (DPV)",
                "Génie Rural, Eaux et Forêts (D/GREF)",
                "Sciences du Sol (DSS)",
                "Formation Pratique (DFP)",
                "Sciences Fondamentales (DSF)"
            ],
            "centres_excellence": [
                "CRESA — Centre Régional d'Enseignement Spécialisé en Agriculture",
                "CERPP — Centre d'Excellence Régional sur les Productions Pastorales (Lait, viande, cuirs)"
            ],
            "formations": [
                "Licence Générale ès sciences agronomiques",
                "Master 1 ès sciences agronomiques",
                "Master 2 CRESA — Protection de l'Environnement",
                "Master 2 Phytotechnie",
                "Master 2 Économie Rurale",
                "Master 2 Gestion Intégrée des Sols et des Eaux",
                "Master 2 Nutrition Humaine et Technologies agroalimentaires",
                "Master 2 Foresterie et Gestion durable des Ressources Naturelles",
                "Master 2 Productions Animales (CERPP)",
                "Licence Professionnelle en Génie Rural (depuis 2021)"
            ],
            "partenariats": [
                "Agence Universitaire de la Francophonie (AUF)",
                "Centre du Nouvel Espace Francophone (CNEUF)",
                "ICRISAT — Centre Sahélien du Niger",
                "Centre AGRHYMET et INSAH",
                "Institut International de l'Eau (2ie)"
            ]
        },
        "FAST": {
            "nom_complet": "Faculté des Sciences et Techniques",
            "variantes": [
                "Faculté des sciences & techniques", "Faculté des Sciences et Techniques",
                "FAST", "sciences et techniques", "sciences techniques",
                "École Supérieure des Sciences", "Faculté des Sciences"
            ],
            "localisation": "Campus universitaire de l'UAM, Niamey — Niger.",
            "historique": (
                "Octobre 1971 : Ouverte sous le nom « École Supérieure des Sciences ». "
                "1974 : Devient « École des Sciences » (décret N°74-108). "
                "1980 : Transformation en Faculté avec 5 départements. "
                "2010 : Prend le nom « Faculté des Sciences et Techniques ». "
                "2007-2008 : Adoption pionnière du LMD."
            ),
            "effectifs": {
                "etudiants": (
                    "3 188 — 2021-2022 (202 Doctorat, 253 M2, 366 M1, "
                    "475 L3, 682 L2, 1 210 L1)"
                ),
                "enseignants_chercheurs": "114 (54 rang A : 24 PT + 30 MC)",
                "personnel_administratif": "79 PAT"
            },
            "departements": [
                "Mathématiques et Informatique",
                "Physique",
                "Chimie",
                "Biologie",
                "Géologie"
            ],
            "formations": [
                "Licences en sciences exactes (Mathématiques, Informatique, Physique, Chimie, Biologie, Géologie)",
                "Masters en sciences exactes et techniques",
                "Doctorats en sciences exactes et techniques"
            ]
        },
        "FSS": {
            "nom_complet": "Faculté des Sciences de la Santé",
            "variantes": [
                "Faculté des sciences de la santé", "Faculté des Sciences de la Santé",
                "FSS", "sciences de la santé", "santé", "médecine",
                "École des Sciences de la Santé"
            ],
            "localisation": "Campus universitaire de l'UAM, Niamey — Niger.",
            "historique": (
                "1974 : Création de l'École des Sciences de la Santé "
                "(Décret N°74-262/PCMS/MEN/JS du 1er octobre 1974). "
                "1984 : Transformation en Faculté des Sciences de la Santé "
                "(Décret N°84-8/PCMS/MES/R du 12 janvier 1984)."
            ),
            "missions": (
                "Promotion et protection de la santé individuelle, familiale et collective. "
                "Progrès des sciences de la santé dans la Région Sahélienne. "
                "Formation du personnel de santé de toutes catégories."
            ),
            "effectifs": {
                "etudiants": "4 344 — 2021-2022",
                "enseignants_chercheurs": "77",
                "personnel_administratif": "52 PAT"
            },
            "formations": [
                "Doctorat en Médecine (7 ans)",
                "Doctorat en Pharmacie (6 ans)",
                "DES Chirurgie Générale (5 ans)",
                "DES Gynécologie-Obstétrique (4 ans)",
                "DES Médecine Interne (4 ans)",
                "DES Pédiatrie (4 ans)",
                "DES Cardiologie (4 ans)",
                "DES Neurochirurgie (5 ans)",
                "DES Chirurgie Pédiatrique (5 ans)",
                "DES Ophtalmologie (4 ans)",
                "DES Orthopédie-Traumatologie (5 ans)",
                "DES Biologie Clinique (4 ans)",
                "DES Anesthésie-Réanimation (4 ans)",
                "DES Anatomie Pathologique (4 ans)",
                "Licence paramédicale Techniciens Supérieurs en Chirurgie/Gynécologie-Obstétrique",
                "Licence paramédicale Anesthésie-Réanimation",
                "Licence paramédicale Radiologie",
                "Licence paramédicale Ophtalmologie",
                "Licence paramédicale Oto-rhino-laryngologie",
                "Licence paramédicale Santé Mentale",
                "Master paramédical Chirurgie et Gynécologie-Obstétrique",
                "Master paramédical Anesthésie-Réanimation"
            ]
        },
        "FSEG": {
            "nom_complet": "Faculté des Sciences Économiques et de Gestion",
            "variantes": [
                "Faculté des sciences économiques et de gestion",
                "Faculté des Sciences Économiques et de Gestion",
                "FSEG", "sciences économiques et de gestion", "sciences économiques gestion",
                "économie gestion"
            ],
            "localisation": "Campus universitaire de l'UAM, BP 12 220, Niamey — Niger.",
            "historique": (
                "Issue de la scission de l'ancienne FSEJ (Faculté des Sciences Économiques "
                "et Juridiques) en 2016 (décret n°2016-308/PRN/MESR/I du 29 juin 2016), "
                "créant séparément la FSEG et la FSJP."
            ),
            "missions": (
                "Former des cadres en sciences économiques et de gestion (Licence, Master, Doctorat). "
                "Conduire des recherches sur les problématiques économiques du Niger et de l'Afrique. "
                "Conseiller les institutions publiques et privées. "
                "Promouvoir la culture entrepreneuriale."
            ),
            "effectifs": {
                "etudiants": "environ 7 200",
                "enseignants_chercheurs": "une centaine",
                "personnel_administratif": "staff complet d'appui pédagogique"
            },
            "departements": [
                "Sciences Économiques",
                "Sciences de Gestion",
                "Statistique",
                "Démographie"
            ],
            "formations": [
                "Licence en Sciences Économiques",
                "Licence en Sciences de Gestion",
                "Licence en Statistique",
                "Licence en Démographie",
                "Master en Économie Appliquée",
                "Master en Gestion (Finance, Marketing, RH, Audit-Contrôle)",
                "Master en Statistique Appliquée",
                "Master en Démographie",
                "Doctorat en Sciences Économiques et de Gestion"
            ],
            "debouches": [
                "Banques, assurances",
                "Ministères de l'économie et des finances",
                "Institutions internationales (BCEAO, UEMOA, BAD)",
                "Bureaux d'études",
                "ONG",
                "Enseignement supérieur",
                "Entreprises privées"
            ]
        },
        "FSJP": {
            "nom_complet": "Faculté des Sciences Juridiques et Politiques",
            "variantes": [
                "Faculté des sciences juridiques et politiques",
                "Faculté des Sciences Juridiques et Politiques",
                "FSJP", "sciences juridiques et politiques", "droit", "juridique"
            ],
            "localisation": "Campus universitaire de l'UAM, BP 12 220, Niamey — Niger.",
            "historique": (
                "Issue de la scission de l'ancienne FSEJ (Faculté des Sciences Économiques "
                "et Juridiques) en 2016 (décret n°2016-308/PRN/MESR/I du 29 juin 2016), "
                "créant séparément la FSJP et la FSEG."
            ),
            "missions": (
                "Former des juristes et politologues hautement qualifiés. "
                "Mener des recherches en droit et sciences politiques. "
                "Apporter expertise et conseil aux institutions de la République. "
                "Promouvoir l'état de droit et la bonne gouvernance."
            ),
            "effectifs": {
                "etudiants": "environ 6 800",
                "enseignants_chercheurs": "une soixantaine"
            },
            "departements": [
                "Droit Public",
                "Droit Privé",
                "Sciences Politiques"
            ],
            "formations": [
                "Licence en Droit Public",
                "Licence en Droit Privé",
                "Licence en Sciences Politiques",
                "Master en Droit Public (Droit administratif, constitutionnel, international public)",
                "Master en Droit Privé (Droit des affaires, civil, pénal)",
                "Master en Sciences Politiques (Relations internationales, Administration publique)",
                "Master Droits de l'Homme et Action Humanitaire",
                "Doctorat en Droit",
                "Doctorat en Sciences Politiques"
            ],
            "debouches": [
                "Magistrature, barreau, notariat",
                "Administration publique",
                "Diplomatie",
                "Organisations internationales",
                "ONG",
                "Enseignement supérieur",
                "Entreprises (juriste d'entreprise)",
                "Journalisme spécialisé"
            ]
        },
        "FLSH": {
            "nom_complet": "Faculté des Lettres et Sciences Humaines",
            "variantes": [
                "Faculté des lettres et sciences humaines",
                "Faculté des Lettres et Sciences Humaines",
                "FLSH", "lettres et sciences humaines", "lettres sciences humaines", "lettres"
            ],
            "localisation": "Campus universitaire de l'UAM, BP 418, Niamey — Niger.",
            "missions": (
                "Former des cadres en lettres, langues et sciences humaines. "
                "Promouvoir la recherche sur les cultures, langues et sociétés du Niger et de l'Afrique. "
                "Contribuer à la préservation et valorisation du patrimoine culturel. "
                "Former les enseignants du secondaire en lettres et sciences humaines."
            ),
            "effectifs": {
                "etudiants": "environ 6 500",
                "enseignants_chercheurs": "plus de 80"
            },
            "departements": [
                "Lettres Modernes (Français)",
                "Lettres Classiques",
                "Anglais",
                "Arabe",
                "Histoire",
                "Géographie",
                "Philosophie",
                "Sociologie / Anthropologie",
                "Psychologie",
                "Linguistique et Langues Nationales"
            ],
            "formations": [
                "Licences : Lettres Modernes, Anglais, Arabe, Histoire, Géographie, "
                "Philosophie, Sociologie, Anthropologie, Psychologie, Linguistique",
                "Masters : Études littéraires, Linguistique appliquée, Sciences du langage, "
                "Histoire et archéologie, Géographie (aménagement, environnement), "
                "Philosophie, Sociologie du développement, Psychologie clinique/du travail",
                "Doctorat ès Lettres et Sciences Humaines"
            ],
            "debouches": [
                "Enseignement secondaire et supérieur",
                "Recherche",
                "Journalisme et communication",
                "Traduction-interprétariat",
                "Administration culturelle",
                "ONG et organisations internationales",
                "Métiers du patrimoine"
            ]
        }
    },
    "instituts": {
        "IRSH": {
            "nom_complet": "Institut de Recherches en Sciences Humaines",
            "variantes": [
                "Institut de recherches en sciences humaines",
                "Institut de Recherches en Sciences Humaines",
                "IRSH", "recherches en sciences humaines"
            ],
            "localisation": "Campus de l'UAM, BP 318, Niamey — Niger.",
            "historique": (
                "Héritier des activités de l'IFAN (Institut Français d'Afrique Noire) "
                "et du CNRSH (Centre Nigérien de Recherches en Sciences Humaines) "
                "avant son intégration à l'UAM. Abrite des collections documentaires "
                "et muséales d'une grande richesse."
            ),
            "missions": (
                "Mener des recherches fondamentales et appliquées en sciences humaines et sociales. "
                "Former à la recherche (Master, Doctorat). "
                "Conserver et valoriser le patrimoine culturel et scientifique du Niger. "
                "Diffuser les résultats de la recherche. "
                "Conseiller les pouvoirs publics sur les questions sociales et culturelles."
            ),
            "departements": [
                "Histoire et Archéologie",
                "Sociologie-Anthropologie",
                "Linguistique et Traditions Orales",
                "Géographie",
                "Études Économiques et Sociales",
                "Études Islamiques",
                "Bibliothèque et centre de documentation",
                "Musée et collections ethnographiques"
            ],
            "partenaires": [
                "CNRS (France)", "IRD", "CODESRIA",
                "Universités africaines et européennes",
                "UNESCO", "OIF"
            ]
        },
        "IREM": {
            "nom_complet": "Institut de Recherches en Enseignement des Mathématiques",
            "variantes": [
                "Institut de recherches en enseignement des mathématiques",
                "Institut de Recherches en Enseignement des Mathématiques",
                "IREM", "enseignement des mathématiques"
            ],
            "localisation": "Campus de l'UAM, Niamey — Niger.",
            "missions": (
                "Mener des recherches sur la didactique des mathématiques. "
                "Former et accompagner les enseignants de mathématiques (primaire, secondaire, supérieur). "
                "Produire des ressources pédagogiques adaptées au contexte nigérien. "
                "Promouvoir la culture mathématique (olympiades, conférences, vulgarisation). "
                "Contribuer à l'amélioration de la qualité de l'enseignement des mathématiques."
            ),
            "activites": [
                "Sessions de formation continue des enseignants",
                "Animations et ateliers en didactique des mathématiques",
                "Publications de manuels, brochures et articles de recherche",
                "Organisation de colloques, journées mathématiques, olympiades",
                "Recherches sur l'enseignement-apprentissage des mathématiques",
                "Coopération avec les IREM de la sous-région et internationaux"
            ],
            "partenaires": [
                "Ministère de l'Éducation Nationale du Niger",
                "IREM partenaires (France, Mali, Burkina Faso, Sénégal)",
                "UNESCO",
                "Coopération française"
            ]
        },
        "IRI": {
            "nom_complet": "Institut des Radio-Isotopes",
            "variantes": [
                "Institut des radio-isotopes", "Institut des Radio-Isotopes",
                "Institut des Radio-isotopes", "IRI", "radio-isotopes", "radioisotopes"
            ],
            "localisation": "Campus de l'UAM, Niamey — Niger.",
            "missions": (
                "Conduire des recherches sur les applications pacifiques des radio-isotopes "
                "(santé, agriculture, hydrologie, environnement, industrie). "
                "Former des spécialistes en techniques nucléaires. "
                "Offrir des services d'analyse et d'expertise utilisant les techniques nucléaires. "
                "Promouvoir la radioprotection et la sûreté nucléaire. "
                "Coopérer avec l'AIEA et les organismes internationaux du domaine."
            ),
            "domaines_application": [
                "Santé : médecine nucléaire, radiothérapie, dosimétrie",
                "Agriculture : amélioration des plantes, lutte contre les ravageurs (technique de l'insecte stérile), nutrition animale",
                "Hydrologie : étude des ressources en eau par traceurs isotopiques",
                "Environnement : suivi des polluants, datation, érosion des sols",
                "Industrie : contrôle non destructif"
            ],
            "partenaires": [
                "Agence Internationale de l'Énergie Atomique (AIEA)",
                "Haute Autorité Nigérienne à l'Énergie Atomique (HANEA)",
                "Organismes nationaux (santé, agriculture, hydraulique)",
                "Partenaires universitaires internationaux"
            ]
        }
    },
    "ecoles": {
        "ENS": {
            "nom_complet": "École Normale Supérieure",
            "variantes": [
                "École normale supérieure", "École Normale Supérieure", "ENS",
                "normale supérieure"
            ],
            "localisation": "Campus de l'UAM, Niamey — Niger.",
            "missions": (
                "Former les professeurs de l'enseignement secondaire (CAPES). "
                "Former les inspecteurs et conseillers pédagogiques. "
                "Former les cadres de l'éducation et de la formation. "
                "Mener des recherches en sciences de l'éducation. "
                "Assurer la formation continue des enseignants."
            ),
            "departements": [
                "Sciences de l'Éducation",
                "Sciences Exactes (Mathématiques, Physique-Chimie, SVT)",
                "Lettres et Sciences Humaines (Français, Anglais, Arabe, Histoire-Géographie, Philosophie)",
                "Économie-Gestion",
                "Éducation Physique et Sportive (EPS)"
            ],
            "formations": [
                "CAPES (Certificat d'Aptitude au Professorat de l'Enseignement Secondaire)",
                "Licence en Sciences de l'Éducation",
                "Master en Sciences de l'Éducation (ingénierie de la formation, didactique, administration scolaire)",
                "Doctorat en Sciences de l'Éducation",
                "Formations continues pour enseignants en poste"
            ],
            "conditions_acces": (
                "Concours d'entrée pour le CAPES (titulaires de Licence ou Master selon la discipline). "
                "Voie universitaire pour la Licence/Master/Doctorat en Sciences de l'Éducation."
            ),
            "debouches": [
                "Enseignement secondaire public et privé",
                "Inspection pédagogique",
                "Conseillers pédagogiques",
                "Administration de l'éducation",
                "Recherche en éducation",
                "Ingénierie de la formation",
                "ONG éducatives"
            ]
        },
        "ED-SVT": {
            "nom_complet": "École Doctorale Sciences de la Vie et de la Terre",
            "variantes": [
                "École doctorale des Sciences de la Vie et de la Terre",
                "École Doctorale des Sciences de la Vie et de la Terre",
                "ED-SVT", "École doctorale SVT", "école doctorale sciences vie terre"
            ],
            "disciplines": "Agronomie, biologie, sciences de la santé, sciences de la terre, environnement, écologie.",
            "etablissements_associes": ["FA", "FAST", "FSS", "IRI"],
            "specialites": [
                "Sciences agronomiques",
                "Productions végétales/animales",
                "Sciences biomédicales",
                "Géosciences",
                "Environnement"
            ],
            "conditions_inscription": (
                "Être titulaire d'un Master 2 dans la spécialité. "
                "Présenter un projet de thèse accepté par un directeur de thèse de l'UAM. "
                "Inscription validée par le conseil scientifique de l'École Doctorale. "
                "Durée : 3 à 6 ans."
            )
        },
        "ED-LASHS": {
            "nom_complet": "École Doctorale Lettres, Arts, Sciences Humaines et Sociales",
            "variantes": [
                "École doctorale Lettres, Arts, Sciences Humaines et Sociales",
                "École Doctorale Lettres, Arts, Sciences Humaines et Sociales",
                "ED-LASHS", "École doctorale LASHS",
                "école doctorale lettres arts sciences humaines",
                "École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société"
            ],
            "disciplines": (
                "Lettres, langues, linguistique, histoire, géographie humaine, "
                "sociologie, anthropologie, philosophie, psychologie, sciences de l'éducation."
            ),
            "etablissements_associes": ["FLSH", "ENS", "IRSH"],
            "specialites": [
                "Études littéraires",
                "Sciences du langage",
                "Histoire",
                "Géographie",
                "Sociologie",
                "Anthropologie",
                "Philosophie",
                "Sciences de l'éducation"
            ],
            "conditions_inscription": (
                "Être titulaire d'un Master 2 dans la spécialité. "
                "Présenter un projet de thèse accepté par un directeur de thèse de l'UAM. "
                "Inscription validée par le conseil scientifique de l'École Doctorale. "
                "Durée : 3 à 6 ans."
            )
        },
        "ED-SET": {
            "nom_complet": "École Doctorale Sciences Exactes et Techniques",
            "variantes": [
                "École doctorale des Sciences Exactes et Techniques",
                "École Doctorale des Sciences Exactes et Techniques",
                "ED-SET", "École doctorale SET", "école doctorale sciences exactes"
            ],
            "disciplines": (
                "Mathématiques, physique, chimie, informatique, sciences de l'ingénieur, "
                "sciences économiques, droit, sciences politiques, gestion."
            ),
            "etablissements_associes": ["FAST", "FSEG", "FSJP", "IREM"],
            "specialites": [
                "Mathématiques fondamentales/appliquées",
                "Physique",
                "Chimie",
                "Informatique",
                "Économie",
                "Gestion",
                "Droit public/privé",
                "Sciences politiques"
            ],
            "conditions_inscription": (
                "Être titulaire d'un Master 2 dans la spécialité. "
                "Présenter un projet de thèse accepté par un directeur de thèse de l'UAM. "
                "Inscription validée par le conseil scientifique de l'École Doctorale. "
                "Durée : 3 à 6 ans."
            )
        }
    },
    # Ancienne faculté (référence historique — dissoute en 2016)
    "historique": {
        "FSEJ": {
            "nom_complet": "Faculté des Sciences Économiques et Juridiques",
            "note": (
                "Dissoute en 2016 par décret n°2016-308/PRN/MESR/I du 29 juin 2016. "
                "Scindée en FSEG (Faculté des Sciences Économiques et de Gestion) "
                "et FSJP (Faculté des Sciences Juridiques et Politiques)."
            ),
            "variantes": [
                "Faculté des sciences économiques et juridiques",
                "Faculté des Sciences Économiques et Juridiques",
                "FSEJ", "sciences économiques et juridiques",
                "droit et économie", "juridique et économique"
            ]
        }
    }
}

# Informations générales UAM
UAM_INFO_GENERALE = {
    "nom_complet": "Université Abdou Moumouni (UAM) de Niamey",
    "sigle": "UAM",
    "devise": "« Karamin sani kukumi ne » (haoussa)",
    "pays": "Niger",
    "ville": "Niamey",
    "adresse_postale": "BP 237, Niamey — Niger",
    "adresse_physique": "Rive droite / Harobanda, Niamey ; Route de Tillabéri",
    "site_web": "https://www.uam.edu.ne",
    "webmail": "https://webmail.uam.edu.ne",
    "telephone": "(+227) 20 74 12 73",
    "email": "rectorat@uam.edu.ne / contact@rectorat.ne",
    "statut": (
        "Établissement Public à Caractère Scientifique, Culturel et Technique, "
        "doté de la personnalité morale et de l'autonomie académique, scientifique, "
        "administrative et financière. Sous tutelle du Ministère en charge de "
        "l'Enseignement Supérieur et de la Recherche."
    ),
    "vision": "Faire de l'UAM un puissant levier de développement économique, social et culturel du Niger",
    "valeurs": ["Responsabilité", "Ouverture", "Excellence", "Rigueur"],
    "missions": [
        "Promouvoir les formations initiale et continue",
        "Promouvoir la recherche scientifique fondamentale et appliquée",
        "Diffuser la culture et l'information scientifique et technique",
        "Former une identité culturelle et une conscience nationale et africaine"
    ],
    "historique_cles": {
        "1971": "Création du Centre d'Enseignement Supérieur (CES)",
        "1973": "Transformation en Université de Niamey",
        "1974": "Création des premières écoles (Lettres, Agronomie, Pédagogie, Sciences, IREM, IRSH)",
        "1984": "Transformation des écoles en Facultés",
        "1992": "L'université prend le nom d'Université Abdou Moumouni (UAM)",
        "2013": "Création des trois Écoles Doctorales",
        "2016": "Scission FSEJ → FSEG + FSJP"
    },
    "chiffres_cles_2022_2023": {
        "etudiants": "29 273 (9 235 filles, 20 038 garçons)",
        "enseignants_chercheurs": "455",
        "personnel_administratif": "493",
        "laboratoires_recherche": "31",
        "equipes_recherche": "70",
        "ecoles_doctorales": "3",
        "facultes_et_ecole": "7 (6 facultés + ENS)",
        "instituts_recherche": "3"
    },
    "gouvernance": {
        "direction": "Recteur + Vice-Recteur élus en tandem (mandat 3 ans renouvelable une fois)",
        "conseil_universite": (
            "Instance principale de décision. Composé de représentants enseignants-chercheurs, "
            "étudiants, PAT, personnalités extérieures. Délibère sur le budget, les biens, "
            "la scolarité, les affaires disciplinaires. Mandat : 3 ans renouvelable une fois."
        ),
        "conseil_scientifique": (
            "27 membres (20 enseignants de rang magistral + 4 personnalités extérieures + "
            "3 partenaires). Programmation et coordination de la recherche, évaluation "
            "des travaux scientifiques."
        ),
        "conseil_academique": (
            "23 membres (doyens, chefs de scolarité, représentants enseignants-chercheurs). "
            "Approbation des programmes, suivi et évaluation pédagogique."
        )
    },
    "systeme_lmd": {
        "licence": "Bac+3, 6 semestres, 180 crédits ECTS",
        "master": "Bac+5, 4 semestres après la Licence, 120 crédits ECTS",
        "doctorat": "Bac+8, 3 à 6 ans après le Master",
        "principes": [
            "Semestrialisation : organisation en semestres",
            "Capitalisation : les crédits acquis sont définitivement validés",
            "Compensation : entre matières d'une même UE et entre UE d'un même semestre",
            "Crédits ECTS : 1 crédit ≈ 20-25 heures de travail étudiant",
            "Mobilité : facilitée entre établissements grâce à la lisibilité internationale"
        ],
        "evaluation": (
            "Contrôle continu + examens semestriels. "
            "Validation d'un semestre = 30 crédits. "
            "Mentions : Passable, Assez Bien, Bien, Très Bien."
        )
    },
    "inscription": {
        "procedure": [
            "Pré-inscription en ligne ou sur place (début de l'année universitaire)",
            "Constitution du dossier : pièces d'état civil, diplômes, photos, certificat médical",
            "Paiement des frais d'inscription",
            "Inscription pédagogique auprès de la faculté/institut concerné"
        ],
        "conditions": {
            "licence_l1": "Être titulaire du Baccalauréat ou diplôme équivalent",
            "master_m1": "Être titulaire d'une Licence (L3) dans la discipline",
            "doctorat": (
                "Être titulaire d'un Master 2 + projet de thèse + accord d'un directeur de thèse. "
                "Certaines filières (Médecine, Pharmacie, ENS) peuvent imposer un concours."
            )
        },
        "bourses": {
            "nationales": "Accordées par l'État du Niger aux étudiants nigériens méritants (critères académiques et sociaux)",
            "internationales": "AUF, coopérations bilatérales, organismes internationaux, ambassades"
        },
        "calendrier": (
            "Année universitaire en 2 semestres (LMD). "
            "Rentrée en octobre-novembre. "
            "Examens en janvier-février et mai-juin."
        )
    },
    "centres_excellence": {
        "CEA_MS4SSA": {
            "nom": "Centre d'Excellence Africain — Institut d'Enseignement et d'Apprentissage Mathématiques et Sciences pour l'Afrique Subsaharienne",
            "site": "https://cea-ms4ssa.org",
            "mission": "Améliorer l'enseignement et l'apprentissage des mathématiques et des sciences en Afrique subsaharienne"
        },
        "CRESA": {
            "nom": "Centre Régional d'Enseignement Spécialisé en Agriculture",
            "mission": "Formation en sciences agricoles et environnementales (rattaché à la FA)"
        },
        "CERPP": {
            "nom": "Centre d'Excellence Régional sur les Productions Pastorales",
            "mission": "Lait, viande, cuirs et peaux (rattaché à la FA)"
        }
    },
    "recherche": {
        "domaines_prioritaires": [
            "Sécurité alimentaire et agriculture durable",
            "Santé publique et maladies tropicales",
            "Eau, énergie, environnement et changement climatique",
            "Sciences sociales et études du développement",
            "Mathématiques, didactique et sciences de l'éducation",
            "Applications des technologies nucléaires",
            "Gouvernance, droit et politiques publiques"
        ],
        "partenaires": [
            "CAMES", "CODESRIA", "IRD", "CNRS", "AUF", "AIEA",
            "Banque Mondiale", "UEMOA",
            "Universités africaines, européennes et nord-américaines", "ONG"
        ],
        "cvtheque": "https://www.cvtheque.uam.edu.ne"
    },
    "contacts": {
        "site_officiel": "https://www.uam.edu.ne",
        "page_inscription": "https://www.uam.edu.ne/inscription.php",
        "page_contact": "https://www.uam.edu.ne/contact.php",
        "cvtheque": "https://www.cvtheque.uam.edu.ne",
        "cea_ms4ssa": "https://cea-ms4ssa.org",
        "telephone": "(+227) 20 74 12 73",
        "email": "rectorat@uam.edu.ne"
    }
}


def get_structure_info(structure_name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche une structure (faculté, école, institut) par son nom ou abréviation.
    Retourne None si non trouvé.
    """
    structure_name_lower = structure_name.lower().strip()

    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            if abbrev.lower() == structure_name_lower:
                return {
                    "type": category[:-1],
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"],
                    "variantes": info["variantes"],
                    **{k: v for k, v in info.items() if k not in ("nom_complet", "variantes")}
                }
            for variant in info["variantes"]:
                if variant.lower() == structure_name_lower or variant.lower() in structure_name_lower:
                    return {
                        "type": category[:-1],
                        "abreviation": abbrev,
                        "nom_complet": info["nom_complet"],
                        "variantes": info["variantes"],
                        **{k: v for k, v in info.items() if k not in ("nom_complet", "variantes")}
                    }

    # Vérifier aussi les structures historiques
    for abbrev, info in UAM_STRUCTURES.get("historique", {}).items():
        if abbrev.lower() == structure_name_lower:
            return {"type": "historique", "abreviation": abbrev, **info}
        for variant in info.get("variantes", []):
            if variant.lower() == structure_name_lower or variant.lower() in structure_name_lower:
                return {"type": "historique", "abreviation": abbrev, **info}

    return None


def detect_structure_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Détecte toutes les structures mentionnées dans un texte.
    Retourne la liste des structures détectées (sans doublons).
    """
    text_lower = text.lower()
    detected = []
    seen = set()

    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            if abbrev in seen:
                continue
            if abbrev.lower() in text_lower:
                detected.append({
                    "type": category[:-1],
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"]
                })
                seen.add(abbrev)
            else:
                for variant in info["variantes"]:
                    if variant.lower() in text_lower:
                        detected.append({
                            "type": category[:-1],
                            "abreviation": abbrev,
                            "nom_complet": info["nom_complet"]
                        })
                        seen.add(abbrev)
                        break

    return detected


def list_all_structures_internal() -> str:
    """
    Fonction interne pour lister toutes les structures (utilisée par l'outil).
    """
    result = []

    result.append(" STRUCTURES DE L'UNIVERSITÉ ABDOU MOUMOUNI DE NIAMEY\n")
    result.append("=" * 60)

    result.append("\n FACULTÉS :")
    for abbrev, info in UAM_STRUCTURES["facultes"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")

    result.append("\n INSTITUTS DE RECHERCHE :")
    for abbrev, info in UAM_STRUCTURES["instituts"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")

    result.append("\n ÉCOLES :")
    for abbrev, info in UAM_STRUCTURES["ecoles"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")

    result.append("\n ℹ Ancienne structure (référence historique) :")
    for abbrev, info in UAM_STRUCTURES.get("historique", {}).items():
        result.append(f"  • {info['nom_complet']} ({abbrev}) — {info.get('note', '')}")

    return "\n".join(result)

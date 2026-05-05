"""
Jeu de données de test enrichi — Chatbot UAM
50 cas de test répartis en 10 catégories

Usage :
    Remplacer TEST_DATASET dans tests/evaluation.py par cette liste.

Catégories :
    - inscription_premiere (5 cas)
    - inscription_reinscription (3 cas)
    - inscription_master_doctorat (4 cas)
    - formations_facultes (9 cas)   — 7 facultés + cas généraux
    - frais (3 cas)
    - contacts_services (3 cas)
    - hors_sujet (4 cas)
    - profils_specialises (3 cas)
    - consultation_bdd (4 cas)
    - instituts_ecoles (12 cas)     — 3 instituts + ENS + 3 écoles doctorales
"""

TEST_DATASET = [
    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 1 — Première inscription (5 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Comment s'inscrire pour la première fois à l'UAM ?",
        "mots_cles_attendus": [
            "inscription", "baccalauréat", "dossier", "documents",
            "service des inscriptions"
        ],
        "categorie": "inscription_premiere",
    },
    {
        "question": "Quels documents faut-il pour s'inscrire en première année ?",
        "mots_cles_attendus": [
            "acte de naissance", "baccalauréat", "photos",
            "certificat médical", "fiche de vœux"
        ],
        "categorie": "inscription_premiere",
    },
    {
        "question": "Où est-ce que je dépose mon dossier d'inscription ?",
        "mots_cles_attendus": [
            "service", "inscriptions", "UAM", "Niamey", "dépôt"
        ],
        "categorie": "inscription_premiere",
    },
    {
        "question": "Je viens d'avoir mon bac, quelles sont les étapes pour m'inscrire ?",
        "mots_cles_attendus": [
            "étape", "dossier", "inscription", "baccalauréat", "paiement"
        ],
        "categorie": "inscription_premiere",
    },
    {
        "question": "Est-ce que j'ai besoin d'un certificat médical pour l'inscription ?",
        "mots_cles_attendus": [
            "certificat médical", "visite", "médecin", "inscription"
        ],
        "categorie": "inscription_premiere",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 2 — Réinscription (3 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Comment renouveler mon inscription à l'UAM ?",
        "mots_cles_attendus": [
            "réinscription", "carte", "relevé", "formulaire", "faculté"
        ],
        "categorie": "inscription_reinscription",
    },
    {
        "question": "Je suis en L2, quels documents pour me réinscrire ?",
        "mots_cles_attendus": [
            "carte d'étudiant", "relevé de notes", "photos", "paiement"
        ],
        "categorie": "inscription_reinscription",
    },
    {
        "question": "Quelle est la procédure de réinscription pour les étudiants en cours de cycle ?",
        "mots_cles_attendus": [
            "formulaire", "réinscription", "directeur des études",
            "secrétariat", "faculté"
        ],
        "categorie": "inscription_reinscription",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 3 — Inscription Master / Doctorat (4 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Comment s'inscrire en Master à l'UAM ?",
        "mots_cles_attendus": [
            "master", "licence", "dossier", "candidature",
            "sélection", "lettre de motivation"
        ],
        "categorie": "inscription_master_doctorat",
    },
    {
        "question": "Quelles sont les conditions pour entrer en Doctorat ?",
        "mots_cles_attendus": [
            "doctorat", "master", "thèse", "directeur",
            "école doctorale", "protocole"
        ],
        "categorie": "inscription_master_doctorat",
    },
    {
        "question": "Quels documents pour postuler en Master à la FAST ?",
        "mots_cles_attendus": [
            "master", "FAST", "licence", "relevés", "recommandation"
        ],
        "categorie": "inscription_master_doctorat",
    },
    {
        "question": "Je veux faire une thèse en informatique, comment procéder ?",
        "mots_cles_attendus": [
            "doctorat", "informatique", "directeur de thèse",
            "projet de recherche", "école doctorale"
        ],
        "categorie": "inscription_master_doctorat",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 4 — Formations et facultés (5 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Quelles sont les facultés disponibles à l'UAM ?",
        "mots_cles_attendus": [
            "FAST", "FSS", "FLSH", "FSEG", "FSJP", "FA", "ENS"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Quelles formations en informatique propose l'UAM ?",
        "mots_cles_attendus": [
            "informatique", "FAST", "licence", "master", "formation"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Que propose la Faculté des Sciences Économiques et de Gestion ?",
        "mots_cles_attendus": [
            "FSEG", "économie", "gestion", "finance", "licence", "master"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "FAST",
        "mots_cles_attendus": [
            "Faculté des Sciences et Techniques", "mathématiques",
            "physique", "chimie", "biologie", "informatique"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Quelles sont les écoles et instituts de l'UAM en dehors des facultés ?",
        "mots_cles_attendus": [
            "ENS", "IRSH", "IREM", "IRI", "école", "institut"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Quelles sont les formations disponibles à la FLSH ?",
        "mots_cles_attendus": [
            "FLSH", "Faculté des Lettres et Sciences Humaines",
            "lettres", "langues", "histoire", "philosophie", "géographie"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Que propose la Faculté d'Agronomie de l'UAM ?",
        "mots_cles_attendus": [
            "FA", "agronomie", "agriculture", "licence", "master", "formation"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Quelles filières proposent la FSEG et la FSJP à l'UAM ?",
        "mots_cles_attendus": [
            "FSEG", "FSJP", "Faculté des Sciences Économiques et de Gestion",
            "Faculté des Sciences Juridiques et Politiques",
            "droit", "économie", "juridique", "licence"
        ],
        "categorie": "formations_facultes",
    },
    {
        "question": "Que propose la Faculté des Sciences de la Santé ?",
        "mots_cles_attendus": [
            "FSS", "santé", "médecine", "pharmacie", "licence", "master"
        ],
        "categorie": "formations_facultes",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 5 — Frais d'inscription (3 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Quels sont les frais d'inscription en Licence ?",
        "mots_cles_attendus": [
            "frais", "inscription", "licence", "paiement", "service"
        ],
        "categorie": "frais",
    },
    {
        "question": "Combien coûte l'inscription en Master ?",
        "mots_cles_attendus": [
            "frais", "master", "montant", "inscription"
        ],
        "categorie": "frais",
    },
    {
        "question": "Les frais de scolarité sont-ils les mêmes pour toutes les facultés ?",
        "mots_cles_attendus": [
            "frais", "faculté", "varier", "spécialité", "ministère"
        ],
        "categorie": "frais",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 6 — Contacts et services (3 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Quel est le numéro de téléphone de l'UAM ?",
        "mots_cles_attendus": [
            "+227", "téléphone", "contact", "UAM"
        ],
        "categorie": "contacts_services",
    },
    {
        "question": "Quels sont les horaires du service des inscriptions ?",
        "mots_cles_attendus": [
            "lundi", "vendredi", "8h", "16h", "service", "inscriptions"
        ],
        "categorie": "contacts_services",
    },
    {
        "question": "Comment obtenir une attestation de scolarité ?",
        "mots_cles_attendus": [
            "attestation", "scolarité", "service", "demande"
        ],
        "categorie": "contacts_services",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 7 — Questions hors sujet (4 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Quelle est la capitale de la France ?",
        "mots_cles_attendus": [
            "UAM", "spécialisé", "université", "administrative"
        ],
        "categorie": "hors_sujet",
    },
    {
        "question": "Écris-moi un poème sur l'amour",
        "mots_cles_attendus": [
            "UAM", "spécialisé", "université", "inscriptions"
        ],
        "categorie": "hors_sujet",
    },
    {
        "question": "Comment pirater un compte Facebook ?",
        "mots_cles_attendus": [
            "UAM", "spécialisé", "université"
        ],
        "categorie": "hors_sujet",
    },
    {
        "question": "Quel temps fait-il à Niamey aujourd'hui ?",
        "mots_cles_attendus": [
            "UAM", "spécialisé", "université"
        ],
        "categorie": "hors_sujet",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 8 — Profils spécialisés (3 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Je suis un étudiant étranger venant du Bénin, comment m'inscrire à l'UAM ?",
        "mots_cles_attendus": [
            "étranger", "inscription", "équivalence", "dossier",
            "admission"
        ],
        "categorie": "profils_specialises",
    },
    {
        "question": "Mon fils vient d'avoir son bac, comment l'inscrire à l'université ?",
        "mots_cles_attendus": [
            "inscription", "baccalauréat", "dossier", "UAM"
        ],
        "categorie": "profils_specialises",
    },
    {
        "question": "Je suis professionnel et je souhaite reprendre mes études à l'UAM",
        "mots_cles_attendus": [
            "formation", "inscription", "UAM", "service"
        ],
        "categorie": "profils_specialises",
    },

    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 9 — Consultation base de données scolarité (4 cas)
    # ═══════════════════════════════════════════════════════════════
    {
        "question": "Mon matricule est UAM240001, est-ce que mon inscription est validée ?",
        "mots_cles_attendus": [
            "inscription", "validée", "statut", "matricule"
        ],
        "categorie": "consultation_bdd",
    },
    {
        "question": "Je voudrais savoir combien j'ai payé. Mon matricule est UAM000009.",
        "mots_cles_attendus": [
            "paiement", "FCFA", "montant", "frais"
        ],
        "categorie": "consultation_bdd",
    },
    {
        "question": "Quels sont mes résultats du semestre ? Matricule UAM030006",
        "mots_cles_attendus": [
            "note", "UE", "ECTS", "validé", "résultats"
        ],
        "categorie": "consultation_bdd",
    },
    {
        "question": "Combien d'étudiants sont inscrits à l'UAM cette année ?",
        "mots_cles_attendus": [
            "inscriptions", "statistiques", "total", "composante"
        ],
        "categorie": "consultation_bdd",
    },
    # ═══════════════════════════════════════════════════════════════
    # CATÉGORIE 10 — Instituts et écoles doctorales (12 cas)
    # ═══════════════════════════════════════════════════════════════

    # ── Instituts de recherche ──────────────────────────────────────
    {
        "question": "Qu'est-ce que l'IRSH de l'UAM ?",
        "mots_cles_attendus": [
            "IRSH", "Institut de Recherches en Sciences Humaines",
            "recherche", "sciences humaines"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Quel est le rôle de l'IREM à l'UAM ?",
        "mots_cles_attendus": [
            "IREM", "mathématiques", "enseignement", "recherche", "institut"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "À quoi sert l'Institut des Radio-Isotopes de l'UAM ?",
        "mots_cles_attendus": [
            "IRI", "radio-isotopes", "recherche", "sciences"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Combien d'instituts de recherche compte l'UAM ?",
        "mots_cles_attendus": [
            "IRSH", "IREM", "IRI", "instituts", "recherche"
        ],
        "categorie": "instituts_ecoles",
    },

    # ── École Normale Supérieure ────────────────────────────────────
    {
        "question": "Comment s'inscrire à l'École Normale Supérieure de l'UAM ?",
        "mots_cles_attendus": [
            "ENS", "École Normale Supérieure", "inscription", "formation", "enseignement"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Quelles formations propose l'ENS ?",
        "mots_cles_attendus": [
            "ENS", "enseignement", "pédagogie", "formation", "professeur"
        ],
        "categorie": "instituts_ecoles",
    },

    # ── Écoles doctorales ───────────────────────────────────────────
    {
        "question": "Quelles sont les écoles doctorales de l'UAM ?",
        "mots_cles_attendus": [
            "ED-SVT", "ED-LASHS", "ED-SET", "école doctorale", "doctorat"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Comment s'inscrire à l'École Doctorale des Sciences de la Vie et de la Terre ?",
        "mots_cles_attendus": [
            "ED-SVT", "doctorat", "sciences de la vie", "inscription", "directeur"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Qu'est-ce que l'ED-LASHS ?",
        "mots_cles_attendus": [
            "ED-LASHS", "lettres", "arts", "sciences humaines", "école doctorale"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Je veux faire un doctorat en mathématiques, quelle école doctorale choisir ?",
        "mots_cles_attendus": [
            "ED-SET", "Sciences Exactes et Techniques", "mathématiques", "doctorat"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Quelles sont les conditions d'accès aux écoles doctorales de l'UAM ?",
        "mots_cles_attendus": [
            "master", "doctorat", "directeur de thèse", "dossier", "école doctorale"
        ],
        "categorie": "instituts_ecoles",
    },
    {
        "question": "Quelle école doctorale correspond aux sciences exactes à l'UAM ?",
        "mots_cles_attendus": [
            "ED-SET", "Sciences Exactes et Techniques", "physique", "chimie", "informatique"
        ],
        "categorie": "instituts_ecoles",
    },
]


# ═══════════════════════════════════════════════════════════════════
# Statistiques du jeu de test
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from collections import Counter
    categories = Counter(t["categorie"] for t in TEST_DATASET)
    print(f"Total : {len(TEST_DATASET)} cas de test")
    print(f"\nRépartition par catégorie :")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:30s} : {count}")

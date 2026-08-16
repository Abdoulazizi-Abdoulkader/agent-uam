# Documentation technique — Agent Conversationnel UAM

> **Université Abdou Moumouni de Niamey (Niger)**
> Stack : Python 3.10+ · LangChain v1 · LangGraph v1 · FAISS · Streamlit · SQLite

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Base de connaissances RAG](#5-base-de-connaissances-rag)
6. [Base de données scolarité](#6-base-de-données-scolarité)
7. [Les 48 outils @tool](#7-les-48-outils-tool)
8. [Profils utilisateurs](#8-profils-utilisateurs)
9. [Interface web Streamlit](#9-interface-web-streamlit)
10. [Pipeline d'évaluation](#10-pipeline-dévaluation)
11. [Évaluation par paires (Option A)](#11-évaluation-par-paires-option-a)
12. [Variables d'environnement](#12-variables-denvironnement)
13. [Logs et métriques](#13-logs-et-métriques)
14. [Guide développeur](#14-guide-développeur)
15. [Dépannage](#15-dépannage)

---

## 1. Vue d'ensemble

L'agent UAM est un assistant conversationnel intelligent destiné aux étudiants, candidats et personnel de l'Université Abdou Moumouni de Niamey. Il répond aux questions sur :

- Les **facultés, écoles et instituts** (FAST, FLSH, FA, FSEG, FSJP, FSS, ENS, IEPE, IPD-AC…)
- Les **formations** disponibles (Licence L1–L3, Master M1–M2, Doctorat)
- Les **inscriptions et réinscriptions** — pièces requises, délais, procédures
- Les **frais de scolarité** — montants, modes de paiement, exonérations
- Les **démarches administratives** — attestations, diplômes, relevés de notes
- Les **services aux étudiants** — logement, bourses, bibliothèque, restauration
- Le **dossier individuel** d'un étudiant (inscription, paiements) via la base de données

### Points forts

| Capacité | Détail |
|---|---|
| **Pattern ReAct** | Le LLM choisit et enchaîne dynamiquement jusqu'à 5 outils par requête |
| **Routage intelligent** | 9 cas conversationnels détectés avant tout appel LLM |
| **48 outils spécialisés** | Recherche sémantique FAISS + requêtes SQL + données statiques |
| **Profil utilisateur** | 9 profils détectés automatiquement (bachelier, étranger, candidat master…) |
| **Mémoire de session** | `MemorySaver` LangGraph — continuité intra-session |
| **Mémoire long terme** | Préférences SQLite persistées entre sessions |
| **Évaluation automatique** | 98 questions · 3 approches comparées · 7 métriques dont RAGAS |

---

## 2. Architecture

### 2.1 Graphe LangGraph (pattern ReAct)

```
Entrée utilisateur
        │
  [route_and_store]           ← détecte le profil + classe le message
        │
        ├─ "agent"            → [call_model]   ← LLM + 48 outils bindés
        │                             │
        │                   ┌─────────┴──────────┐
        │                   ▼                    ▼
        │               [tools]              [END]
        │         (ToolNode personnalisé)
        │                   │
        │                   └──────→ [call_model] … (max 5 itérations)
        │
        ├─ "reject_query"    → [reject_query]          → [END]
        └─ "handle_special"  → [handle_special_case]   → [END]
```

**Anti-boucle** : `tool_iterations` incrémenté à chaque passage dans `[tools]`. Si `tool_iterations ≥ UAM_MAX_TOOL_ITERATIONS (5)`, `should_continue` force `END`.

### 2.2 Cas de routage dans `route_and_store`

| Signal détecté | Destination | Mécanisme |
|---|---|---|
| Abréviation seule (FA, FAST, FLSH…) | `agent` | regex sur `UAM_STRUCTURES` |
| Salutation (GREETING / BOTH) | `agent` | `detect_greeting` |
| Au revoir (FAREWELL) | `handle_special_case` | mots-clés |
| Remerciement (THANKS) | `handle_special_case` | mots-clés |
| Frustration / confusion / répétition | `handle_special_case` | `detect_frustration_or_confusion` |
| Profil CANDIDAT_MASTER | `agent` | `detect_user_profile` → suggestion `search_external_student_master` |
| Profil CANDIDAT_DOCTORAT | `agent` | `detect_user_profile` → suggestion `search_phd_admission` |
| Profil ETUDIANT_ETRANGER | `agent` | `detect_user_profile` → suggestion `search_foreign_student_procedures` |
| Question pertinente UAM | `agent` | `check_question_relevance` |
| Hors sujet | `reject_query` | — |

### 2.3 Description des modules

| Fichier | Rôle | Lignes |
|---|---|---|
| `agent_uam.py` | Point d'entrée principal, réexporte les composants | ~80 |
| `agent_graph.py` | Construit le `StateGraph` LangGraph avec `MemorySaver` | 85 |
| `agent_state.py` | `AgentState` TypedDict avec `Annotated[Sequence[BaseMessage], add]` | ~40 |
| `graph_nodes.py` | Nœuds du graphe : routage, appel LLM, cas spéciaux, rejet | 399 |
| `tools.py` | 48 outils `@tool` + vectorstore FAISS global + helpers | 2037 |
| `tool_node.py` | `ToolNode` personnalisé avec gestion d'erreur et fallback | ~120 |
| `prompts.py` | Templates de prompts système (`build_tool_system_prompt`) | ~150 |
| `app_config.py` | Configuration centralisée via variables d'env (`get_config()`) | ~180 |
| `llm_utils.py` | Initialisation LLM et embeddings selon le provider | ~200 |
| `document_loader.py` | Chargement PDF/TXT/MD + indexation FAISS | ~200 |
| `memory.py` | `UserMemory` — persistance préférences (JSON + SQLite) | ~300 |
| `uam_structures.py` | `UAM_STRUCTURES` dict statique — 9 composantes UAM | ~200 |
| `multi_agents.py` | Système multi-agents — un agent spécialisé par faculté | ~400 |
| `app_streamlit.py` | Interface web Streamlit complète | 559 |
| `chatbot.py` | Interface console CLI | ~150 |
| `database_connector.py` | Connecteur SQLite/PostgreSQL/MySQL/MongoDB | ~450 |
| `metrics.py` | Enregistrement et résumé des métriques d'utilisation | ~200 |
| `export_utils.py` | Export PDF / JSON des conversations | ~150 |
| `logger_config.py` | Logging structuré avec rotation journalière | ~80 |
| `utils.py` | Validation, sanitization, retry decorator | ~190 |

### 2.4 État du graphe (`AgentState`)

```python
class AgentState(TypedDict):
    messages:           Annotated[Sequence[BaseMessage], add]
    question:           str
    is_relevant:        bool
    context:            str
    response:           str
    need_clarification: bool
    user_id:            str
    user_preferences:   dict
    tool_iterations:    int
    user_profile:       str          # profil détecté automatiquement
```

---

## 3. Installation

### Prérequis

- Python 3.10 ou supérieur
- Au moins une clé API (voir [§4](#4-configuration))
- Optionnel : poppler-utils (extraction PDF)

### Installation automatique

```bash
git clone <url-du-repo>
cd agent-uam
./setup.sh          # crée le venv, installe les dépendances, vérifie l'env
```

### Installation manuelle

```bash
python -m venv venv
source venv/bin/activate          # Linux/macOS
# .\venv\Scripts\activate          # Windows

pip install -r requirements.txt
cp .env.example .env               # puis remplir les clés API
python test_setup.py               # vérification de l'installation
```

### Initialisation de la base de données

```bash
python seed_database.py           # crée les tables et peuple database/scolarite_uam.db avec des données de test
```

---

## 4. Configuration

### Fichier `.env`

```env
# ── Provider recommandé ──────────────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...     # accès à 300+ modèles

# ── Alternatives ─────────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...                # Llama 3.3 70B, très rapide
OPENAI_API_KEY=sk-...               # GPT-4o
ANTHROPIC_API_KEY=sk-ant-...        # Claude Sonnet

# ── Base de données (optionnel) ───────────────────────────────────────────────
UAM_DB_TYPE=sqlite                  # sqlite | postgresql | mysql | mongodb
UAM_DB_PATH=./database/scolarite_uam.db
```

### Providers LLM supportés

| Provider | Enum | Clé env | Notes |
|---|---|---|---|
| **OpenRouter** | `OPENROUTER` | `OPENROUTER_API_KEY` | Recommandé — 300+ modèles |
| **Groq** | `LLAMA_GROQ` | `GROQ_API_KEY` | Très rapide, Llama 3.3 70B |
| **OpenAI** | `OPENAI` | `OPENAI_API_KEY` | GPT-4o |
| **Anthropic** | `CLAUDE` | `ANTHROPIC_API_KEY` | Claude Sonnet |
| **Ollama** | `LLAMA_OLLAMA` | — | Exécution locale |

Pour changer de provider via l'environnement :

```env
UAM_LLM_PROVIDER=llama_groq
UAM_LLM_MODEL=llama-3.3-70b-versatile
```

---

## 5. Base de connaissances RAG

### Documents source

Les fichiers placés dans `documents_uam/` sont automatiquement chargés et indexés au démarrage :

| Fichier | Contenu |
|---|---|
| `Depliant-UAM_VNumerique.pdf` | Présentation générale de l'UAM |
| `Document_Final_SR_UAM.pdf` | Document de référence statuts et règlements |
| `formations.pdf` | Catalogue des formations |
| `Guide_Etudiant_UAM_final2_comp_2013.pdf` | Guide étudiant complet |
| `preinscription_uam.pdf` | Procédure de pré-inscription |
| `Présentation_des_Facultés_Ecoles_Instituts.txt` | Fiches des composantes |
| `Formalités_d_admission.txt` | Formalités d'admission détaillées |
| `info_UAM.md` | Informations générales |
| `guide_inscriptions.md` | Guide des inscriptions |
| `guide_reinscription.md` | Guide des réinscriptions |

Formats supportés : **PDF**, **TXT**, **Markdown (.md)**.

### Pipeline d'indexation

```
document_loader.py
    │
    ├─ PyPDFLoader / TextLoader / UnstructuredMarkdownLoader
    ├─ RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
    ├─ HuggingFaceEmbeddings — paraphrase-multilingual-MiniLM-L12-v2
    └─ FAISS.from_documents → persisté dans ./vectorstore/
```

Le vectorstore est chargé depuis le cache au prochain démarrage si `./vectorstore/` existe. Pour forcer la réindexation, supprimer ce dossier.

### Recherche sémantique

Deux fonctions internes dans `tools.py` :

- `_rag_search(query, k=5)` — retourne les `k` documents les plus proches
- `_rag_response(query, not_found_msg, k=5)` — retourne un texte formaté

**Cache LRU** : les requêtes normalisées (NFKD + suppression diacritiques) sont mises en cache pour éviter les appels FAISS redondants dans une même session.

---

## 6. Base de données scolarité

### Fichier

```
database/scolarite_uam.db    (SQLite)
```

Configuré via `.env` : `UAM_DB_TYPE=sqlite`, `UAM_DB_PATH=./database/scolarite_uam.db`.

### Schéma

```
composantes (9)
    └─ departements (27)
           └─ formations (135) ── niveau: L1–L3, M1–M2, D1–D3
                  │
                  ├─ unites_enseignement (13 pour L1 Informatique FAST)
                  │
                  └─ inscriptions (58)
                         ├─ paiements (118)
                         └─ resultats (85)
```

#### Table `etudiants` (58 enregistrements)

| Colonne | Type | Description |
|---|---|---|
| `matricule` | TEXT UNIQUE | Format : UAM + 6 chiffres |
| `nom`, `prenom` | TEXT | Identité |
| `sexe` | TEXT | M / F |
| `type_etudiant` | TEXT | nouveau / ancien / etranger |
| `annee_bac`, `serie_bac`, `mention_bac` | | Baccalauréat |

#### Table `inscriptions` (58 enregistrements)

| Colonne | Type | Valeurs |
|---|---|---|
| `statut` | TEXT | `en_attente` · `validee` · `rejetee` · `annulee` |
| `annee_academique` | TEXT | ex. `2024-2025` |
| `formation_id` | INT | FK → formations |

#### Table `paiements` (118 enregistrements)

| `type_frais` | Montant typique |
|---|---|
| `inscription` | 15 000 FCFA |
| `scolarite` | 25 000–50 000 FCFA |
| `bibliotheque` | 5 000 FCFA |
| `carte_etudiant` | 2 000 FCFA |
| `assurance` | 3 000 FCFA |

#### Table `unites_enseignement` — L1 Informatique FAST (formation_id=21)

| Code | Intitulé | Crédits | Semestre |
|---|---|---|---|
| INF101 | Introduction à l'Informatique | 6 | S1 |
| INF102 | Algorithmique I | 6 | S1 |
| MAT101 | Analyse Mathématique I | 4 | S1 |
| MAT102 | Algèbre I | 4 | S1 |
| PHY101 | Physique Générale | 3 | S1 |
| FRA101 | Techniques d'Expression Française | 3 | S1 |
| ANG101 | Anglais I | 2 | S1 |
| INF103 | Programmation C | 6 | S2 |
| INF104 | Architecture des Ordinateurs | 4 | S2 |
| MAT103 | Analyse Mathématique II | 4 | S2 |
| MAT104 | Algèbre II | 4 | S2 |
| INF105 | Systèmes d'Exploitation | 3 | S2 |
| ANG102 | Anglais II | 2 | S2 |

### Matricules de test

| Matricule | Profil | Cas de test |
|---|---|---|
| UAM240001 | L1 Informatique FAST, `statut=validee`, 50 000 FCFA payés | "Mon inscription est-elle validée ?" |
| UAM050023 | L1 Informatique FAST, `statut=validee`, 7 UEs S1 en cours | "Quels cours suis-je inscrit ce semestre ?" |
| UAM010014 | L1 Économie FSEG, `statut=en_attente`, 15 000 FCFA payés | "Est-ce que j'ai des arriérés ?" |
| UAM000009 | L3 FA, `statut=en_attente`, 45 000 FCFA payés | Paiements partiels |
| UAM030006 | L1 FSJP Droit Public, 13 résultats | Notes académiques |

### Peuplement / réinitialisation

```bash
python seed_database.py     # (ré)initialise le schéma et insère les données de test (idempotent)
```

---

## 7. Les 48 outils @tool

### Catégorie : Recherche documentaire (RAG)

| Outil | Description |
|---|---|
| `search_uam_knowledge` | Recherche libre dans toute la base documentaire |
| `search_formations` | Formations par faculté et/ou niveau |
| `search_admission_requirements` | Conditions d'admission (niveau, faculté, filière) |
| `search_required_documents` | Pièces requises pour inscription / réinscription |
| `search_registration_procedure` | Procédure d'inscription étape par étape |
| `search_registration_calendar` | Calendrier des inscriptions |
| `search_prerequisites` | Prérequis académiques d'une filière |
| `search_competences_requises` | Compétences attendues |
| `search_cycles_et_duree` | Durée et cycles de formation |
| `search_chronogramme` | Chronogramme des cours |
| `search_coefficients` | Coefficients et crédits ECTS |
| `search_professeurs` | Information sur le corps professoral |
| `search_debouches` | Débouchés professionnels |
| `search_avantages_universite` | Avantages et points forts de l'UAM |
| `search_reglement_interieur` | Règlement intérieur d'une faculté |
| `search_organisation_corps_professoral` | Organisation du corps enseignant |
| `search_organisation_corps_estudiantin` | Organisation des étudiants |
| `search_reclamations` | Procédures de réclamation |
| `search_housing_and_services` | Logement, restauration, services campus |
| `search_scholarships` | Bourses et aides financières |
| `search_contacts_services` | Contacts et services administratifs |
| `search_student_card` | Carte étudiante — obtention et usage |
| `search_transfer_equivalence` | Transfert et équivalences de diplômes |
| `search_international_equivalence` | Équivalences internationales |
| `search_late_reenrollment` | Réinscription tardive |
| `search_internship_info` | Stages et insertion professionnelle |
| `search_double_degree` | Double diplôme |
| `search_latest_news` | Dernières actualités et annonces (BDD) |

### Catégorie : Structures UAM (données statiques)

| Outil | Description |
|---|---|
| `get_faculty_info` | Fiche complète d'une composante (nom, mission, filières) |
| `get_structure_by_abbreviation` | Recherche par sigle (FAST, FLSH, FA…) |
| `list_all_structures` | Liste toutes les composantes de l'UAM |

### Catégorie : Profils spécialisés

| Outil | Description |
|---|---|
| `search_external_student_master` | Procédures pour candidats master extérieurs à l'UAM |
| `search_phd_admission` | Admission en doctorat |
| `search_foreign_student_procedures` | Procédures étudiants étrangers |
| `search_recognition_prior_learning` | Validation des acquis (VAE) |
| `search_master_thesis_supervision` | Encadrement mémoires de master |
| `search_academic_partnership` | Partenariats académiques |

### Catégorie : Base de données

| Outil | Description |
|---|---|
| `search_student_record` | Dossier étudiant par matricule (`query_type`: inscription / paiement / resultats / cours / general) |
| `get_schedules_from_db` | Emplois du temps (faculté, filière, niveau) |
| `calculate_fees` | Calcul des frais selon le niveau et la faculté |

### Catégorie : Détection et conversation

| Outil | Description |
|---|---|
| `detect_greeting` | Classifie un message : GREETING / FAREWELL / THANKS / BOTH / NONE |
| `check_question_relevance` | Vérifie si une question est pertinente pour l'UAM |
| `detect_user_profile` | Classifie l'utilisateur en 9 profils |
| `detect_frustration_or_confusion` | Détecte frustration, confusion, répétition |
| `get_agent_capabilities` | Explique ce que l'agent sait faire |

### Catégorie : Mémoire utilisateur

| Outil | Description |
|---|---|
| `save_user_preference` | Enregistre une préférence (langue, niveau, faculté…) |
| `get_user_preferences` | Récupère les préférences enregistrées |

### Catégorie : Utilitaires

| Outil | Description |
|---|---|
| `generate_registration_checklist` | Génère une checklist personnalisée pour l'inscription |

---

## 8. Profils utilisateurs

`detect_user_profile` classe chaque message en 9 profils. Le profil enrichit le prompt système avec des outils prioritaires.

| Profil | Signaux textuels | Outils prioritaires |
|---|---|---|
| `BACHELIER` | "bac", "terminale", "viens d'avoir" | `search_admission_requirements`, `calculate_fees` |
| `ETUDIANT_UAM` | "mon matricule", "réinscription", "relevé" | `search_student_record`, `search_registration_procedure` |
| `ETUDIANT_EXTERNE` | "transfert", "viens d'une autre université" | `search_transfer_equivalence` |
| `ETUDIANT_ETRANGER` | "étranger", "visa", "pays" | `search_foreign_student_procedures`, `search_international_equivalence` |
| `CANDIDAT_MASTER` | "master", "M1", "mémoire" | `search_external_student_master`, `search_formations` |
| `CANDIDAT_DOCTORAT` | "thèse", "doctorat", "PhD" | `search_phd_admission`, `search_master_thesis_supervision` |
| `PROFESSIONNEL` | "VAE", "formation continue", "reprise" | `search_recognition_prior_learning` |
| `PARENT` | "mon fils", "ma fille", "enfant" | `search_required_documents`, `search_housing_and_services` |
| `INCONNU` | — | outils généraux |

---

## 9. Interface web Streamlit

### Lancement

```bash
source venv/bin/activate
streamlit run app_streamlit.py
# Ouvrir http://localhost:8501
```

Ou via le script :

```bash
./run_streamlit.sh
```

### Fonctionnalités

- Sélection du **provider LLM** et du **modèle** depuis la barre latérale
- **Historique de conversation** persisté dans la session
- **Indicateur de profil** détecté automatiquement
- **Métriques en temps réel** — temps de réponse, nombre d'appels outils
- **Export** de la conversation en JSON ou PDF
- **Mode multi-agents** — activation optionnelle des agents spécialisés par faculté
- **Rate limiting** affiché à l'utilisateur si dépassé

---

## 10. Pipeline d'évaluation

### Dataset d'évaluation

Fichier : `dataset_evaluation.csv`

| Statistique | Valeur |
|---|---|
| Total de questions | 98 |
| Questions pertinentes UAM | 74 |
| Questions hors-sujet | 24 |

**Catégories** :

| Catégorie | Nb |
|---|---|
| `hors_sujet` | 24 |
| `instituts_ecoles` | 12 |
| `formations_facultes` | 9 |
| `profils_specialises` | 6 |
| `multi_etape` | 6 |
| `inscription_premiere` | 5 |
| `effectifs` | 5 |
| `consultation_bdd` | 7 |
| `inscription_master_doctorat` | 4 |
| `localisation` | 4 |
| `historique` | 4 |
| `inscription_reinscription` | 3 |
| `frais` | 3 |
| `contacts_services` | 3 |
| `conversation_simple` | 3 |

### Métriques calculées

| Métrique | Description | Seuil recommandé |
|---|---|---|
| **Exactitude** | Taux de bonne classification pertinent/hors-sujet | > 0.85 |
| **Précision** | Vraies pertinentes / (vraies + fausses pertinentes) | > 0.80 |
| **Rappel** | Vraies pertinentes / toutes les pertinentes attendues | > 0.80 |
| **F1-Score** | Moyenne harmonique précision/rappel | > 0.80 |
| **Keyword Recall** | Proportion de mots-clés attendus dans la réponse | > 0.70 |
| **ROUGE-1/2/L** | Chevauchement n-grammes avec le `ground_truth` | > 0.40 / 0.20 / 0.35 |
| **Faithfulness** (RAGAS) | Ancrage dans les chunks récupérés | > 0.70 |
| **Answer Relevancy** (RAGAS) | Adéquation de la réponse à la question | > 0.70 |
| **Latence P50 / P90** | Temps de réponse médian / percentile 90 | < 5 000 / 10 000 ms |

> RAGAS n'est pas calculé pour le mode **LLM seul** (il présuppose un contexte récupéré).

### Trois approches comparées

| Approche | Flag | Description |
|---|---|---|
| **LLM seul** | `--llm-only` | Génération directe, sans retrieval ni outils |
| **RAG séquentielle** | `--baseline` | Retrieve top-4 documents → generate, sans graphe |
| **Agent LangGraph** | *(défaut)* | Graphe ReAct + 48 outils + routage + mémoire |

### Commandes

```bash
# Évaluation complète de l'agent
python evaluate.py

# Test rapide sur 10 questions
python evaluate.py --limit 10 --no-ragas

# Mode baseline RAG séquentielle
python evaluate.py --baseline

# Mode LLM seul
python evaluate.py --llm-only

# Limiter RAGAS à 30 exemples (plus rapide)
python evaluate.py --ragas-limit 30

# Comparaison complète des 3 approches → génère COMPARISON_REPORT.md
./run_comparison.sh

# Avec options
./run_comparison.sh --ragas-limit 74
./run_comparison.sh --limit 20 --no-ragas
./run_comparison.sh --ragas-limit 30 --ragas-workers 2
```

### Options de `evaluate.py`

| Option | Défaut | Description |
|---|---|---|
| `--dataset FILE` | `dataset_evaluation.csv` | Chemin vers le CSV |
| `--limit N` | — | Limiter à N questions |
| `--no-ragas` | — | Désactiver le calcul RAGAS |
| `--baseline` | — | Mode RAG séquentielle |
| `--llm-only` | — | Mode LLM seul |
| `--ragas-limit N` | `50` | Nb max d'exemples pour RAGAS |
| `--ragas-workers N` | `1` | Workers parallèles RAGAS |
| `--temperature T` | `0.0` | Température du LLM |
| `--output DIR` | `./evaluation_results` | Dossier de sortie |

### Sorties

```
evaluation_results/
├── evaluation_detail_YYYYMMDD_HHMMSS.csv     ← une ligne par question
├── evaluation_summary_YYYYMMDD_HHMMSS.csv    ← résumé des métriques
├── evaluation_complete_YYYYMMDD_HHMMSS.json  ← archive complète
└── tableau_latex_YYYYMMDD_HHMMSS.tex         ← tableaux LaTeX prêts à l'emploi

COMPARISON_REPORT.md                           ← rapport des 3 approches
```

---

## 11. Évaluation par paires (Option A)

### Principe

Le **run gelé** produit des réponses canoniques à temperature=0, alignées avec les chunks RAG récupérés. Ces paires (question, réponse, chunks) servent ensuite à un évaluateur LLM qui juge chaque réponse.

### Modules

| Module | Rôle |
|---|---|
| `grounding_capture.py` | Journal thread-safe des appels de récupération RAG (chunks + scores) |
| `run_grounding_capture.py` | Exécute le run gelé sur les 74 questions pertinentes |
| `context_tracker.py` | Tracker de contexte pour RAGAS dans `evaluate.py` |

### Workflow

```
1. python run_grounding_capture.py
        │
        ├─ Charge 74 questions (expected_relevant=true)
        ├─ Initialise le LLM avec temperature=0
        ├─ Active grounding_capture (bypass cache LRU)
        ├─ Exécute chaque question séquentiellement
        │        └─ grounding_capture.set_current_question()
        │        └─ agent.invoke()
        │        └─ _rag_search() → grounding_capture.log_retrieval()
        └─ Produit :
               responses_frozen.csv    ← 74 (question, réponse canonique)
               grounding_log.json      ← chunks + scores pour chaque appel RAG

2. Évaluateur LLM externe (ex. Claude)
        └─ lit responses_frozen.csv + grounding_log.json
        └─ juge chaque réponse (pertinence, ancrage, complétude)
```

### Commandes

```bash
# Run gelé complet (74 questions)
python run_grounding_capture.py

# Test rapide sur 5 questions
python run_grounding_capture.py --limit 5

# Avec modèle spécifique
python run_grounding_capture.py --model "meta-llama/llama-3.3-70b-instruct"
```

> **Important** : Ne pas relancer `run_grounding_capture.py` après la première exécution réussie — les fichiers `responses_frozen.csv` et `grounding_log.json` sont les références canoniques.

---

## 12. Variables d'environnement

### Variables de configuration principale

| Variable | Défaut | Description |
|---|---|---|
| `UAM_LLM_PROVIDER` | `openrouter` | Provider LLM actif |
| `UAM_LLM_MODEL` | selon provider | Nom du modèle |
| `UAM_LLM_TEMPERATURE` | `0.3` | Température (0 = déterministe) |
| `UAM_DOCUMENTS_DIR` | `./documents_uam` | Dossier des documents source |
| `UAM_VECTORSTORE_DIR` | `./vectorstore` | Cache FAISS persisté |
| `UAM_CHUNK_SIZE` | `1000` | Taille des chunks de découpage |
| `UAM_CHUNK_OVERLAP` | `200` | Chevauchement entre chunks |
| `UAM_SIMILARITY_K` | `4` | Nombre de documents retournés par recherche |
| `UAM_MAX_TOOL_ITERATIONS` | `5` | Limite de la boucle ReAct |
| `UAM_RATE_LIMIT` | `60` | Requêtes max par minute |

### Variables de base de données

| Variable | Défaut | Description |
|---|---|---|
| `UAM_DB_TYPE` | — | `sqlite` / `postgresql` / `mysql` / `mongodb` |
| `UAM_DB_PATH` | `./database/scolarite_uam.db` | Chemin SQLite |
| `UAM_DB_HOST` | `localhost` | Hôte PostgreSQL/MySQL |
| `UAM_DB_PORT` | `5432` / `3306` | Port PostgreSQL/MySQL |
| `UAM_DB_NAME` | `uam_db` | Nom de la base |
| `UAM_DB_USER` | — | Utilisateur BDD |
| `UAM_DB_PASSWORD` | — | Mot de passe BDD |

---

## 13. Logs et métriques

### Logs applicatifs

Stockés dans `logs/` avec rotation journalière (format `YYYY-MM-DD.log`).

```python
from logger_config import get_logger
logger = get_logger(__name__)
logger.info("message")
logger.debug("détail")
logger.error("erreur", exc_info=True)
```

### Métriques d'utilisation

Enregistrées dans `metrics.db` (SQLite) via `metrics.py` :

- Nombre de questions traitées
- Temps de réponse moyen
- Taux de questions hors-sujet
- Taux d'appels à chaque outil

```python
from metrics import record_query, get_summary
record_query(question, response_time_ms, is_relevant, tool_calls)
summary = get_summary()
```

---

## 14. Guide développeur

### Ajouter un nouvel outil

1. Définir la fonction avec le décorateur `@tool` dans `tools.py`
2. Ajouter une docstring claire (le LLM s'en sert pour décider quand l'appeler)
3. La fonction est automatiquement intégrée via `get_tools()` → `agent_graph.py`

```python
@tool
def search_my_feature(query: str, faculty: str = "") -> str:
    """
    Cherche [description précise]. Utiliser quand l'utilisateur demande [cas].

    Args:
        query:   Terme de recherche
        faculty: Sigle de la faculté (FAST, FLSH, FA…) — optionnel
    """
    return _search_by_faculty_or_uam(query, faculty, "Aucune info trouvée pour {target}.")
```

### Ajouter une catégorie de routage

Dans `graph_nodes.py`, fonction `route_and_store` :

```python
if detect_my_condition(last_message):
    return {**state, "routing_decision": "my_target"}
```

Puis ajouter l'arête conditionnelle dans `agent_graph.py`.

### Tests

```bash
source venv/bin/activate
python test_setup.py          # vérification de l'installation
python -m pytest tests/       # suite de tests unitaires
```

### Structure des tests

```
tests/
├── test_tools.py             # Tests des outils @tool
├── test_graph_nodes.py       # Tests du routage et des nœuds
├── test_database.py          # Tests du connecteur BDD
└── test_utils.py             # Tests des utilitaires
```

---

## 15. Dépannage

### "Aucun document trouvé dans documents_uam/"

Vérifiez que le dossier contient des fichiers PDF, TXT ou MD. Le loader ignore les fichiers vides.

### "API key not found"

Le fichier `.env` doit exister à la racine du projet. Vérifiez que la clé correspond au provider configuré dans `UAM_LLM_PROVIDER`.

### "Provider non supporté" / ImportError

Installez le package LangChain du provider manquant :

```bash
pip install langchain-groq        # Groq
pip install langchain-openai      # OpenAI / OpenRouter
pip install langchain-anthropic   # Claude
pip install langchain-community   # Ollama
```

### Erreur FAISS sur Windows

```bash
conda install -c pytorch faiss-cpu
```

### L'agent boucle (dépasse max_tool_iterations)

Augmenter `UAM_MAX_TOOL_ITERATIONS` dans `.env` (défaut : 5). Ou vérifier que les outils retournent des réponses non vides.

### La base de données SQLite ne répond pas

```bash
python -c "from database_connector import is_database_available; print(is_database_available())"
```

Si `False`, vérifier que `UAM_DB_TYPE=sqlite` et que `UAM_DB_PATH` pointe vers le bon fichier.

### Réindexer les documents FAISS

```bash
rm -rf vectorstore/
python agent_uam.py   # ou streamlit run app_streamlit.py — la réindexation est automatique
```

### RAGAS échoue avec "context is empty"

Vérifier que `context_tracker.push_context()` est bien appelé dans `_rag_search`. Le contexte est accessible via `context_tracker.get_context()` pour chaque thread.

---

*Documentation générée le 2026-06-09 — projet agent-uam · Université Abdou Moumouni de Niamey*

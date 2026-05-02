# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Agent UAM** is a conversational AI assistant for Université Abdou Moumouni de Niamey (Niger). It uses a LangGraph ReAct agent with ~48 tools, a FAISS RAG pipeline, and an OpenRouter LLM backend to answer questions about admissions, formations, faculties, fees, and student services. The system supports both a CLI chatbot and a Streamlit web interface.

---

## Commandes principales

```bash
# Lancer l'interface web Streamlit (recommandé)
streamlit run app_streamlit.py

# Lancer en mode console (CLI)
python agent_uam.py

# Vérifier l'installation et les dépendances
python test_setup.py

# Initialiser la base de données (schéma + données de test)
python setup_database.py

# Installer les dépendances
pip install -r requirements.txt

# Activer l'environnement virtuel
source venv/bin/activate
```

---

## Configuration requise

Créer un fichier `.env` à la racine. **OPENROUTER_API_KEY est requis** (provider par défaut) :

```env
OPENROUTER_API_KEY=sk-or-v1-...   # Requis (défaut — accès multi-modèles)
OPENAI_API_KEY=sk-...              # Alternatif (si provider OPENAI)
ANTHROPIC_API_KEY=sk-ant-...       # Alternatif (si provider CLAUDE)
GROQ_API_KEY=gsk_...               # Alternatif (si provider LLAMA_GROQ)
```

Le provider par défaut est `OPENROUTER` avec le modèle `openai/gpt-4o-mini`. Pour changer de provider ou de modèle, utiliser les variables d'env `UAM_LLM_PROVIDER` et `UAM_LLM_MODEL`.

Les documents UAM (PDF/TXT/MD) doivent être placés dans `documents_uam/`.

---

## Architecture

### Flux d'exécution

```
Utilisateur
    ↓
chatbot.py (run_chatbot) ou app_streamlit.py — point d'entrée
    ↓
agent_graph.py (create_agent_graph) — construit le StateGraph LangGraph
    ↓
graph_nodes.py — 5 nœuds du graphe :
  • route_and_store   → détermine le type de message, stocke routing_hint + routing_context
  • call_model        → appelle le LLM avec outils bindés
  • should_continue   → décide : appel outils ou fin (limite max_tool_iterations)
  • handle_special_case → répond directement sans LLM (adieux, remerciements, frustration, confusion, répétition)
  • reject_query      → répond poliment aux questions hors sujet
    ↓
tool_node.py (ToolNode) — exécute les outils, incrémente tool_iterations
    ↓
tools.py — ~48 outils @tool (recherche FAISS, détection, DB, préférences)
```

### Modules clés

| Fichier | Rôle |
|---|---|
| `agent_uam.py` | Module principal — réexporte tout, point d'entrée `__main__` |
| `agent_graph.py` | Construction du `StateGraph` LangGraph avec `MemorySaver` |
| `agent_state.py` | `AgentState` TypedDict — messages, routing_hint, tool_iterations, user_profile, etc. |
| `graph_nodes.py` | Implémentations des 5 nœuds du graphe |
| `tools.py` | ~48 outils `@tool` + gestion du vectorstore FAISS global |
| `tool_node.py` | `ToolNode` wrapper LangGraph (avec fallback de compatibilité) |
| `app_config.py` | Config centralisée via dataclasses — `AppConfig`, `LLMConfig`, `VectorStoreConfig`, `DatabaseConfig`; enum `LLMProvider` |
| `llm_utils.py` | Initialisation du LLM (OpenRouter uniquement) et des embeddings HuggingFace |
| `document_loader.py` | Chargement PDF/TXT/DOCX/MD + indexation FAISS avec cache par fingerprint SHA256 |
| `memory.py` | `UserMemory` — préférences utilisateur persistées en SQLite (avec migration depuis JSON) |
| `uam_structures.py` | `UAM_STRUCTURES` dict — 7 facultés, 3 instituts, 4 écoles doctorales |
| `database_connector.py` | Adaptateur multi-BDD (PostgreSQL, MySQL, SQLite, MongoDB) |
| `metrics.py` | Collecte de métriques en SQLite (questions, temps de réponse, CPU/mémoire) |
| `utils.py` | Utilitaires — `sanitize_input`, `validate_question`, `retry_on_failure`, `format_error_message` |
| `export_utils.py` | Export des conversations en JSON ou PDF (via ReportLab) |
| `multi_agents.py` | Système multi-agents — un agent spécialisé par faculté UAM |
| `app_streamlit.py` | Interface web Streamlit (sélection de modèle, chat, métriques, export) |
| `chatbot.py` | REPL CLI interactif avec enregistrement de métriques |
| `prompts.py` | Templates de prompts système (`build_tool_system_prompt`, `build_context_system_prompt`) |
| `logger_config.py` | Logging structuré avec rotation par date — `logs/agent_uam_YYYYMMDD.log` |
| `evaluate.py` | Évaluation automatisée sur dataset CSV (pour la thèse) |
| `setup_database.py` | Création du schéma de BDD et population avec données de test |
| `test_setup.py` | Vérification de l'installation et des dépendances |
| `tests/test_utils.py` | Tests unitaires des utilitaires |
| `evaluation/build_memoire.py` | Construction du mémoire d'évaluation |
| `evaluation/test_dataset_uam.py` | Dataset de test pour l'évaluation |

> **Note** : Il n'existe pas de fichier `config.py` séparé. L'enum `LLMProvider` et toutes les configurations sont dans `app_config.py`.

---

## Schéma de l'état (`AgentState`)

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]  # accumulé automatiquement
    question: str
    is_relevant: bool
    context: str                # contexte RAG récupéré
    response: str
    need_clarification: bool
    user_id: str
    user_preferences: dict
    tool_iterations: int        # compteur anti-boucle
    routing_hint: str           # "agent" | "reject_query" | "handle_special_case"
    routing_context: str        # "FAREWELL" | "THANKS" | "FRUSTRATION" | "CONFUSION" | "REPETITION"
    user_profile: str           # voir profils ci-dessous
```

---

## Pattern LangGraph

Le graphe suit le pattern ReAct avec tools :
1. `route_and_store` → détecte le type de message, stocke `routing_hint` + `routing_context`
2. Arête conditionnelle → `agent`, `reject_query`, ou `handle_special_case`
3. `agent` (`call_model`) → LLM avec outils bindés via `llm.bind_tools(tools)`
4. `should_continue` → si `tool_calls` présents ET `tool_iterations < max` → `tools`, sinon → `END`
5. `tools` (ToolNode) → exécute les outils, incrémente `tool_iterations` → retour à `agent`
6. `handle_special_case` → répond directement pour : FAREWELL, THANKS, FRUSTRATION, CONFUSION, REPETITION
7. `reject_query` → répond poliment aux questions hors sujet
8. Limite anti-boucle : `max_tool_iterations = 5` (configurable via `UAM_MAX_TOOL_ITERATIONS`)
9. Persistance de session : `MemorySaver` avec un `thread_id` UUID unique par session

---

## Cas conversationnels gérés par `route_and_store`

| Cas détecté | Destination | Action / Outils |
|---|---|---|
| Abréviation seule (FA, FAST, FLSH…) | `agent` | `get_faculty_info` ou `get_structure_by_abbreviation` |
| Salutation simple | `agent` | `detect_greeting` |
| FAREWELL (au revoir, bye, bonne journée…) | `handle_special_case` | Réponse pré-écrite |
| THANKS (merci, parfait, super…) | `handle_special_case` | Réponse pré-écrite |
| Frustration / confusion | `handle_special_case` | `detect_frustration_or_confusion` |
| Répétition de question | `handle_special_case` | Réponse pré-écrite |
| Profil CANDIDAT_MASTER | `agent` | `search_external_student_master` prioritaire |
| Profil CANDIDAT_DOCTORAT | `agent` | `search_phd_admission` prioritaire |
| Profil ETUDIANT_ETRANGER | `agent` | `search_foreign_student_procedures` prioritaire |
| Question UAM pertinente | `agent` | Outils spécialisés selon contexte |
| Hors sujet | `reject_query` | — |

---

## Profils utilisateur détectés automatiquement

`detect_user_profile` (outil regex) classe chaque message en :
`BACHELIER`, `ETUDIANT_UAM`, `ETUDIANT_EXTERNE`, `ETUDIANT_ETRANGER`, `CANDIDAT_MASTER`, `CANDIDAT_DOCTORAT`, `PROFESSIONNEL`, `PARENT`, `INCONNU`.

Le profil est stocké dans `AgentState.user_profile` et enrichit le prompt système dans `call_model` pour orienter le LLM vers les outils prioritaires.

---

## Outils (`tools.py`)

Le fichier expose ~48 outils `@tool`. La fonction `get_tools()` retourne la liste complète et inclut conditionnellement les outils DB si `_db_available = True`.

### Catégories d'outils

| Catégorie | Exemples d'outils |
|---|---|
| Détection (sans RAG) | `detect_greeting`, `detect_user_profile`, `detect_frustration_or_confusion`, `check_question_relevance` |
| Formations & Académique | `search_formations`, `search_prerequisites`, `search_cycles_et_duree`, `search_coefficients`, `search_debouches` |
| Admission & Inscription | `search_admission_requirements`, `search_required_documents`, `search_registration_procedure`, `search_registration_calendar`, `generate_registration_checklist`, `calculate_fees` |
| Profils spéciaux | `search_external_student_master`, `search_phd_admission`, `search_foreign_student_procedures` |
| Services & Vie étudiante | `search_housing_and_services`, `search_scholarships`, `search_contacts_services`, `search_internship_info` |
| Structures UAM | `get_faculty_info`, `get_structure_by_abbreviation`, `list_all_structures` |
| Base de données | `search_latest_news`, `get_schedules_from_db` (actifs si DB disponible) |
| Préférences utilisateur | `save_user_preference`, `get_user_preferences` |

### État global dans tools.py

- `_vectorstore` — référence FAISS thread-safe (via `_vectorstore_lock`)
- `_thread_local` — stockage `user_id` par thread pour les sessions Streamlit
- `_db_available` — flag de connectivité base de données

---

## Vectorstore FAISS

- Initialisé dans `document_loader.py`, injecté dans `tools.py` via `set_vectorstore()`
- **Cache intelligent** : fingerprint SHA256 de tous les fichiers de documents — rechargement uniquement si les fichiers ont changé, le modèle d'embedding ou le provider change
- Embeddings : `HuggingFaceEmbeddings` (modèle `paraphrase-multilingual-MiniLM-L12-v2`)
- Persistance dans `./vectorstore/` (index.faiss + index.pkl + index.meta.json)
- Paramètres : `chunk_size=1000`, `chunk_overlap=200`, `similarity_k=4`

---

## Initialisation LLM (`llm_utils.py`)

- Seul **OPENROUTER** est actuellement supporté (le code ignore les autres providers)
- Requiert `OPENROUTER_API_KEY` dans l'environnement
- Retourne une instance `ChatOpenAI` pointant vers `openrouter.ai/api/v1`
- Headers automatiques : `HTTP-Referer`, `X-Title`
- Thread-safe via `_openrouter_lock`
- Défauts : modèle `openai/gpt-4o-mini`, température `0.3`

---

## Base de données (`database_connector.py`)

Adaptateur multi-BDD qui supporte PostgreSQL, MySQL, SQLite, et MongoDB.

- `get_db_connection()` — connexion singleton avec initialisation lazy
- `query_database(query, params)` — adapte les placeholders SQL selon le SGBD
- `search_formations_db`, `search_fees_db`, `search_news_announcements_db`, `search_schedules_db` — fonctions de recherche spécialisées
- `is_database_available()` — vérifie la connectivité
- Configure via les variables `UAM_DB_*` dans `.env`

---

## Métriques (`metrics.py`)

Collecte automatique en SQLite (`metrics.db`) :
- `record_question(user_id, question, is_relevant, response_time_ms)` — une ligne par interaction
- `get_metrics_summary()` — total questions, hors-sujet, temps de réponse moyen
- `get_top_questions(limit)` — questions les plus fréquentes (normalisées)
- `record_system_metrics()` — CPU% et mémoire% (requiert `psutil`)

---

## Variables d'environnement de configuration

| Variable | Défaut | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | **(requis)** | Clé API OpenRouter |
| `UAM_LLM_PROVIDER` | `openrouter` | Provider LLM |
| `UAM_LLM_MODEL` | `openai/gpt-4o-mini` | Modèle LLM |
| `UAM_LLM_TEMPERATURE` | `0.3` | Température de génération |
| `UAM_DOCUMENTS_DIR` | `./documents_uam` | Dossier documents (PDF/TXT/MD) |
| `UAM_VECTORSTORE_DIR` | `./vectorstore` | Persistance FAISS |
| `UAM_CHUNK_SIZE` | `1000` | Taille des chunks de découpage |
| `UAM_CHUNK_OVERLAP` | `200` | Chevauchement des chunks |
| `UAM_SIMILARITY_K` | `4` | Nombre de résultats de similarité |
| `UAM_MAX_TOOL_ITERATIONS` | `5` | Limite de boucle outils |
| `UAM_MAX_INPUT_LENGTH` | `2000` | Longueur max d'entrée utilisateur |
| `UAM_MEMORY_DB` | `./user_memory.db` | SQLite préférences utilisateur |
| `UAM_METRICS_DB` | `./metrics.db` | SQLite métriques d'usage |
| `UAM_DB_TYPE` | `None` | Type BDD externe (postgresql/mysql/mongodb) |
| `UAM_DB_HOST` | `localhost` | Hôte BDD externe |
| `UAM_DB_PORT` | selon SGBD | Port BDD externe |
| `UAM_DB_NAME` | `uam_db` | Nom de la BDD externe |
| `UAM_DB_USER` | — | Utilisateur BDD |
| `UAM_DB_PASSWORD` | — | Mot de passe BDD |

---

## Interface Streamlit (`app_streamlit.py`)

- Sélecteur de modèle parmi 8 modèles OpenRouter (GPT-4o, Claude Sonnet, Llama 70B, Gemma 3, Mistral, DeepSeek…)
- Gestion de session : `user_id`, `messages`, `agent_initialized`, `conversation_history`
- Dashboard métriques dans la barre latérale
- Export conversations en JSON ou PDF
- Questions suggérées et grille de présentation des fonctionnalités

---

## Évaluation (`evaluate.py`, `evaluation/`)

Système d'évaluation pour la thèse de Master :
- `load_dataset(path)` — lit un CSV avec colonnes : `question`, `ground_truth`, `category`, `expected_relevant`, `mots_cles`
- `run_agent_on_dataset(agent, vectorstore, samples, config)` — exécute l'agent sur chaque question, mesure `response_time_ms`, collecte les documents récupérés
- CLI : `python evaluate.py --dataset data.csv --limit 50`
- `evaluation/test_dataset_uam.py` — dataset de test structuré
- `evaluation/build_memoire.py` — génération des tableaux de résultats pour le mémoire

---

## Patterns de conception importants

1. **Singleton thread-safe** : Config (`get_config()`), LLM, embeddings, connexions DB utilisent `_lock` + `_instance`
2. **Tool binding automatique** : `llm.bind_tools(tools)` — le LLM choisit et appelle les outils seul
3. **Réduction de messages** : `Annotated[Sequence[BaseMessage], add]` accumule automatiquement les messages dans l'état
4. **Cache FAISS par fingerprint** : évite de reconstruire l'index si les documents n'ont pas changé
5. **Détection par regex** : greeting, frustration, profil utilisateur, pertinence — pas de ML séparé
6. **Enrichissement de contexte** : `detect_structure_in_text()` détecte les abréviations et étend les requêtes de recherche
7. **Stratégies de fallback** : DB indisponible → valeurs statiques codées en dur; FAISS manquant → message d'erreur explicite
8. **Abstraction multi-BDD** : adaptation automatique des placeholders SQL selon le SGBD cible

---

## Conventions de développement

- Tout le texte visible par l'utilisateur et les docstrings des outils sont en **français** (les docstrings des `@tool` sont lus par le LLM pour choisir l'outil)
- Les noms de variables et fonctions internes sont en **anglais** (style snake_case Python)
- Le vectorstore est initialisé **une seule fois** au démarrage et partagé via `set_vectorstore()` / `get_vectorstore()`
- Les logs vont dans `logs/` avec rotation journalière ; les erreurs dans `logs/errors_YYYYMMDD.log` en plus
- Ne jamais appeler `initialize_llm()` ou `initialize_embeddings()` directement depuis les nœuds — passer les instances déjà créées
- Pour ajouter un outil : définir avec `@tool`, docstring en français, ajouter à la liste dans `get_tools()`
- L'état du graphe (`AgentState`) ne doit être modifié que dans les nœuds via `return {...}` (immutabilité LangGraph)

---

## Structure des fichiers

```
agent-uam/
├── Core Graph & State
│   ├── agent_uam.py          # Point d'entrée & exports
│   ├── agent_state.py        # TypedDict AgentState
│   ├── agent_graph.py        # Construction du StateGraph
│   ├── graph_nodes.py        # 5 nœuds + logique de routage
│   └── tool_node.py          # Wrapper ToolNode avec fallback
│
├── Tools & Knowledge
│   ├── tools.py              # ~48 outils @tool + état vectorstore global
│   ├── uam_structures.py     # Registre des structures UAM (7 facultés, 3 instituts, 4 écoles)
│   └── document_loader.py    # Chargement docs + indexation FAISS (cache SHA256)
│
├── Configuration & System
│   ├── app_config.py         # AppConfig, LLMConfig, VectorStoreConfig, DatabaseConfig, LLMProvider
│   ├── llm_utils.py          # Init LLM (OpenRouter) + embeddings
│   ├── prompts.py            # Prompts système et guide d'outils
│   ├── logger_config.py      # Logging rotatif journalier
│   └── utils.py              # sanitize_input, validate_question, retry_on_failure, etc.
│
├── Persistence
│   ├── memory.py             # UserMemory (SQLite, migration JSON)
│   ├── metrics.py            # Métriques d'usage (SQLite)
│   ├── database_connector.py # Adaptateur PostgreSQL/MySQL/SQLite/MongoDB
│   └── export_utils.py       # Export JSON et PDF (ReportLab)
│
├── Interfaces
│   ├── chatbot.py            # REPL CLI
│   └── app_streamlit.py      # Interface web Streamlit
│
├── Evaluation & Tests
│   ├── evaluate.py           # Évaluation automatisée sur dataset CSV
│   ├── human_eval.py         # Évaluation humaine
│   ├── setup_database.py     # Schéma & données de test BDD
│   ├── test_setup.py         # Vérification installation
│   ├── tests/test_utils.py   # Tests unitaires utils
│   └── evaluation/           # Dataset et scripts pour la thèse
│
├── documents_uam/            # Documents source (PDF, TXT, MD)
├── vectorstore/              # Index FAISS persisté (index.faiss, index.pkl, index.meta.json)
├── logs/                     # Logs rotatifs (créé automatiquement)
├── requirements.txt          # Dépendances Python
└── .env                      # Variables d'environnement (non versionné)
```

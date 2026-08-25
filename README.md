# Agent Conversationnel UAM

Assistant virtuel intelligent pour l'Université Abdou Moumouni de Niamey (UAM), construit avec LangChain v1.0+ et LangGraph v1.0+.

---

## Table des matières

- [Description](#description)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Évaluation automatique](#évaluation-automatique)
- [Structure du projet](#structure-du-projet)
- [Providers LLM supportés](#providers-llm-supportés)
- [Dépannage](#dépannage)

---

## Description

L'agent répond aux questions des étudiants, enseignants et visiteurs de l'UAM sur :

- Les facultés, écoles et instituts (FAST, FLSH, FA, FSEG, FSJP, FSS, ENS…)
- Les formations et filières disponibles (Licence, Master, Doctorat)
- Les conditions d'admission et pièces d'inscription
- Les démarches administratives (diplômes, attestations, relevés)
- Les services aux étudiants (logement, bourses, restauration, bibliothèque)
- Les contacts des services universitaires

La base de connaissances est construite à partir des documents officiels de l'UAM (PDF, TXT, Markdown), indexés avec FAISS et des embeddings multilingues.

---

## Fonctionnalités

- **Routage intelligent** — détecte automatiquement le type de message (salutation, remerciement, frustration, question UAM, hors sujet) avant tout appel LLM
- **Pattern ReAct** — le LLM choisit et enchaîne les outils nécessaires (45+ outils spécialisés)
- **Profil utilisateur** — adapte les réponses selon le profil détecté (bachelier, étudiant étranger, candidat master/doctorat, professionnel, parent…)
- **Recherche sémantique FAISS** — recherche vectorielle multilingue dans les documents UAM
- **Mémoire de session** — continuité conversationnelle via `MemorySaver` (LangGraph)
- **Mémoire long terme** — préférences utilisateur persistées en SQLite
- **Interface web** — UI Streamlit moderne avec export JSON/PDF
- **Mode multi-agents** — agents spécialisés par faculté pour des réponses plus ciblées
- **Rate limiting** — protection contre le flood (configurable, 60 req/min par défaut)
- **Métriques** — suivi des questions, temps de réponse, questions hors sujet

---

## Architecture

### Graphe LangGraph (pattern ReAct)

```text
Entrée utilisateur
       │
   [router]  ← route_and_store()
       │
       ├─ "agent"              → [agent] (call_model + outils bindés)
       │                              │
       │                    ┌─────────┴──────────┐
       │                    ▼                    ▼
       │               [tools]               [END]
       │                    │
       │                    └──────────→ [agent] …
       │
       ├─ "reject_query"       → [reject_query] → [END]
       └─ "handle_special_case"→ [handle_special_case] → [END]
```

### Décisions de routage

| Cas détecté | Destination |
| --- | --- |
| Abréviation seule (FA, FAST…) | `agent` |
| Salutation (GREETING / BOTH) | `agent` |
| Au revoir (FAREWELL) | `handle_special_case` |
| Remerciement (THANKS) | `handle_special_case` |
| Frustration / confusion / répétition | `handle_special_case` |
| Profil CANDIDAT_MASTER / DOCTORAT / ETRANGER | `agent` |
| Question pertinente UAM | `agent` |
| Hors sujet | `reject_query` |

### Modules principaux

| Fichier | Rôle |
| --- | --- |
| `agent_uam.py` | Point d'entrée principal — réexporte tout |
| `agent_graph.py` | Construction du `StateGraph` LangGraph |
| `agent_state.py` | `AgentState` TypedDict |
| `graph_nodes.py` | Nœuds du graphe (routage, appel LLM, cas spéciaux) |
| `tools/` | Package : 49 outils `@tool` + vectorstore FAISS |
| `tool_node.py` | `ToolNode` personnalisé (avec fallback) |
| `prompts.py` | Templates de prompts système |
| `config.py` / `app_config.py` | Configuration centralisée via variables d'env |
| `llm_utils.py` | Initialisation LLM et embeddings |
| `document_loader.py` | Chargement PDF/TXT + indexation FAISS |
| `memory.py` | `UserMemory` — SQLite (préférences long terme) |
| `uam_structures.py` | Données statiques des facultés/écoles/instituts |
| `multi_agents.py` | Système multi-agents par faculté |
| `app_streamlit.py` | Interface web Streamlit |
| `chatbot.py` | Interface console (CLI) |
| `metrics.py` | Enregistrement et résumé des métriques |
| `export_utils.py` | Export PDF/JSON des conversations |

---

## Installation

### Prérequis

- Python 3.10+
- Une clé API (OpenRouter recommandé, voir [ci-dessous](#providers-llm-supportés))

### Étapes

```bash
# 1. Cloner le dépôt
git clone <url-du-repo>
cd agent-uam

# 2. Utiliser le script de setup (crée le venv et installe les dépendances)
./setup.sh

# ou manuellement :
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Documents UAM

Placez vos fichiers PDF, TXT ou Markdown dans `documents_uam/`. Six documents sont déjà inclus.

---

## Configuration

Créez un fichier `.env` à la racine :

```env
# Provider actif (OpenRouter — recommandé, accès à 300+ modèles)
OPENROUTER_API_KEY=sk-or-v1-...

# Alternatives
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Variables d'environnement optionnelles

| Variable | Défaut | Description |
| --- | --- | --- |
| `UAM_LLM_PROVIDER` | `openrouter` | Provider LLM |
| `UAM_LLM_MODEL` | selon provider | Nom du modèle |
| `UAM_LLM_TEMPERATURE` | `0.3` | Température |
| `UAM_DOCUMENTS_DIR` | `./documents_uam` | Dossier des documents |
| `UAM_VECTORSTORE_DIR` | `./vectorstore` | Cache FAISS |
| `UAM_CHUNK_SIZE` | `1000` | Taille des chunks |
| `UAM_SIMILARITY_K` | `4` | Nombre de résultats par recherche |
| `UAM_MAX_TOOL_ITERATIONS` | `5` | Limite de la boucle outils |
| `UAM_RATE_LIMIT` | `60` | Requêtes max par minute |

---

## Utilisation

### Site institutionnel avec assistant intégré (recommandé)

```bash
./run_api.sh
# Ouvrir http://localhost:8000
```

Site web de l'université — facultés, 135 formations, procédure d'inscription et frais —
avec l'assistant accessible en permanence depuis un panneau latéral. Les contenus sont
tirés de `uam_structures.py` et de `database/scolarite_uam.db`.

| Route | Rôle |
|---|---|
| `GET /` | le site |
| `GET /#assistant` | le site, assistant déjà ouvert |
| `POST /api/chat` | `{question, session_id}` → `{response, sources, elapsed_ms}` |
| `POST /api/chat/stream` | même chose en Server-Sent Events (réponse affichée au fil de l'eau) |
| `GET /health` | état du service |
| `/webhook/whatsapp` | canal WhatsApp — voir [WHATSAPP.md](WHATSAPP.md) |

Le modèle d'embeddings et l'index FAISS sont chargés une seule fois au démarrage
(5 à 15 s), puis partagés par toutes les requêtes.

### Interface Streamlit (outil de travail)

```bash
source venv/bin/activate
streamlit run app_streamlit.py
# Ouvrir http://localhost:8501
```

Ou via le script :

```bash
./run_streamlit.sh
```

### WhatsApp

L'agent répond aussi sur WhatsApp via l'API Business Cloud de Meta.
Mise en route pas à pas : [WHATSAPP.md](WHATSAPP.md).

### Mode console (CLI)

```bash
source venv/bin/activate
python agent_uam.py
```

### Exemples de questions

```text
Quelles sont les facultés de l'UAM ?
Comment s'inscrire à l'UAM ?
Quelles formations sont disponibles à la FAST ?
Quels sont les frais de scolarité pour un master ?
Je veux faire une thèse à l'UAM, comment procéder ?
Comment obtenir une attestation de scolarité ?
Quelles sont les conditions pour les étudiants étrangers ?
```

---

## Évaluation automatique

Le projet inclut un pipeline d'évaluation complet qui compare trois approches pour quantifier la contribution de chaque composant (retrieval, orchestration agentique).

### Approches comparées

| Approche | Description |
| --- | --- |
| **LLM seul** | Génération directe à partir des connaissances du modèle, sans retrieval ni outils |
| **RAG séquentielle** | Retrieve top-4 documents → generate avec contexte, sans graphe ni outils spécialisés |
| **Agent LangGraph** | Graphe d'états + ReAct + 45+ outils `@tool` + routage intelligent + mémoire de session |

### Métriques calculées

| Métrique | Description | Seuil acceptable |
| --- | --- | --- |
| **Précision / Rappel / F1** | Classification pertinent / hors-sujet | > 0.80 |
| **Exactitude** | Taux de bonne classification | > 0.85 |
| **Keyword Recall** | Proportion de mots-clés attendus présents dans la réponse | > 0.70 |
| **ROUGE-1 / ROUGE-2 / ROUGE-L** | Qualité du texte généré par rapport au ground truth | > 0.40 / 0.20 / 0.35 |
| **Faithfulness** (RAGAS) | Ancrage de la réponse dans les documents récupérés | > 0.70 |
| **Answer Relevancy** (RAGAS) | Adéquation de la réponse à la question posée | > 0.70 |
| **Latence P50 / P90** | Temps de réponse médian et percentile 90 | < 5 000 / 10 000 ms |

> RAGAS n'est pas calculé pour le mode LLM seul (Faithfulness et Answer Relevancy présupposent un contexte récupéré).

### Dataset d'évaluation

- **98 questions** couvrant 15 catégories (inscriptions, formations, facultés, frais, contacts, hors-sujet…)
- 74 questions pertinentes UAM — 24 questions hors-sujet
- Chaque question inclut : `ground_truth`, `category`, `expected_relevant`, `mots_cles`

### Commandes

```bash
# Évaluation complète de l'agent LangGraph
python evaluate.py

# Test rapide sur 10 questions
python evaluate.py --limit 10

# Sans RAGAS (plus rapide)
python evaluate.py --no-ragas

# Mode baseline RAG séquentielle
python evaluate.py --baseline

# Mode LLM seul
python evaluate.py --llm-only

# Comparaison des 3 approches en une commande (génère COMPARISON_REPORT.md)
./run_comparison.sh

# Limiter le nombre d'exemples RAGAS (défaut : 50)
./run_comparison.sh --ragas-limit 30

# Exécution rapide pour tests
./run_comparison.sh --limit 10 --no-ragas
```

### Options de `evaluate.py`

| Option | Défaut | Description |
| --- | --- | --- |
| `--dataset` | `dataset_evaluation.csv` | Chemin vers le CSV de test |
| `--limit N` | — | Limiter à N questions |
| `--no-ragas` | — | Désactiver le calcul RAGAS |
| `--baseline` | — | Mode baseline RAG séquentielle |
| `--llm-only` | — | Mode LLM seul (sans retrieval) |
| `--ragas-limit N` | `50` | Nb max d'exemples pour RAGAS |
| `--ragas-workers N` | `1` | Workers parallèles RAGAS (1 = séquentiel) |
| `--output` | `./evaluation_results` | Dossier de sortie |

### Sorties générées

```text
evaluation_results/
├── evaluation_detail_YYYYMMDD_HHMMSS.csv    # Une ligne par question
├── evaluation_summary_YYYYMMDD_HHMMSS.csv   # Résumé des métriques (pour mémoire)
├── evaluation_complete_YYYYMMDD_HHMMSS.json # Archive complète
└── tableau_latex_YYYYMMDD_HHMMSS.tex        # Tableaux LaTeX prêts à l'emploi

COMPARISON_REPORT.md                          # Rapport comparatif des 3 approches
```

---

## Structure du projet

```text
agent-uam/
├── agent_uam.py              # Module principal (point d'entrée + réexports)
├── agent_graph.py            # Graphe LangGraph
├── agent_state.py            # AgentState TypedDict
├── graph_nodes.py            # Nœuds du graphe
├── tools/                    # Package : outils @tool (49)
├── tool_node.py              # ToolNode personnalisé
├── prompts.py                # Templates de prompts
├── app_config.py             # Configuration centralisée
├── llm_utils.py              # Initialisation LLM / embeddings
├── document_loader.py        # Chargement + indexation FAISS
├── memory.py                 # Mémoire utilisateur (SQLite)
├── uam_structures.py         # Données statiques UAM
├── multi_agents.py           # Système multi-agents
├── app_streamlit.py          # Interface web Streamlit
├── chatbot.py                # Interface console CLI
├── metrics.py                # Métriques d'utilisation
├── export_utils.py           # Export PDF / JSON
├── database_connector.py     # Connecteur base de données optionnel
├── seed_database.py          # Script de peuplement de database/scolarite_uam.db
│
├── evaluate.py               # Évaluation automatisée (3 modes)
├── baseline_rag.py           # Baseline RAG séquentielle (retrieve → generate)
├── llm_only.py               # Baseline LLM seul (sans retrieval)
├── context_tracker.py        # Tracker des contextes RAG utilisés par l'agent
├── dataset_evaluation.csv    # Dataset d'évaluation (98 questions)
├── human_eval.py             # Évaluation humaine
│
├── logger_config.py          # Logging structuré
├── utils.py                  # Utilitaires (validation, sanitization, retry)
│
├── documents_uam/            # Documents source de la base de connaissances
├── evaluation/               # Scripts et données d'évaluation complémentaires
├── tests/                    # Tests unitaires
│
├── setup.sh                  # Script d'installation
├── run_streamlit.sh          # Lancement Streamlit
├── run_comparison.sh         # Comparaison des 3 approches d'évaluation
├── requirements.txt          # Dépendances Python
├── .env                      # Clés API (non versionné)
└── CLAUDE.md                 # Instructions pour Claude Code
```

Dossiers générés à l'exécution (non versionnés) :

```text
vectorstore/      # Index FAISS
logs/             # Journaux applicatifs
exports/          # Conversations exportées
*.db              # Bases SQLite (mémoire, métriques)
```

---

## Providers LLM supportés

| Provider | Clé env | Recommandé | Notes |
| --- | --- | --- | --- |
| **OpenRouter** | `OPENROUTER_API_KEY` | Oui | Accès à 300+ modèles, modèles gratuits disponibles |
| **Groq** | `GROQ_API_KEY` | Oui | Très rapide, Llama 3.3 70B |
| **OpenAI** | `OPENAI_API_KEY` | — | GPT-4o |
| **Anthropic** | `ANTHROPIC_API_KEY` | — | Claude Sonnet |
| **Ollama** | aucune | — | Exécution locale |

### Modèles OpenRouter disponibles dans l'interface

| Affichage | ID modèle |
| --- | --- |
| GPT-4o mini | `openai/gpt-4o-mini` |
| Claude Sonnet 3.7 | `anthropic/claude-3.7-sonnet` |
| Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` |
| Gemma 3 27B (gratuit) | `google/gemma-3-27b-it:free` |
| Llama 3.1 8B (gratuit) | `meta-llama/llama-3.1-8b-instruct:free` |
| Mistral 7B (gratuit) | `mistralai/mistral-7b-instruct:free` |
| DeepSeek R1 (gratuit) | `deepseek/deepseek-r1:free` |

---

## Dépannage

### "Aucun document trouvé"

Vérifiez que `documents_uam/` contient des fichiers PDF ou TXT.

### "Provider non supporté" / import error

Installez le package manquant :

```bash
pip install langchain-groq        # Groq
pip install langchain-openai      # OpenAI
pip install langchain-anthropic   # Claude
pip install langchain-community   # Ollama
```

### "API key not found"

Vérifiez que `.env` existe à la racine et contient la clé correspondant au provider configuré.

### Erreur FAISS sur Windows

```bash
conda install -c pytorch faiss-cpu
```

### L'agent répète toujours la même réponse

Vérifiez que `UAM_MAX_TOOL_ITERATIONS` n'est pas trop bas (défaut : 5).

---

## Licence

Développé pour l'Université Abdou Moumouni de Niamey (UAM) — Niger.

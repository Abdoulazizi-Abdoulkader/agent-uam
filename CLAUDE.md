# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commandes principales

```bash
# Lancer l'interface web Streamlit (recommandé)
streamlit run app_streamlit.py

# Lancer en mode console (CLI)
python agent_uam.py

# Vérifier l'installation et les dépendances
python test_setup.py

# Installer les dépendances
pip install -r requirements.txt

# Activer l'environnement virtuel
source venv/bin/activate
```

## Configuration requise

Créer un fichier `.env` à la racine avec au moins une clé API :

```env
GROQ_API_KEY=gsk_...          # Recommandé (Llama 3.3 70B)
OPENAI_API_KEY=sk-...          # Alternatif
ANTHROPIC_API_KEY=sk-ant-...   # Alternatif
OPENROUTER_API_KEY=sk-or-v1-...  # Alternatif (accès multi-modèles)
```

Le provider par défaut est Groq (`LLMProvider.LLAMA_GROQ`). Pour changer, modifier `PROVIDER` dans `agent_uam.py` (`__main__`) ou via la variable d'env `UAM_LLM_PROVIDER`.

Les documents UAM (PDF/TXT) doivent être placés dans `documents_uam/`.

## Architecture

### Flux d'exécution

```
Utilisateur
    ↓
chatbot.py (run_chatbot) — point d'entrée CLI
    ↓
agent_graph.py (create_agent_graph) — construit le graphe LangGraph
    ↓
graph_nodes.py — nœuds du graphe :
  • route_question → détermine si la question est pertinente (UAM) ou hors sujet
  • call_model → appelle le LLM avec outils bindés
  • should_continue → décide : appel outils ou fin
  • reject_query → répond poliment aux questions hors sujet
    ↓
tool_node.py (ToolNode) — exécute les outils appelés par le LLM
    ↓
tools.py — ~30 outils @tool pour recherche sémantique FAISS, infos facultés, frais, etc.
```

### Modules clés

| Fichier | Rôle |
|---|---|
| `agent_uam.py` | Module principal — réexporte tout, point d'entrée `__main__` |
| `agent_graph.py` | Construction du `StateGraph` LangGraph avec `MemorySaver` |
| `agent_state.py` | `AgentState` TypedDict avec `Annotated[Sequence[BaseMessage], add]` |
| `graph_nodes.py` | Nœuds du graphe (routage, appel LLM, rejet) |
| `tools.py` | Tous les outils `@tool` + gestion du vectorstore FAISS global |
| `tool_node.py` | `ToolNode` personnalisé pour l'exécution des outils |
| `config.py` | Enum `LLMProvider` (OPENAI, CLAUDE, LLAMA_GROQ, LLAMA_OLLAMA, OPENROUTER) |
| `llm_utils.py` | Initialisation du LLM et des embeddings selon le provider |
| `document_loader.py` | Chargement PDF/TXT + indexation FAISS |
| `memory.py` | `UserMemory` — persistance des préférences utilisateur (JSON + SQLite) |
| `uam_structures.py` | `UAM_STRUCTURES` dict statique des facultés/écoles/instituts UAM |
| `app_config.py` | Configuration centralisée via variables d'env (`get_config()`) |
| `multi_agents.py` | Système multi-agents — un agent spécialisé par faculté UAM |
| `app_streamlit.py` | Interface web Streamlit |
| `prompts.py` | Templates de prompts système (`build_tool_system_prompt`, etc.) |
| `logger_config.py` | Logging structuré (logs/ avec rotation par date) |

### Pattern LangGraph utilisé

Le graphe suit le pattern ReAct avec tools :
1. `route_question` → entrée conditionnelle vers `agent`, `reject_query`, ou `handle_special_case`
2. `agent` (call_model) → LLM avec outils bindés via `llm.bind_tools(tools)`
3. `should_continue` → si `tool_calls` présents → `tools`, sinon → `END`
4. `tools` (ToolNode) → exécution des outils → retour à `agent`
5. `handle_special_case` → répond directement (sans LLM) aux cas : adieux, remerciements, frustration, confusion
6. `reject_query` → répond poliment aux questions hors sujet
7. Limite anti-boucle : `max_tool_iterations = 5` (configurable via `UAM_MAX_TOOL_ITERATIONS`)

### Cas conversationnels gérés par `route_question`

| Cas détecté | Destination | Outils utilisés |
|---|---|---|
| Abréviation seule (FA, FAST…) | `agent` | `get_faculty_info` |
| Salutation simple | `agent` | `detect_greeting` |
| FAREWELL (au revoir, bye…) | `handle_special_case` | — |
| THANKS (merci, parfait…) | `handle_special_case` | — |
| Frustration / confusion | `handle_special_case` | `detect_frustration_or_confusion` |
| Profil CANDIDAT_MASTER | `agent` | `search_external_student_master` |
| Profil CANDIDAT_DOCTORAT | `agent` | `search_phd_admission` |
| Profil ETUDIANT_ETRANGER | `agent` | `search_foreign_student_procedures` |
| Question UAM pertinente | `agent` | outils spécialisés |
| Hors sujet | `reject_query` | — |

### Profils utilisateur détectés automatiquement

`detect_user_profile` classe chaque message en : `BACHELIER`, `ETUDIANT_UAM`, `ETUDIANT_EXTERNE`, `ETUDIANT_ETRANGER`, `CANDIDAT_MASTER`, `CANDIDAT_DOCTORAT`, `PROFESSIONNEL`, `PARENT`, `INCONNU`. Le profil enrichit le prompt système dans `call_model` avec les outils prioritaires à utiliser.

La persistance de session est assurée par `MemorySaver` avec un `thread_id` UUID unique par session.

### Vectorstore FAISS

Le vectorstore est initialisé une fois dans `document_loader.py` et stocké comme état global dans `tools.py` via `set_vectorstore()`. Les embeddings utilisent `HuggingFaceEmbeddings` (modèle `paraphrase-multilingual-MiniLM-L12-v2` ou similaire). Le vectorstore est persisté dans `./vectorstore/`.

### Variables d'environnement de configuration

| Variable | Défaut | Description |
|---|---|---|
| `UAM_LLM_PROVIDER` | `llama_groq` | Provider LLM |
| `UAM_LLM_MODEL` | selon provider | Nom du modèle |
| `UAM_LLM_TEMPERATURE` | `0.3` | Température |
| `UAM_DOCUMENTS_DIR` | `./documents_uam` | Dossier documents |
| `UAM_VECTORSTORE_DIR` | `./vectorstore` | Persistance FAISS |
| `UAM_CHUNK_SIZE` | `1000` | Taille des chunks |
| `UAM_SIMILARITY_K` | `4` | Nb résultats similarité |
| `UAM_MAX_TOOL_ITERATIONS` | `5` | Limite boucle outils |
| `UAM_DB_TYPE` | None | Type BDD (postgresql/mysql/mongodb) |

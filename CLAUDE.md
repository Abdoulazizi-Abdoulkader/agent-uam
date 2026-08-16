# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commandes principales

```bash
# Lancer le site institutionnel + assistant + webhook WhatsApp (recommandé)
./run_api.sh                    # http://localhost:8000

# Lancer l'interface Streamlit (outil de travail)
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

Créer un fichier `.env` à la racine avec la clé API OpenRouter :

```env
OPENROUTER_API_KEY=sk-or-v1-...  # Requis — seul provider actif (accès multi-modèles)
```

Seul OpenRouter est actif (`llm_utils.initialize_llm`). Le LLM appelle l'API
OpenRouter via `ChatOpenAI` (`base_url=https://openrouter.ai/api/v1`). Modèle par
défaut : `openai/gpt-4o-mini` (override via `UAM_LLM_MODEL`). L'enum `LLMProvider`
conserve d'autres valeurs (OPENAI, CLAUDE, LLAMA_GROQ…) mais elles sont ignorées :
le paramètre `provider` n'a plus d'effet, tout passe par OpenRouter. Les embeddings
sont calculés localement via HuggingFace (`paraphrase-multilingual-MiniLM-L12-v2`).

Les documents UAM (PDF/TXT) doivent être placés dans `documents_uam/`.

## Architecture

### Flux d'exécution

```text
Utilisateur
    ↓
3 points d'entrée :
  • api/main.py (FastAPI)   — site web + webhook WhatsApp  ← recommandé
  • app_streamlit.py        — interface Streamlit
  • chatbot.py (run_chatbot)— CLI
    ↓
api/agent_service.py — pour le web et WhatsApp : construit l'agent une seule fois
                       (get_agent) et expose answer(question, session_id)
    ↓
agent_graph.py (create_agent_graph) — construit le graphe LangGraph
    ↓
graph_nodes.py — nœuds du graphe :
  • route_and_store → route le message (agent / reject_query / handle_special_case)
                       et mémorise routing_hint, routing_context et user_profile
  • call_model → appelle le LLM avec outils bindés
  • should_continue → décide : appel outils ou fin
  • handle_special_case → répond sans LLM (adieux, remerciements, abréviation seule…)
  • reject_query → répond poliment aux questions hors sujet
    ↓
tool_node.py (ToolNode) — exécute les outils appelés par le LLM
    ↓
tools.py — 49 outils @tool pour recherche sémantique FAISS, infos facultés, frais, etc.
           (45 toujours actifs + 4 conditionnels à la base de données — voir audit_outils.md)
```

### Modules clés

| Fichier | Rôle |
|---|---|
| `agent_uam.py` | Module principal — réexporte tout, point d'entrée `__main__` |
| `agent_graph.py` | Construction du `StateGraph` LangGraph avec `MemorySaver` |
| `agent_state.py` | `AgentState` TypedDict avec `Annotated[Sequence[BaseMessage], add]` |
| `graph_nodes.py` | Nœuds du graphe : `route_and_store`, `call_model`, `should_continue`, `handle_special_case`, `reject_query` |
| `tools.py` | Tous les outils `@tool` + gestion du vectorstore FAISS global |
| `tool_node.py` | `ToolNode` (wrapper de `langgraph.prebuilt.ToolNode` + incrément `tool_iterations`) |
| `llm_utils.py` | Initialisation du LLM (OpenRouter via `ChatOpenAI`) et des embeddings HuggingFace locaux |
| `document_loader.py` | Chargement PDF/TXT + indexation FAISS |
| `memory.py` | `UserMemory` — persistance des préférences utilisateur (JSON + SQLite) |
| `uam_structures.py` | `UAM_STRUCTURES` dict statique des facultés/écoles/instituts UAM |
| `app_config.py` | Configuration centralisée via variables d'env (`get_config()`) |
| `multi_agents.py` | Système multi-agents — un agent spécialisé par faculté UAM |
| `app_streamlit.py` | Interface web Streamlit |
| `api/agent_service.py` | **Couche de service partagée** — `get_agent()` (singleton) et `answer(question, session_id)`. Toute nouvelle interface doit passer par là plutôt que réimplémenter l'invocation du graphe |
| `api/main.py` | Serveur FastAPI — site (`/`), API de chat (`/api/chat`), webhook WhatsApp |
| `api/site_data.py` | Contenu du site : fusionne `uam_structures.py` et `database/scolarite_uam.db` |
| `api/whatsapp.py` | Canal WhatsApp Cloud API — signature, extraction, formatage, envoi |
| `web/` | Site : `templates/index.html`, `static/style.css`, `static/chat.js` (aucune ressource externe : le site s'affiche sans réseau) |
| `prompts.py` | Templates de prompts système (`build_tool_system_prompt`, etc.) |
| `logger_config.py` | Logging structuré (logs/ avec rotation par date) |

### Pattern LangGraph utilisé

Le graphe suit le pattern ReAct avec tools :
1. `route_and_store` (nœud d'entrée `router`) → arête conditionnelle vers `agent`, `reject_query`, ou `handle_special_case` (selon `routing_hint`)
2. `agent` (call_model) → LLM avec outils bindés via `llm.bind_tools(tools)`
3. `should_continue` → si `tool_calls` présents → `tools`, sinon → `END`
4. `tools` (ToolNode) → exécution des outils → retour à `agent`
5. `handle_special_case` → répond directement (sans LLM) aux cas : adieux, remerciements, frustration, confusion
6. `reject_query` → répond poliment aux questions hors sujet
7. Limite anti-boucle : `max_tool_iterations = 5` (configurable via `UAM_MAX_TOOL_ITERATIONS`)

### ⚠️ Retours des nœuds : ne jamais renvoyer `{**state}`

`AgentState.messages` porte le réducteur `add` (`operator.add`) : LangGraph **concatène**
la valeur retournée à l'existant au lieu de la remplacer. Un nœud qui renvoie
`{**state, "autre_champ": ...}` réexpédie donc tout l'historique, qui **double à chaque
passage** — mesuré en session réelle : 1 → 2 → 4 → … → 83 608 messages, avec pour
conséquences des réponses à 75 s et des erreurs 400 (`messages with role 'tool' must be
a response to a preceeding message with 'tool_calls'`) masquées par le repli de
`call_model`.

**Règle : un nœud ne retourne que les champs qu'il modifie.** LangGraph fusionne le reste
de l'état tout seul. N'inclure `messages` que pour *ajouter* des messages.

`_compress_history` ([graph_nodes.py](graph_nodes.py)) retire par ailleurs les
`ToolMessage` et les `AIMessage` porteurs de `tool_calls` des **tours passés** (ils ne
servent qu'au tour qui les a produits, et pèsent ~1 500 tokens chacun). Les deux types
sont retirés ensemble : l'API exige qu'un message annonçant des `tool_calls` soit suivi
de leurs résultats.

### Cas conversationnels gérés par `route_and_store`

| Cas détecté | Destination | Outils utilisés |
|---|---|---|
| Abréviation seule (FA, FAST…) | `handle_special_case` | — (réponse directe depuis `UAM_STRUCTURES`) |
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

La persistance de session est assurée par `MemorySaver` avec un `thread_id` unique par session : UUID en Streamlit et sur le web (conservé dans `localStorage`), `whatsapp:<numéro>` sur WhatsApp. `MemorySaver` étant en mémoire, redémarrer le processus efface l'historique conversationnel — à remplacer par un `SqliteSaver` pour un service durable.

Le `user_id` de session est propagé aux outils via un `contextvars.ContextVar` (`tools.set_session_user_id`) et non un `threading.local` : le `ToolNode` exécute les outils dans un pool de threads, qui héritent du contexte mais pas du stockage par thread.

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
| `WHATSAPP_VERIFY_TOKEN` | None | Vérification du webhook Meta (webhook fermé si absent) |
| `WHATSAPP_ACCESS_TOKEN` | None | Token de l'app Meta (temporaire : 24 h) |
| `WHATSAPP_PHONE_NUMBER_ID` | None | Identifiant du numéro expéditeur |
| `WHATSAPP_APP_SECRET` | None | Signature des webhooks (vérification désactivée si absent) |

Voir `.env.example` pour un fichier prêt à compléter et `WHATSAPP.md` pour la mise en route du canal WhatsApp.

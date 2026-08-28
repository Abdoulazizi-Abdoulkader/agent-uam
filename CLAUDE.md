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

# Reconstruire la base de données scolarité (nécessaire après un clone : database/scolarite_uam.db
# n'est pas versionnée, *.db est dans .gitignore ; sans elle, search_student_record et
# search_statistics_uam ne renvoient aucun résultat, faute de tables). Dans cet ordre :
python database/simulation_scolarite.py   # crée le schéma et 50 étudiants simulés
python seed_database.py                   # ajoute frais_formations, statistiques_composantes et 8 étudiants de test (58 étudiants au total)

# Installer les dépendances
pip install -r requirements.txt

# Activer l'environnement virtuel
source venv/bin/activate

venv/bin/python -m pytest tests/ -q   # Lancer la suite de tests
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
tools/ — 49 outils @tool pour recherche sémantique FAISS, infos facultés, frais, etc.
         (49 outils au total : 45 toujours actifs, 2 conditionnés à la base de
         données (search_student_record, search_statistics_uam), et 2 réservés
         aux backends documentaires — search_latest_news (BUG-01) et
         get_schedules_from_db (BUG-11), tous deux inertes sur SQLite faute de
         table. En configuration réelle (SQLite) : 47 outils exposés.)
```

### Modules clés

| Fichier | Rôle |
|---|---|
| `agent_uam.py` | Module principal — réexporte tout, point d'entrée `__main__` |
| `agent_graph.py` | Construction du `StateGraph` LangGraph avec `MemorySaver` |
| `agent_state.py` | `AgentState` TypedDict avec `Annotated[Sequence[BaseMessage], add]` |
| `graph_nodes.py` | Nœuds du graphe : `route_and_store`, `call_model`, `should_continue`, `handle_special_case`, `reject_query` |
| `tools/` | Package : tous les outils `@tool` + gestion du vectorstore FAISS global |
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

### Accès au dossier étudiant : second facteur obligatoire (SEC-01)

`search_student_record` **n'accepte pas le matricule seul**. `date_naissance` est
un argument obligatoire, vérifié contre `etudiants.date_naissance` par
`database_connector.verify_student_birthdate`, qui renvoie un booléen et jamais
la date elle-même — elle ne circule donc pas dans les dictionnaires que les
outils formatent.

Trois invariants à ne pas casser en modifiant cet outil :

- **Pas d'oracle d'énumération** : un matricule inconnu et une date incorrecte
  renvoient le *même* message, au caractère près, sans écho du matricule. Le
  format des matricules est prévisible (`UAM` + 6 chiffres) : un message qui
  distinguerait les deux cas permettrait de découvrir par balayage quels
  dossiers existent.
- **Fail-closed** : erreur de base, date illisible, dossier sans date de
  naissance → refus, jamais accès.
- **Non-divulgation** : la date de naissance n'apparaît dans aucune réponse.

Ce n'est **pas** une authentification (pas de session étudiant dans cette
application) : c'est la barrière que le schéma permet de poser pour la
démonstration sur base simulée. La mise en production avec les vraies données
de scolarité demande une authentification réelle. Preuve :
`tests/test_sec_01_dossier_etudiant.py`.

### Routage hors sujet : deux étages de mots-clés

`check_question_relevance` (`tools/conversation.py`) sépare `keywords_forts`
(mots sans autre sens courant — « faculté », « inscription », « semestre »… —
qui déclenchent `PERTINENT` seuls) de `keywords_faibles` (mots génériques du
français — « cours », « service », « dossier », « note », « moyenne »,
« résultat », « bac »… — qui ne déclenchent `PERTINENT` que si la phrase ne
porte aucun marqueur de `_DOMAINE_CONCURRENT_RE`).

Deux points de vigilance :

- Le garde-fou de domaine **désarme l'étage faible, il ne rejette pas** : les
  mécanismes en aval (`uam_geo_patterns`, `external_patterns`,
  `education_phrases`) peuvent toujours rattraper la phrase. Ne jamais le
  transformer en rejet direct, ni déplacer ces marqueurs dans `_OFF_TOPIC_RE`,
  qui court-circuite en tête de fonction (c'est ce court-circuit qui a causé
  BUG-07).
- `tests/test_routage_hors_sujet.py` (précision) et
  `tests/test_keywords_uam_corpus.py` (rappel, 55 vraies questions) doivent
  rester verts **ensemble** : c'est la seule preuve qu'un resserrement
  n'éconduit pas de vraies questions.

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

La persistance de session est assurée par le checkpointer configuré via `UAM_CHECKPOINTER` (`agent_graph.py:_build_checkpointer`), avec un `thread_id` unique par session : UUID en Streamlit et sur le web (conservé dans `localStorage`), `whatsapp:<numéro>` sur WhatsApp. Par défaut c'est un `SqliteSaver` (`./database/checkpoints.db`, configurable via `UAM_CHECKPOINT_DB`) : l'historique conversationnel survit au redémarrage du processus. `UAM_CHECKPOINTER=memory` bascule sur `MemorySaver` (en mémoire, effacé au redémarrage) si besoin.

Le `user_id` de session est propagé aux outils via un `contextvars.ContextVar` (`tools.set_session_user_id`) et non un `threading.local` : le `ToolNode` exécute les outils dans un pool de threads, qui héritent du contexte mais pas du stockage par thread.

### Vectorstore FAISS

Le vectorstore est initialisé une fois dans `document_loader.py` et stocké comme état global dans `tools/_vectorstore.py` via `set_vectorstore()`. Les embeddings utilisent `HuggingFaceEmbeddings` (modèle `paraphrase-multilingual-MiniLM-L12-v2` ou similaire). Le vectorstore est persisté dans `./vectorstore/`.

### Variables d'environnement de configuration

| Variable | Défaut | Description |
|---|---|---|
| `UAM_LLM_PROVIDER` | `openrouter` | Provider LLM |
| `UAM_LLM_MODEL` | selon provider | Nom du modèle |
| `UAM_LLM_TEMPERATURE` | `0.3` | Température |
| `UAM_DOCUMENTS_DIR` | `./documents_uam` | Dossier documents |
| `UAM_VECTORSTORE_DIR` | `./vectorstore` | Persistance FAISS |
| `UAM_CHUNK_SIZE` | `1000` | Taille des chunks |
| `UAM_SIMILARITY_K` | `4` | Nb résultats similarité |
| `UAM_MAX_TOOL_ITERATIONS` | `5` | Limite boucle outils |
| `UAM_DB_TYPE` | None | Type BDD (postgresql/mysql/mongodb) |
| `UAM_CHECKPOINTER` | `sqlite` | Persistance des sessions : `sqlite` (survit au redémarrage) ou `memory` |
| `UAM_CHECKPOINT_DB` | `./database/checkpoints.db` | Chemin du fichier SQLite des checkpoints |
| `WHATSAPP_VERIFY_TOKEN` | None | Vérification du webhook Meta (webhook fermé si absent) |
| `WHATSAPP_ACCESS_TOKEN` | None | Token de l'app Meta (temporaire : 24 h) |
| `WHATSAPP_PHONE_NUMBER_ID` | None | Identifiant du numéro expéditeur |
| `WHATSAPP_APP_SECRET` | None | Signature des webhooks (vérification désactivée si absent) |

Voir `.env.example` pour un fichier prêt à compléter et `WHATSAPP.md` pour la mise en route du canal WhatsApp.

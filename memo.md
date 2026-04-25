# 📚 Mémoire Technique - Agent Conversationnel UAM

## 🎯 Vue d'Ensemble

### Principe du Projet

L'**Agent Conversationnel UAM** est un système d'intelligence artificielle conversationnelle conçu pour l'Université Abdou Moumouni de Niamey (UAM). Il permet aux étudiants, enseignants et visiteurs d'obtenir des informations précises sur l'université via une interface conversationnelle naturelle.

### Objectifs Principaux

1. **Répondre aux questions** sur les formations, structures, horaires, frais, etc.
2. **Guider les utilisateurs** dans leurs démarches administratives
3. **Fournir des informations à jour** depuis une base de connaissances structurée
4. **Maintenir le contexte** de conversation pour des interactions fluides
5. **Personnaliser les réponses** selon les préférences utilisateur

---

## 🏗️ Architecture Technique

### Architecture Générale

Le projet suit une **architecture modulaire** basée sur **LangGraph** (graphes d'état) et **LangChain** (orchestration LLM) :

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACE UTILISATEUR                    │
│  ┌──────────────┐              ┌──────────────┐             │
│  │  Streamlit   │              │   Console    │             │
│  │  (Web UI)    │              │   (CLI)      │             │
│  └──────┬───────┘              └──────┬───────┘             │
└─────────┼─────────────────────────────┼─────────────────────┘
          │                             │
          └─────────────┬───────────────┘
                        │
          ┌─────────────▼───────────────┐
          │     AGENT GRAPH (LangGraph)  │
          │  ┌────────────────────────┐  │
          │  │  StateGraph Workflow   │  │
          │  │  - route_question      │  │
          │  │  - call_model          │  │
          │  │  - tools               │  │
          │  │  - generate_response   │  │
          │  └────────────────────────┘  │
          └─────────────┬─────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│   LLM        │ │   TOOLS     │ │  MEMORY     │
│  (Groq/      │ │  (Search,   │ │  (Session,  │
│   OpenAI/    │ │   DB, etc.) │ │   User)     │
│   Claude)    │ │             │ │             │
└───────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
          ┌─────────────▼───────────────┐
          │    SOURCES DE DONNÉES        │
          │  ┌──────────┐  ┌──────────┐  │
          │  │   RAG    │  │   SQL    │  │
          │  │ (FAISS)  │  │ (SQLite) │  │
          │  └──────────┘  └──────────┘  │
          └──────────────────────────────┘
```

### Composants Principaux

#### 1. **Interface Utilisateur** (`app_streamlit.py`, `chatbot.py`)
- **Streamlit** : Interface web moderne avec chat en temps réel
- **Console** : Interface CLI simple pour tests et scripts
- Gestion des sessions utilisateur avec UUID unique

#### 2. **Graphe d'Agent** (`agent_graph.py`)
- **StateGraph** : Structure le workflow de l'agent
- **Nœuds** : Points de traitement (routage, modèle, outils, réponse)
- **Arêtes conditionnelles** : Décisions dynamiques selon l'état
- **MemorySaver** : Persistance de l'état entre les interactions

#### 3. **État de l'Agent** (`agent_state.py`)
```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]  # Historique conversationnel
    question: str                                      # Question actuelle
    is_relevant: bool                                  # Pertinence de la question
    context: str                                       # Contexte récupéré
    response: str                                      # Réponse générée
    need_clarification: bool                           # Besoin de clarification
    user_id: str                                       # ID utilisateur
    user_preferences: Dict[str, Any]                   # Préférences utilisateur
```

#### 4. **Nœuds du Graphe** (`graph_nodes.py`)
- **`route_question`** : Détecte la pertinence et route vers l'agent ou rejet
- **`call_model`** : Appelle le LLM avec les outils disponibles
- **`should_continue`** : Détermine si des outils doivent être appelés
- **`search_knowledge`** : Recherche dans la base de connaissances RAG
- **`generate_response`** : Génère la réponse finale
- **`reject_query`** : Rejette les questions hors-sujet

#### 5. **Outils** (`tools.py`)
Collection de 20+ outils spécialisés :
- **`search_uam_knowledge`** : Recherche sémantique dans les documents
- **`search_formations`** : Recherche les formations disponibles
- **`calculate_fees`** : Calcule les frais de scolarité
- **`get_faculty_info`** : Informations sur les structures
- **`get_schedules_from_db`** : Horaires des services
- **`search_prerequisites`** : Prérequis d'admission
- Et bien d'autres...

#### 6. **Base de Connaissances RAG** (`document_loader.py`)
- **Chargement** : PDF, TXT, Markdown depuis `documents_uam/`
- **Découpage** : Text splitter pour créer des chunks
- **Embeddings** : Vectorisation avec Sentence Transformers
- **Index FAISS** : Recherche vectorielle rapide et efficace

#### 7. **Base de Données SQLite** (`database_connector.py`, `setup_database.py`)
- **Structures** : Facultés, écoles, instituts avec missions détaillées
- **Formations** : 52+ formations avec conditions d'accès
- **Horaires** : 18 services avec contacts complets
- **Frais** : 13 entrées de frais par type d'étudiant
- **Filières** : Spécialisations et débouchés

#### 8. **Mémoire Utilisateur** (`memory.py`)
- **Session** : Mémoire conversationnelle courte durée (MemorySaver)
- **Long terme** : Préférences utilisateur persistantes (JSON)
- **Personnalisation** : Adaptation des réponses selon l'historique

#### 9. **Configuration LLM** (`llm_utils.py`, `config.py`)
- **Multi-providers** : Groq, OpenAI, Claude, Ollama, OpenRouter
- **Initialisation** : Configuration automatique selon le provider
- **Embeddings** : Gestion des modèles d'embedding multilingues

---

## ⚙️ Fonctionnement Détaillé

### Flux d'Exécution Principal

```
1. INITIALISATION
   ├─ Chargement des documents → RAG (FAISS)
   ├─ Connexion à la base de données SQLite
   ├─ Initialisation du LLM (Groq/OpenAI/Claude)
   ├─ Création du graphe LangGraph
   └─ Génération UUID pour la session

2. RÉCEPTION D'UNE QUESTION
   ├─ Création HumanMessage avec la question
   └─ Invocation du graphe avec l'état actuel

3. ROUTAGE INITIAL (route_question)
   ├─ Détection de salutation → Agent direct
   ├─ Vérification pertinence → Agent ou Rejet
   └─ Détection structure mentionnée → Agent spécialisé

4. APPEL DU MODÈLE (call_model)
   ├─ LLM analyse la question
   ├─ Décision : utiliser des outils ou répondre directement
   └─ Si outils nécessaires → Génération tool_calls

5. EXÉCUTION DES OUTILS (tools)
   ├─ Pour chaque tool_call :
   │   ├─ Recherche dans RAG (search_uam_knowledge)
   │   ├─ Requête SQL (search_formations_db)
   │   ├─ Calcul frais (calculate_fees)
   │   └─ Autres outils spécialisés
   └─ Retour des résultats en ToolMessage

6. GÉNÉRATION DE LA RÉPONSE (generate_response)
   ├─ LLM reçoit les résultats des outils
   ├─ Synthèse des informations
   ├─ Génération réponse contextuelle et naturelle
   └─ Ajout à l'historique conversationnel

7. RETOUR À L'UTILISATEUR
   └─ Affichage de la réponse dans l'interface
```

### Exemple Concret : "Quelles sont les formations en Master à la FAST ?"

```
1. Question reçue → HumanMessage("Quelles sont les formations en Master à la FAST ?")

2. route_question détecte :
   - Structure mentionnée : FAST (Faculté des Sciences et Techniques)
   - Question pertinente → Route vers "agent"

3. call_model analyse :
   - Besoin d'informations spécifiques
   - Génère tool_calls :
     * search_formations(faculty="FAST", level="Master")
     * get_faculty_info(faculty_name="FAST")

4. Exécution des outils :
   - search_formations :
     → Requête SQL : SELECT * FROM formations WHERE structure_id=1 AND niveau='Master'
     → Résultats : 8 Masters trouvés
     → Recherche RAG complémentaire dans documents
   - get_faculty_info :
     → Détection structure FAST
     → Recherche mission et composition dans RAG

5. generate_response :
   - LLM reçoit :
     * Liste des 8 Masters avec conditions d'accès
     * Informations sur la FAST
   - Génère réponse structurée et complète

6. Réponse affichée à l'utilisateur
```

### Gestion de l'État

L'état est **persisté** entre les interactions grâce à `MemorySaver` :

```python
# Chaque session a un thread_id unique
thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}

# L'état est automatiquement sauvegardé après chaque interaction
state = agent.invoke({"messages": [HumanMessage("...")]}, config)

# Au prochain appel avec le même thread_id, l'historique est restauré
state = agent.invoke({"messages": [HumanMessage("...")]}, config)
# → Les messages précédents sont toujours présents
```

### Routage Intelligent

Le système utilise **plusieurs niveaux de routage** :

1. **Routage initial** (`route_question`) :
   - Détecte les salutations
   - Vérifie la pertinence (questions UAM vs hors-sujet)
   - Identifie les structures mentionnées

2. **Routage multi-agents** (`multi_agents.py`) :
   - Crée des agents spécialisés par structure
   - Route vers l'agent approprié selon la question
   - Agent général pour questions transversales

3. **Routage outils** (`should_continue`) :
   - Le LLM décide quels outils utiliser
   - Peut appeler plusieurs outils en parallèle
   - Itère jusqu'à avoir assez d'informations

---

## 🔧 Technologies et Bibliothèques

### Core Technologies

| Technologie | Version | Rôle |
|------------|---------|------|
| **LangChain** | v1.0+ | Orchestration LLM, gestion des outils |
| **LangGraph** | v1.0+ | Workflow basé sur graphes d'état |
| **FAISS** | Latest | Recherche vectorielle pour RAG |
| **Sentence Transformers** | Latest | Embeddings multilingues |
| **SQLite** | Built-in | Base de données structurée |
| **Streamlit** | Latest | Interface web interactive |

### LLM Providers Supportés

1. **Groq** (Recommandé)
   - Modèle : Llama 3.3 70B
   - Avantages : Rapide, gratuit jusqu'à quota
   - Package : `langchain-groq`

2. **OpenAI**
   - Modèle : GPT-4o
   - Avantages : Très performant
   - Package : `langchain-openai`

3. **Anthropic (Claude)**
   - Modèle : Claude Sonnet 4
   - Avantages : Excellent raisonnement
   - Package : `langchain-anthropic`

4. **Ollama** (Local)
   - Modèle : Llama 3.2
   - Avantages : Exécution locale, pas de clé API
   - Package : `langchain-community`

5. **OpenRouter**
   - Accès à 300+ modèles
   - Avantages : Meilleurs prix, haute disponibilité
   - Package : `langchain-openai` (compatible)

### Patterns Modernes Utilisés

#### 1. **@tool Decorator**
```python
@tool
def search_uam_knowledge(query: str) -> str:
    """Recherche dans la base de connaissances."""
    # Le décorateur @tool permet au LLM de découvrir et utiliser cette fonction
```

#### 2. **Annotated State**
```python
messages: Annotated[Sequence[BaseMessage], add]
# Le reducer 'add' fusionne automatiquement les nouveaux messages
```

#### 3. **ToolNode Prebuilt**
```python
from langgraph.prebuilt import ToolNode
tool_node = ToolNode(tools)
# Exécute automatiquement les tool_calls du LLM
```

#### 4. **MemorySaver**
```python
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
# Persiste automatiquement l'état entre les appels
```

---

## 📊 Sources de Données

### 1. Base de Connaissances RAG (Recherche Augmentée par Génération)

**Localisation** : `documents_uam/`

**Types de documents** :
- PDF : Guides officiels, présentations
- TXT : Textes structurés, formalités
- Markdown : Documentation formatée

**Processus** :
1. **Chargement** : `document_loader.py` charge tous les fichiers
2. **Découpage** : Text splitter crée des chunks de ~1000 caractères
3. **Embedding** : Chaque chunk est vectorisé avec Sentence Transformers
4. **Indexation** : Stockage dans FAISS pour recherche rapide
5. **Recherche** : Similarité cosinus pour trouver les chunks pertinents

**Avantages** :
- Recherche sémantique (comprend le sens, pas juste les mots-clés)
- Support multilingue (français principalement)
- Mise à jour facile (ajouter des documents)

### 2. Base de Données SQLite

**Localisation** : `uam_database.db`

**Tables principales** :

| Table | Contenu | Lignes |
|-------|---------|--------|
| `structures` | Facultés, écoles, instituts | 9 |
| `formations` | Formations avec conditions | 52 |
| `filieres` | Spécialisations | 9 |
| `horaires` | Horaires des services | 18 |
| `scolarite` | Frais par niveau/type | 13 |

**Avantages** :
- Données structurées et normalisées
- Requêtes SQL précises
- Mise à jour centralisée
- Jointures pour données complexes

**Initialisation** :
```bash
python setup_database.py
```

### 3. Mémoire Utilisateur

**Session** (courte durée) :
- Stockée dans MemorySaver (mémoire)
- Contient l'historique conversationnel
- Perdue à la fin de la session

**Long terme** (persistante) :
- Fichier : `user_memory.json`
- Stocke les préférences utilisateur
- Survit entre les sessions

---

## 🔄 Flux de Données Détaillé

### Scénario : Question sur les frais de scolarité

```
UTILISATEUR
    │
    │ "Combien coûte une licence pour un étudiant nigérien ?"
    ▼
INTERFACE (chatbot.py / app_streamlit.py)
    │
    │ Création HumanMessage
    ▼
AGENT GRAPH (agent_graph.py)
    │
    │ route_question()
    ├─ Détecte question pertinente
    └─ Route vers "agent"
    │
    │ call_model()
    ├─ LLM analyse la question
    ├─ Détecte besoin d'informations précises
    └─ Génère tool_call : calculate_fees(level="Licence", ...)
    │
    │ should_continue()
    ├─ Détecte tool_calls présents
    └─ Route vers "tools"
    │
    │ ToolNode (tools.py)
    ├─ Exécute calculate_fees()
    │   ├─ Appelle search_fees_db(level="Licence")
    │   │   └─ database_connector.py
    │   │       └─ Requête SQL : SELECT * FROM scolarite WHERE niveau LIKE '%Licence%'
    │   │           └─ Retourne : {"frais_inscription": 10000, ...}
    │   └─ Retourne résultat formaté
    └─ Crée ToolMessage avec résultat
    │
    │ Retour vers "agent"
    │
    │ call_model() (2ème appel)
    ├─ LLM reçoit ToolMessage avec frais
    ├─ Synthétise l'information
    └─ Génère réponse naturelle
    │
    │ should_continue()
    ├─ Plus de tool_calls
    └─ Route vers "end"
    │
    │ generate_response()
    └─ Formate la réponse finale
    │
    ▼
INTERFACE
    │
    │ Affiche la réponse
    ▼
UTILISATEUR
    "Pour un étudiant nigérien, les frais d'inscription en Licence sont de 10 000 FCFA..."
```

---

## 🎨 Points Clés de l'Architecture

### 1. **Modularité**
Chaque composant a une responsabilité unique :
- `tools.py` : Outils uniquement
- `graph_nodes.py` : Logique des nœuds uniquement
- `database_connector.py` : Accès BD uniquement
- `document_loader.py` : Chargement documents uniquement

### 2. **Extensibilité**
Facile d'ajouter :
- Nouveaux outils : Décorer avec `@tool`
- Nouveaux nœuds : Ajouter au graphe
- Nouveaux providers LLM : Ajouter dans `llm_utils.py`
- Nouvelles sources de données : Étendre `database_connector.py`

### 3. **Robustesse**
- Gestion d'erreurs à chaque niveau
- Fallback si base de données indisponible
- Validation des entrées utilisateur
- Routage intelligent pour questions hors-sujet

### 4. **Performance**
- Recherche vectorielle FAISS optimisée
- Cache des embeddings
- Requêtes SQL indexées
- Parallélisation possible des outils

### 5. **Maintenabilité**
- Code bien structuré et documenté
- Séparation des préoccupations
- Configuration centralisée
- Tests possibles par composant

---

## 🚀 Utilisation Pratique

### Démarrage Rapide

```bash
# 1. Installation
pip install -r requirements.txt

# 2. Configuration
echo "GROQ_API_KEY=votre_cle" > .env

# 3. Initialisation base de données
python setup_database.py

# 4. Lancement
streamlit run app_streamlit.py
# ou
python agent_uam.py
```

### Configuration

**Fichier `.env`** :
```env
GROQ_API_KEY=gsk_...
UAM_DB_TYPE=sqlite
UAM_DB_PATH=./uam_database.db
```

**Fichier `agent_uam.py`** :
```python
PROVIDER = LLMProvider.LLAMA_GROQ
MODEL_NAME = "llama-3.3-70b-versatile"
```

---

## 📈 Améliorations Futures Possibles

1. **Cache intelligent** : Mise en cache des réponses fréquentes
2. **Analytics** : Suivi des questions les plus posées
3. **Feedback utilisateur** : Système de notation des réponses
4. **Multi-langues** : Support Hausa, Zarma, etc.
5. **API REST** : Exposition de l'agent via API
6. **Intégration WhatsApp** : Bot WhatsApp pour l'UAM
7. **Voice interface** : Support vocal pour questions/réponses

---

## 🔍 Dépannage

### Problèmes Courants

1. **Base de données vide**
   ```bash
   python setup_database.py
   ```

2. **Documents non chargés**
   - Vérifier `documents_uam/` contient des fichiers
   - Vérifier les logs au démarrage

3. **Erreur API**
   - Vérifier `.env` contient la bonne clé
   - Vérifier le quota API

4. **Réponses imprécises**
   - Ajouter plus de documents dans `documents_uam/`
   - Vérifier la qualité des données dans la BD

---

## 📚 Ressources et Documentation

- **LangChain** : https://docs.langchain.com
- **LangGraph** : https://docs.langchain.com/langgraph
- **FAISS** : https://github.com/facebookresearch/faiss
- **Streamlit** : https://docs.streamlit.io

---

## ✨ Conclusion

L'Agent Conversationnel UAM est un système sophistiqué qui combine :
- **IA conversationnelle** moderne (LLM)
- **Recherche sémantique** (RAG)
- **Données structurées** (SQL)
- **Architecture modulaire** (LangGraph)
- **Interface utilisateur** moderne (Streamlit)

Il offre une expérience utilisateur fluide pour obtenir des informations sur l'UAM, avec la capacité d'évoluer et de s'adapter aux besoins futurs.

---

**Dernière mise à jour** : Décembre 2024  
**Version** : 1.0  
**Auteur** : Équipe de développement UAM


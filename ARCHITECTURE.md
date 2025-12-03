# 🏗️ Architecture et Fonctionnement de l'Agent UAM

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture générale](#architecture-générale)
3. [Flux de données](#flux-de-données)
4. [Composants principaux](#composants-principaux)
5. [Système multi-agents](#système-multi-agents)
6. [Mémoire à long terme](#mémoire-à-long-terme)
7. [Comment améliorer l'application](#comment-améliorer-lapplication)
8. [Points d'entrée pour modifications](#points-dentrée-pour-modifications)

---

## 🎯 Vue d'ensemble

L'Agent Conversationnel UAM est un système intelligent qui répond aux questions sur l'Université Abdou Moumouni de Niamey en utilisant :

- **LangChain 1.0+** : Framework pour applications LLM
- **LangGraph 1.0+** : Système de workflows basés sur des graphes d'état
- **FAISS** : Base de données vectorielle pour la recherche sémantique
- **Streamlit** : Interface web moderne

### Fonctionnalités principales

1. 💾 **Mémoire à long terme** : Se souvient des préférences utilisateur
2. 🛠️ **Outils spécialisés** : Calcul frais, recherche formations, etc.
3. 🌐 **Interface web** : Chat UI élégant avec Streamlit
4. 📄 **Export** : Sauvegarde des conversations en PDF/JSON
5. 🤖🤖 **Multi-agents** : Agents spécialisés par faculté

---

## 🏛️ Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACE UTILISATEUR                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Streamlit  │  │   Console    │  │   API REST   │      │
│  │   (Web UI)   │  │    (CLI)     │  │  (Futur)     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │
          └─────────────────┴─────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    COUCHE AGENT                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LangGraph StateGraph                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Route   │→ │  Agent   │→ │  Tools   │          │   │
│  │  │ Question │  │   LLM    │  │  Node    │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘          │   │
│  │       │              │              │                │   │
│  │       └──────────────┴──────────────┘                │   │
│  │                    │                                  │   │
│  │                    ▼                                  │   │
│  │            ┌──────────────┐                          │   │
│  │            │  Response    │                          │   │
│  │            │  Generator   │                          │   │
│  │            └──────────────┘                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    COUCHE OUTILS                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Search     │  │  Calculate   │  │   Get Info   │      │
│  │  Knowledge   │  │    Fees      │  │  Structure   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │
          └─────────────────┴─────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              BASE DE CONNAISSANCES                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   FAISS      │  │   User       │  │  Structures  │      │
│  │  Vectorstore │  │   Memory     │  │  Database    │      │
│  │  (Documents) │  │  (JSON)      │  │  (Python)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flux de données

### 1. Initialisation

```
Démarrage
    │
    ├─→ Charger variables d'environnement (.env)
    │
    ├─→ Initialiser LLM (Groq/OpenAI/Claude)
    │
    ├─→ Charger documents (PDF/TXT) → FAISS Vectorstore
    │
    ├─→ Créer graphe LangGraph
    │
    └─→ Prêt à recevoir des questions
```

### 2. Traitement d'une question

```
Question utilisateur
    │
    ├─→ route_question() : Vérifier pertinence
    │   │
    │   ├─→ Pertinente ? → Agent principal
    │   └─→ Hors sujet ? → Rejeter poliment
    │
    ├─→ call_model() : LLM avec outils bindés
    │   │
    │   ├─→ LLM décide d'utiliser un outil ?
    │   │   │
    │   │   ├─→ Oui → ToolNode exécute l'outil
    │   │   │   │
    │   │   │   └─→ Retour à call_model()
    │   │   │
    │   │   └─→ Non → Générer réponse finale
    │   │
    │   └─→ should_continue() : Routage
    │       │
    │       ├─→ "tools" → Exécuter outils
    │       └─→ "end" → Terminer
    │
    ├─→ generate_response() : Générer réponse avec contexte
    │
    └─→ Sauvegarder dans mémoire utilisateur
```

### 3. Système multi-agents (optionnel)

```
Question utilisateur
    │
    ├─→ route_to_faculty_agent() : Détecter faculté
    │   │
    │   ├─→ Détection par abréviation (FAST, FLSH, etc.)
    │   ├─→ Détection par nom complet
    │   └─→ Détection par mots-clés (fallback)
    │
    ├─→ Agent spécialisé (ex: fast_agent)
    │   │
    │   ├─→ Recherche spécifique dans base de connaissances
    │   ├─→ Prompt spécialisé pour la faculté
    │   └─→ Génération de réponse contextuelle
    │
    └─→ Retour réponse spécialisée
```

---

## 🧩 Composants principaux

### 1. `agent_uam.py` - Cœur de l'application

#### Classes principales

**`LLMProvider`** (Enum)
- Définit les providers LLM supportés
- Valeurs : OPENAI, CLAUDE, LLAMA_OLLAMA, LLAMA_GROQ

**`AgentState`** (TypedDict)
- État de l'agent avec gestion moderne des messages
- Utilise `Annotated[Sequence[BaseMessage], add]` pour fusion automatique

**`UserMemory`** (Class)
- Gestion de la mémoire à long terme
- Stockage JSON persistant
- Méthodes : `save_user_preference()`, `get_user_preferences()`, `add_conversation()`

#### Fonctions principales

**`initialize_llm(provider, model_name, temperature)`**
- Initialise le LLM selon le provider
- Gère les clés API automatiquement

**`load_and_index_documents(pdf_directory, provider)`**
- Charge PDF/TXT/MD/DOCX
- Crée index FAISS vectoriel
- Retourne vectorstore pour recherche sémantique

**`create_agent_graph(vectorstore, llm)`**
- Crée le graphe LangGraph
- Configure les nœuds et transitions
- Intègre ToolNode pour exécution automatique des outils

#### Outils (@tool)

1. **`search_uam_knowledge(query)`** : Recherche sémantique dans documents
2. **`check_question_relevance(question)`** : Vérifie pertinence de la question
3. **`calculate_fees(level, faculty)`** : Calcule frais de scolarité
4. **`search_formations(faculty, level)`** : Recherche formations
5. **`get_faculty_info(faculty_name)`** : Informations sur une faculté
6. **`get_structure_by_abbreviation(abbreviation)`** : Nom complet depuis abréviation
7. **`list_all_structures()`** : Liste toutes les structures UAM
8. **`save_user_preference(user_id, key, value)`** : Sauvegarde préférence
9. **`get_user_preferences(user_id)`** : Récupère préférences

### 2. `multi_agents.py` - Système multi-agents

**`MultiAgentState`** (TypedDict)
- État pour le système multi-agents
- Inclut `faculty` et `agent_used`

**`route_to_faculty_agent(state)`**
- Route vers l'agent spécialisé approprié
- Utilise `detect_structure_in_text()` pour détection automatique

**`create_faculty_agent(faculty_name, faculty_full_name, llm)`**
- Crée un agent spécialisé pour une faculté
- Prompt personnalisé selon la faculté

**`create_multi_agent_graph(vectorstore, llm)`**
- Crée le graphe multi-agents complet
- 7 agents spécialisés + 1 agent général

### 3. `app_streamlit.py` - Interface web

**Fonctionnalités** :
- Chat en temps réel
- Configuration provider LLM
- Choix entre agent simple et multi-agents
- Affichage préférences utilisateur
- Export JSON/PDF
- Gestion sessions avec UUID

### 4. `export_utils.py` - Export conversations

**`export_to_json(conversations, user_id, preferences)`**
- Export format JSON structuré

**`export_to_pdf(conversations, user_id, preferences)`**
- Export format PDF formaté avec ReportLab

---

## 🤖 Système multi-agents

### Architecture

```
Question → route_to_faculty_agent()
    │
    ├─→ Détection structure (FAST, FLSH, etc.)
    │   │
    │   ├─→ fast_agent → Prompt spécialisé FAST
    │   ├─→ flsh_agent → Prompt spécialisé FLSH
    │   ├─→ fa_agent → Prompt spécialisé Agronomie
    │   ├─→ fss_agent → Prompt spécialisé Santé
    │   ├─→ fseg_agent → Prompt spécialisé Économie
    │   ├─→ fsjp_agent → Prompt spécialisé Droit
    │   ├─→ ens_agent → Prompt spécialisé ENS
    │   └─→ general_agent → Questions générales
    │
    └─→ Réponse spécialisée
```

### Avantages

- ✅ Réponses plus précises par domaine
- ✅ Meilleure gestion du contexte
- ✅ Isolation des connaissances
- ✅ Scalable (facile d'ajouter de nouveaux agents)

---

## 💾 Mémoire à long terme

### Structure de stockage (`user_memory.json`)

```json
{
  "user_id_1": {
    "preferences": {
      "faculte_interesse": "FAST",
      "niveau_etude": "master"
    },
    "conversation_history": [
      {
        "question": "...",
        "response": "...",
        "timestamp": "2025-12-03T10:00:00"
      }
    ],
    "created_at": "2025-12-01T08:00:00",
    "last_updated": "2025-12-03T10:00:00"
  }
}
```

### Utilisation

- Sauvegarde automatique des conversations
- Récupération des préférences pour personnalisation
- Historique pour contexte conversationnel

---

## 🚀 Comment améliorer l'application

### 1. Ajouter de nouveaux outils

**Fichier** : `agent_uam.py`

**Étape 1** : Créer la fonction avec décorateur `@tool`

```python
@tool
def mon_nouvel_outil(param1: str, param2: int) -> str:
    """
    Description de ce que fait l'outil.
    
    Args:
        param1: Description du paramètre 1
        param2: Description du paramètre 2
        
    Returns:
        Description de ce qui est retourné
    """
    # Votre logique ici
    result = f"Résultat avec {param1} et {param2}"
    return result
```

**Étape 2** : Ajouter à la liste des outils

```python
def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    return [
        search_uam_knowledge,
        check_question_relevance,
        # ... autres outils ...
        mon_nouvel_outil  # ← Ajouter ici
    ]
```

**Exemple concret** : Ajouter un outil pour vérifier les horaires

```python
@tool
def get_opening_hours(service: str) -> str:
    """
    Obtient les horaires d'ouverture d'un service de l'UAM.
    
    Args:
        service: Nom du service (ex: "bibliothèque", "scolarité")
        
    Returns:
        Horaires d'ouverture du service
    """
    # Logique de recherche dans la base de connaissances
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    docs = _vectorstore.similarity_search(f"horaires {service}", k=2)
    if docs:
        return "\n\n".join([doc.page_content[:500] for doc in docs])
    return f"Horaires non trouvés pour {service}"
```

### 2. Améliorer la détection de structures

**Fichier** : `agent_uam.py` (section `UAM_STRUCTURES`)

**Ajouter une nouvelle structure** :

```python
UAM_STRUCTURES = {
    "facultes": {
        # ... structures existantes ...
        "NOUVELLE_FAC": {
            "nom_complet": "Nouvelle Faculté",
            "variantes": ["nouvelle faculté", "NOUVELLE_FAC", "NF"]
        }
    },
    # ...
}
```

**Ajouter un nouvel agent** : `multi_agents.py`

```python
# Dans FACULTIES
"NOUVELLE_FAC": "Nouvelle Faculté"

# Dans route_to_faculty_agent()
agent_mapping = {
    # ... mappings existants ...
    "nouvelle_fac": "nouvelle_fac_agent"
}

# Créer l'agent spécialisé
workflow.add_node("nouvelle_fac_agent", create_faculty_agent("NOUVELLE_FAC", "Nouvelle Faculté", llm))
```

### 3. Améliorer le prompt système

**Fichier** : `agent_uam.py` (fonction `call_model`)

**Modifier le prompt** :

```python
system_prompt = """Tu es l'assistant virtuel officiel de l'UAM.

NOUVELLES CONSIGNES :
- [Ajouter vos nouvelles consignes ici]
- [Autre consigne]

CONSIGNES EXISTANTES :
- Réponds de manière claire, précise et professionnelle
- ...
"""
```

### 4. Ajouter de nouveaux formats de documents

**Fichier** : `agent_uam.py` (fonction `load_and_index_documents`)

**Ajouter support Excel** :

```python
# 5. Charger les fichiers Excel (nouveau)
try:
    from langchain_community.document_loaders import ExcelLoader
    xlsx_files = list(Path(pdf_directory).glob("**/*.xlsx"))
    if xlsx_files:
        xlsx_loader = DirectoryLoader(
            pdf_directory,
            glob="**/*.xlsx",
            loader_cls=ExcelLoader,
            show_progress=False
        )
        xlsx_docs = xlsx_loader.load()
        all_documents.extend(xlsx_docs)
        print(f"  ✓ {len(xlsx_docs)} fichier(s) Excel chargé(s)")
except Exception as e:
    if "No module named" not in str(e):
        print(f"    Erreur chargement Excel: {e}")
```

### 5. Améliorer l'interface Streamlit

**Fichier** : `app_streamlit.py`

**Ajouter une nouvelle fonctionnalité** :

```python
# Dans la sidebar
st.subheader("📊 Statistiques")
if st.session_state.get("conversation_history"):
    st.metric("Conversations", len(st.session_state.conversation_history))
    st.metric("Messages", len(st.session_state.messages))
```

### 6. Améliorer la recherche sémantique

**Fichier** : `agent_uam.py` (fonction `search_uam_knowledge`)

**Ajouter filtrage par métadonnées** :

```python
@tool
def search_uam_knowledge(query: str, faculty: str = "") -> str:
    """
    Recherche avec filtrage optionnel par faculté.
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Recherche avec métadonnées si faculté spécifiée
    if faculty:
        filter_dict = {"faculty": faculty}
        docs = _vectorstore.similarity_search(query, k=4, filter=filter_dict)
    else:
        docs = _vectorstore.similarity_search(query, k=4)
    
    # ... reste du code ...
```

### 7. Ajouter une base de données pour la mémoire

**Créer** : `database.py`

```python
import sqlite3
from typing import Dict, Any, List

class DatabaseMemory:
    """Mémoire persistante avec SQLite"""
    
    def __init__(self, db_path: str = "uam_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT,
                key TEXT,
                value TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY (user_id, key)
            )
        """)
        # ... autres tables ...
        conn.commit()
        conn.close()
    
    # ... méthodes de sauvegarde/récupération ...
```

**Remplacer** : `_user_memory = UserMemory()` par `_user_memory = DatabaseMemory()`

### 8. Ajouter authentification utilisateur

**Créer** : `auth.py`

```python
import hashlib
import secrets

class UserAuth:
    """Gestion de l'authentification utilisateur"""
    
    def create_user(self, email: str, password: str) -> str:
        """Crée un nouvel utilisateur"""
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        # Sauvegarder dans base de données
        return user_id
    
    def authenticate(self, email: str, password: str) -> Optional[str]:
        """Authentifie un utilisateur"""
        # Vérifier credentials
        return user_id if valid else None
```

**Intégrer dans Streamlit** :

```python
# Dans app_streamlit.py
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # Afficher formulaire de connexion
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Se connecter"):
        user_id = auth.authenticate(email, password)
        if user_id:
            st.session_state.authenticated = True
            st.session_state.user_id = user_id
```

---

## 📍 Points d'entrée pour modifications

### Pour ajouter une fonctionnalité

1. **Nouvel outil** → `agent_uam.py` ligne ~590-700
2. **Nouvelle structure** → `agent_uam.py` ligne ~80-180
3. **Nouvel agent** → `multi_agents.py` ligne ~40-250
4. **Nouveau format document** → `agent_uam.py` ligne ~400-480
5. **Amélioration UI** → `app_streamlit.py`
6. **Nouveau format export** → `export_utils.py`

### Pour modifier le comportement

1. **Prompt système** → `agent_uam.py` ligne ~620-640
2. **Routage questions** → `agent_uam.py` ligne ~570-590
3. **Routage multi-agents** → `multi_agents.py` ligne ~50-100
4. **Gestion mémoire** → `agent_uam.py` ligne ~520-590

### Pour déboguer

1. **Activer logs détaillés** :
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Ajouter print statements** dans les fonctions clés
3. **Tester individuellement** chaque composant

---

## 🔧 Guide de développement

### Workflow recommandé

1. **Identifier le besoin** : Quelle fonctionnalité ajouter ?
2. **Choisir le point d'entrée** : Où modifier le code ?
3. **Tester localement** : Créer un script de test
4. **Intégrer** : Ajouter au code principal
5. **Tester end-to-end** : Vérifier avec l'interface complète
6. **Documenter** : Mettre à jour README/FEATURES.md

### Exemple : Ajouter un outil de calcul de moyenne

**Étape 1** : Créer la fonction

```python
@tool
def calculate_average_grades(grades: str) -> str:
    """
    Calcule la moyenne à partir d'une liste de notes.
    
    Args:
        grades: Liste de notes séparées par des virgules (ex: "15,18,12,16")
        
    Returns:
        La moyenne calculée
    """
    try:
        grade_list = [float(g.strip()) for g in grades.split(",")]
        average = sum(grade_list) / len(grade_list)
        return f"Moyenne calculée: {average:.2f}/20"
    except Exception as e:
        return f"Erreur: {e}"
```

**Étape 2** : Ajouter à `get_tools()`

```python
def get_tools():
    return [
        # ... outils existants ...
        calculate_average_grades  # Nouvel outil
    ]
```

**Étape 3** : Tester

```python
# test_tool.py
from agent_uam import calculate_average_grades

result = calculate_average_grades.invoke({"grades": "15,18,12,16"})
print(result)  # Devrait afficher: "Moyenne calculée: 15.25/20"
```

**Étape 4** : L'agent peut maintenant utiliser cet outil automatiquement !

---

## 📚 Ressources pour aller plus loin

- [Documentation LangChain](https://docs.langchain.com/oss/python/langchain/overview)
- [Documentation LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [Documentation Streamlit](https://docs.streamlit.io/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

---

## 🎯 Prochaines améliorations suggérées

1. **API REST** : Exposer l'agent via FastAPI/Flask
2. **Base de données** : Remplacer JSON par PostgreSQL/SQLite
3. **Authentification** : Système de login utilisateur
4. **Analytics** : Suivi des questions les plus fréquentes
5. **Multilingue** : Support Hausa, Zarma, etc.
6. **Notifications** : Alertes pour nouvelles informations
7. **Intégration calendrier** : Rappels d'événements importants
8. **Chatbot vocal** : Support audio avec Whisper/TTS

---

**Note** : Cette architecture est modulaire et extensible. N'hésitez pas à expérimenter et améliorer !


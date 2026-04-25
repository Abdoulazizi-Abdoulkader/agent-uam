# 🤖 Agent Conversationnel UAM

Agent conversationnel intelligent pour l'Université Abdou Moumouni de Niamey (UAM), basé sur les dernières technologies LangChain v1.0+ et LangGraph v1.0+ (2025).

## 📋 Table des matières

- [Description](#description)
- [Fonctionnalités](#fonctionnalités)
- [Technologies utilisées](#technologies-utilisées)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Structure du projet](#structure-du-projet)
- [Améliorations implémentées](#améliorations-implémentées)
- [Support des LLM](#support-des-llm)
- [Documentation technique](#documentation-technique)
- [Dépannage](#dépannage)
- [Documentation et ressources](#documentation-et-ressources)
- [Contribution](#contribution)
- [Licence](#licence)

## 🎯 Description

Cet agent conversationnel permet aux étudiants, enseignants et visiteurs de l'Université Abdou Moumouni de Niamey d'obtenir des informations sur :

- 📋 Les facultés, écoles et instituts
- 🎓 Les formations et filières disponibles
- 📝 Les conditions d'admission et pièces d'inscription
- 🏢 Les démarches administratives (diplômes, attestations, relevés, etc.)
- ⏰ Les horaires et services
- 📞 Les contacts des différents services

L'agent utilise une base de connaissances vectorielle construite à partir des documents officiels de l'université pour fournir des réponses précises et contextuelles.

## ✨ Fonctionnalités

### Fonctionnalités de Base
- ✅ **Recherche sémantique** : Recherche intelligente dans la base de connaissances UAM
- ✅ **Gestion de conversation** : Maintien du contexte conversationnel avec MemorySaver
- ✅ **Routage intelligent** : Détection automatique de la pertinence des questions
- ✅ **Multi-providers** : Support de plusieurs fournisseurs LLM (OpenAI, Claude, Groq, Ollama)
- ✅ **Persistance de session** : Chaque session utilise un UUID unique pour la continuité
- ✅ **Gestion moderne de l'état** : Utilisation d'Annotated pour la fusion automatique des messages
- ✅ **Outils intégrés** : Utilisation du décorateur @tool pour une meilleure intégration

### Nouvelles Fonctionnalités (2025)
- 💾 **Mémoire à long terme** : Se souvient des préférences utilisateur entre les sessions
- 🛠️ **Outils spécialisés** : Calcul frais, recherche formations, informations facultés
- 🌐 **Interface Streamlit moderne** : Chat UI élégant avec fonctionnalités avancées
- 📄 **Export conversations** : Sauvegarde en PDF/JSON
- 🤖🤖 **Multi-agents** : Agents spécialisés par faculté pour des réponses plus précises

## 🛠 Technologies utilisées

### Core
- **LangChain v1.0+** : Framework pour applications LLM
  - 📚 [Documentation LangChain](https://docs.langchain.com/oss/python/langchain/overview)
- **LangGraph v1.0+** : Création de workflows basés sur des graphes d'état
  - 📚 [Documentation LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- **DeepAgents** : Framework pour agents avancés
  - 📚 [Documentation DeepAgents](https://docs.langchain.com/oss/python/deepagents/overview)
- **FAISS** : Recherche vectorielle pour la base de connaissances
- **Sentence Transformers** : Embeddings multilingues

### LLM Providers supportés
- **Groq** (recommandé) : Llama 3.3 70B
- **OpenAI** : GPT-4o
- **Anthropic** : Claude Sonnet 4
- **Ollama** : Modèles locaux (Llama 3.2)

### Traitement de documents
- **PyPDF** : Chargement de fichiers PDF
- **TextLoader** : Chargement de fichiers texte
- Support optionnel pour Markdown et DOCX

## 📦 Installation

### Prérequis

- Python 3.10 ou supérieur
- pip (gestionnaire de paquets Python)

### Installation des dépendances

1. **Cloner le dépôt** (ou télécharger les fichiers)

```bash
git clone <url-du-repo>
cd agent-uam
```

2. **Créer un environnement virtuel** (recommandé)

```bash
python -m venv venv
source venv/bin/activate  # Sur Linux/Mac
# ou
venv\Scripts\activate  # Sur Windows
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

### Installation avec GPU (optionnel)

Pour améliorer les performances avec FAISS :

```bash
pip install faiss-gpu
```

## ⚙️ Configuration

### 1. Configuration des clés API

Créez un fichier `.env` à la racine du projet avec vos clés API :

```env
# Groq (recommandé)
GROQ_API_KEY=gsk_votre_cle_groq

# Ou pour OpenAI
OPENAI_API_KEY=sk-votre_cle_openai

# Ou pour Claude
ANTHROPIC_API_KEY=sk-ant-votre_cle_anthropic

# Ou pour OpenRouter (accès à plusieurs modèles via une seule API)
OPENROUTER_API_KEY=sk-or-v1-votre_cle_openrouter
# Optionnel : pour identifier votre application
OPENROUTER_APP_URL=https://github.com/votre-repo
OPENROUTER_APP_NAME=Agent UAM
```

**Note** : Vous n'avez besoin que d'une seule clé API selon le provider que vous souhaitez utiliser.

### 2. Préparation des documents

Placez vos documents (PDF, TXT) dans le dossier `documents_uam/` :

```bash
mkdir documents_uam
# Copiez vos fichiers PDF et TXT dans ce dossier
```

### 3. Configuration du provider LLM

Dans `agent_uam.py`, modifiez les variables de configuration :

```python
# Configuration pour Groq (Llama) - RECOMMANDÉ
PROVIDER = LLMProvider.LLAMA_GROQ
MODEL_NAME = "llama-3.3-70b-versatile"

# Autres options disponibles :
# PROVIDER = LLMProvider.CLAUDE
# MODEL_NAME = "claude-sonnet-4-20250514"

# PROVIDER = LLMProvider.OPENAI
# MODEL_NAME = "gpt-4o"

# PROVIDER = LLMProvider.LLAMA_OLLAMA
# MODEL_NAME = "llama3.2"

# PROVIDER = LLMProvider.OPENROUTER
# MODEL_NAME = "openai/gpt-4o"  # ou "anthropic/claude-3.7-sonnet", "google/gemini-pro", etc.
# Voir https://openrouter.ai/models pour la liste complète des modèles disponibles
```

## 🚀 Utilisation

### Option 1 : Interface Web (Recommandé)

```bash
streamlit run app_streamlit.py
```

Puis ouvrez votre navigateur sur `http://localhost:8501`

**Avantages** :
- Interface moderne et intuitive
- Chat en temps réel
- Export des conversations
- Configuration avancée
- Support multi-agents

### Option 2 : Mode Console (CLI)

```bash
python agent_uam.py
```

**Avantages** :
- Légère et rapide
- Pas de dépendances web
- Idéal pour les scripts

### Interaction avec l'agent

Une fois lancé, l'agent affichera :

```
🎓 Initialisation de l'agent conversationnel UAM avec llama_groq...
📚 Chargement des documents...
  ✓ 3 PDF(s) chargé(s)
  ✓ 2 fichier(s) TXT chargé(s)
✅ 5 document(s) total chargé(s) et divisé(s) en 45 chunks

✅ Agent prêt avec llama_groq ! Posez vos questions sur l'UAM
   (Tapez 'quit', 'exit' ou 'bye' pour quitter)
============================================================

📝 Session ID: 550e8400-e29b-41d4-a716-446655440000

🤖 Assistant: Bonjour ! Je suis l'assistant virtuel de l'Université Abdou Moumouni de Niamey.
              Comment puis-je vous aider ?

👤 Vous: Quelles sont les filières disponibles à la Faculté des Sciences ?
```

### Commandes disponibles

- `quit`, `exit`, `bye`, `au revoir`, `quitter` : Quitter l'application

## 📁 Structure du projet

```
agent-uam/
│
├── agent_uam.py              # Agent principal avec mémoire et outils
├── app_streamlit.py         # Interface Streamlit moderne
├── multi_agents.py          # Système multi-agents par faculté
├── export_utils.py          # Utilitaires d'export PDF/JSON
├── requirements.txt         # Dépendances Python
├── README.md                # Documentation principale
├── IMPROVEMENTS.md          # Documentation des améliorations récentes
├── run_streamlit.sh         # Script pour lancer Streamlit
│
├── logger_config.py          # Configuration du système de logging
├── utils.py                 # Utilitaires généraux (validation, helpers)
├── app_config.py            # Configuration centralisée de l'application
│
├── documents_uam/           # Dossier contenant les documents UAM
│   ├── Document_Final_SR_UAM.pdf
│   ├── Formalités_d_admission.txt
│   ├── formations.pdf
│   ├── preinscription_uam.pdf
│   └── Présentation_des_Facultés_Ecoles_Instituts.txt
│
├── exports/                 # Dossier d'export (généré automatiquement)
├── logs/                    # Dossier des logs (généré automatiquement)
│   ├── agent_uam_YYYYMMDD.log
│   └── errors_YYYYMMDD.log
├── user_memory.json         # Mémoire persistante (généré automatiquement)
└── venv/                    # Environnement virtuel Python (généré)
```

## 🔧 Améliorations implémentées (2025)

### Améliorations Récentes

#### ✅ Système de Logging Structuré
- Logging complet avec différents niveaux (DEBUG, INFO, WARNING, ERROR)
- Logs séparés pour les erreurs (`logs/errors_YYYYMMDD.log`)
- Logs détaillés avec contexte (fichier, ligne, fonction)
- Rotation automatique des fichiers de log par date

#### ✅ Gestion d'Erreurs Améliorée
- Gestion d'erreurs robuste avec try/except appropriés
- Messages d'erreur conviviaux pour l'utilisateur
- Retry logic pour les opérations critiques
- Validation des entrées utilisateur

#### ✅ Configuration Centralisée
- Module de configuration centralisé (`app_config.py`)
- Chargement depuis les variables d'environnement
- Configuration pour base de données, LLM, vector store
- Validation et initialisation automatique des dossiers

#### ✅ Utilitaires et Helpers
- Fonctions de validation et sanitization
- Extraction d'entités (structures, niveaux, mots-clés)
- Formatage d'erreurs convivial
- Helpers pour manipulation de données

### Fonctionnalités LangChain/LangGraph

Ce projet utilise les dernières fonctionnalités de LangChain et LangGraph :

### ✅ @tool decorator
Les outils sont définis avec le décorateur `@tool` pour une meilleure intégration avec LangGraph :

```python
@tool
def search_uam_knowledge(query: str) -> str:
    """Recherche des informations dans la base de connaissances de l'UAM."""
    # ...
```

### ✅ UUID pour les sessions
Chaque session utilise un `thread_id` unique généré avec `uuid.uuid4()` :

```python
thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}
```

### ✅ StateGraph
Utilisation de `StateGraph` pour structurer le workflow de l'agent avec routage conditionnel.

### ✅ Annotated State
L'état de l'agent utilise `Annotated[Sequence[BaseMessage], add]` pour la fusion automatique des messages :

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]
    # ...
```

### ✅ MemorySaver
Persistance de l'état avec `MemorySaver` pour maintenir la continuité des conversations :

```python
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### ✅ Gestion moderne des messages
Utilisation de `BaseMessage` et de ses sous-classes (`HumanMessage`, `AIMessage`, `SystemMessage`) pour une meilleure intégration avec LangChain.

## 🤖 Support des LLM

### Groq (Recommandé)
- **Avantages** : Rapide, gratuit jusqu'à un certain quota, modèle Llama 3.3 70B performant
- **Configuration** : `GROQ_API_KEY` dans `.env`
- **Modèle par défaut** : `llama-3.3-70b-versatile`

### OpenAI
- **Avantages** : Très performant, modèle GPT-4o
- **Configuration** : `OPENAI_API_KEY` dans `.env`
- **Modèle par défaut** : `gpt-4o`

### Anthropic (Claude)
- **Avantages** : Excellent pour le raisonnement complexe
- **Configuration** : `ANTHROPIC_API_KEY` dans `.env`
- **Modèle par défaut** : `claude-sonnet-4-20250514`

### Ollama (Local)
- **Avantages** : Exécution locale, pas besoin de clé API
- **Configuration** : Installer Ollama localement
- **Modèle par défaut** : `llama3.2`

### OpenRouter
- **Avantages** : Accès à 300+ modèles via une seule API, meilleurs prix, haute disponibilité, compatible OpenAI
- **Configuration** : `OPENROUTER_API_KEY` dans `.env`
- **Modèle par défaut** : `openai/gpt-4o`
- **Modèles disponibles** : Voir [https://openrouter.ai/models](https://openrouter.ai/models)
- **Exemples de modèles** :
  - `openai/gpt-4o` - GPT-4o d'OpenAI
  - `anthropic/claude-3.7-sonnet` - Claude Sonnet 3.7
  - `google/gemini-pro` - Gemini Pro de Google
  - `meta-llama/llama-3.1-70b-instruct` - Llama 3.1 70B
  - Et bien d'autres...
- **Modèle par défaut** : `llama3.2`

## 🔍 Dépannage

### Erreur : "Aucun document trouvé"
**Solution** : Vérifiez que le dossier `documents_uam/` contient des fichiers PDF ou TXT.

### Erreur : "Provider non supporté"
**Solution** : Vérifiez que vous avez installé le package correspondant :
- `langchain-groq` pour Groq
- `langchain-openai` pour OpenAI
- `langchain-anthropic` pour Claude
- `langchain-community` pour Ollama

### Erreur : "API key not found"
**Solution** : Vérifiez que votre fichier `.env` contient la bonne clé API et qu'il est à la racine du projet.

### Erreur avec FAISS sur Windows
**Solution** : Utilisez conda pour installer FAISS :
```bash
conda install -c pytorch faiss-cpu
```

### L'agent ne répond pas correctement
**Solutions** :
1. Vérifiez que vos documents sont bien chargés (regardez les logs au démarrage)
2. Essayez de reformuler votre question
3. Vérifiez que le provider LLM est correctement configuré

## 📝 Exemples de questions

Voici quelques exemples de questions que vous pouvez poser à l'agent :

### Questions générales
- "Quelles sont les filières disponibles à la Faculté des Sciences ?"
- "Comment s'inscrire à l'UAM ?"
- "Quels sont les documents nécessaires pour l'inscription ?"

### Questions sur les formations
- "Quelles sont les conditions d'admission en Master ?"
- "Quelles formations sont disponibles en Agronomie ?"
- "Quels sont les débouchés de la Faculté des Sciences et Techniques ?"

### Questions administratives
- "Comment obtenir une attestation de scolarité ?"
- "Quels sont les frais de scolarité pour une licence ?"
- "Quels sont les horaires de la bibliothèque ?"

### Questions spécialisées (Multi-agents)
- "Quelles sont les spécialités en Master à la FAST ?" → Routage vers FAST Agent
- "Quelles formations propose la Faculté d'Agronomie ?" → Routage vers FA Agent

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. Forkez le projet
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📄 Licence

Ce projet est développé pour l'Université Abdou Moumouni de Niamey (UAM).

## 👥 Auteurs

Développé pour l'Université Abdou Moumouni de Niamey (UAM).

## 📚 Documentation et ressources

### Documentation officielle
- **LangChain** : [https://docs.langchain.com/oss/python/langchain/overview](https://docs.langchain.com/oss/python/langchain/overview)
- **LangGraph** : [https://docs.langchain.com/oss/python/langgraph/overview](https://docs.langchain.com/oss/python/langgraph/overview)
- **DeepAgents** : [https://docs.langchain.com/oss/python/deepagents/overview](https://docs.langchain.com/oss/python/deepagents/overview)

### Ressources supplémentaires
- [LangChain GitHub](https://github.com/langchain-ai/langchain)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [Exemples LangChain](https://github.com/langchain-ai/langchain/tree/master/templates)

## 🙏 Remerciements

- LangChain et LangGraph pour leurs excellentes bibliothèques
- La communauté open-source pour les outils et ressources
- L'Université Abdou Moumouni de Niamey pour le support

---

**Note** : Ce projet utilise les dernières versions de LangChain (v1.0+) et LangGraph (v1.0+) datant de 2025, avec toutes les fonctionnalités modernes pour une meilleure performance et une meilleure maintenabilité.

Pour plus d'informations, consultez la [documentation officielle LangChain](https://docs.langchain.com/oss/python/langchain/overview) et [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview).


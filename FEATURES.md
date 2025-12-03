# 🚀 Nouvelles Fonctionnalités - Agent UAM

## 📋 Résumé des Améliorations

Cette version améliorée de l'Agent Conversationnel UAM inclut 5 fonctionnalités majeures :

### 1. 💾 Mémoire à Long Terme

**Fonctionnalité** : L'agent se souvient des préférences utilisateur entre les sessions.

**Implémentation** :
- Stockage persistant dans `user_memory.json`
- Sauvegarde automatique des préférences utilisateur
- Historique des conversations par utilisateur
- API simple pour sauvegarder/récupérer les préférences

**Utilisation** :
```python
from agent_uam import _user_memory

# Sauvegarder une préférence
_user_memory.save_user_preference("user_123", "faculte_interesse", "FAST")

# Récupérer les préférences
prefs = _user_memory.get_user_preferences("user_123")
```

**Outils disponibles** :
- `save_user_preference()` : Sauvegarde une préférence
- `get_user_preferences()` : Récupère les préférences

### 2. 🛠️ Outils Spécialisés

**Fonctionnalité** : Outils dédiés pour des tâches spécifiques.

**Outils disponibles** :

#### `calculate_fees(level, faculty)`
Calcule les frais de scolarité selon le niveau et la faculté.
- **Niveaux** : licence, master, doctorat
- **Exemple** : `calculate_fees("licence", "FAST")`

#### `search_formations(faculty, level)`
Recherche les formations disponibles.
- **Paramètres** : faculté (optionnel), niveau (optionnel)
- **Exemple** : `search_formations("FAST", "master")`

#### `get_faculty_info(faculty_name)`
Obtient des informations détaillées sur une faculté.
- **Exemple** : `get_faculty_info("Faculté des Sciences et Techniques")`

#### `save_user_preference(user_id, key, value)`
Sauvegarde une préférence utilisateur.
- **Exemple** : `save_user_preference("user_123", "niveau_etude", "master")`

#### `get_user_preferences(user_id)`
Récupère les préférences d'un utilisateur.

### 3. 🌐 Interface Streamlit Moderne

**Fonctionnalité** : Interface web élégante avec chat UI.

**Caractéristiques** :
- Design moderne et responsive
- Chat en temps réel
- Sidebar pour la configuration
- Gestion des sessions utilisateur
- Export des conversations
- Affichage des préférences utilisateur

**Lancement** :
```bash
# Option 1 : Script bash
./run_streamlit.sh

# Option 2 : Directement
streamlit run app_streamlit.py
```

**Fonctionnalités de l'interface** :
- Sélection du provider LLM (Groq, OpenAI, Claude, Ollama)
- Choix entre agent simple et multi-agents
- Configuration du modèle
- Affichage de l'historique des conversations
- Export JSON/PDF depuis l'interface

### 4. 📄 Export des Conversations

**Fonctionnalité** : Export des conversations en JSON et PDF.

**Format JSON** :
```json
{
  "user_id": "uuid",
  "export_date": "2025-01-15T10:30:00",
  "conversations": [
    {
      "question": "...",
      "response": "...",
      "timestamp": "..."
    }
  ],
  "preferences": {...},
  "total_conversations": 10
}
```

**Format PDF** :
- Mise en page professionnelle
- En-tête avec informations de l'export
- Préférences utilisateur
- Historique complet des conversations
- Formatage élégant avec styles

**Utilisation** :
```python
from export_utils import export_to_json, export_to_pdf

# Export JSON
json_path = export_to_json(conversations, user_id, preferences)

# Export PDF
pdf_path = export_to_pdf(conversations, user_id, preferences)
```

### 5. 🤖🤖 Système Multi-Agents

**Fonctionnalité** : Agents spécialisés par faculté pour des réponses plus précises.

**Agents disponibles** :
- **FAST Agent** : Faculté des Sciences et Techniques
- **FA Agent** : Faculté d'Agronomie
- **FLSH Agent** : Faculté des Lettres et Sciences Humaines
- **FSS Agent** : Faculté des Sciences de la Santé
- **FSEG Agent** : Faculté des Sciences Économiques et Juridiques
- **FSJP Agent** : Faculté des Sciences Juridiques et Politiques
- **ENS Agent** : École Normale Supérieure
- **General Agent** : Questions générales sur l'UAM

**Routage automatique** :
- Détection automatique de la faculté concernée par mots-clés
- Routage vers l'agent spécialisé approprié
- Chaque agent a un prompt spécialisé et une expertise dédiée

**Utilisation** :
```python
from multi_agents import create_multi_agent_graph

# Créer le graphe multi-agents
multi_agent = create_multi_agent_graph(vectorstore, llm)

# Utiliser comme un agent normal
result = multi_agent.invoke(state, config)
```

**Avantages** :
- Réponses plus précises et spécialisées
- Meilleure gestion du contexte par domaine
- Isolation des connaissances par faculté
- Scalabilité : facile d'ajouter de nouveaux agents

## 📦 Installation

### Dépendances supplémentaires

```bash
pip install streamlit reportlab
```

### Structure des fichiers

```
agent-uam/
├── agent_uam.py          # Agent principal avec mémoire et outils
├── app_streamlit.py      # Interface Streamlit
├── multi_agents.py       # Système multi-agents
├── export_utils.py      # Utilitaires d'export
├── user_memory.json     # Mémoire persistante (généré)
├── exports/              # Dossier d'export (généré)
└── requirements.txt      # Dépendances mises à jour
```

## 🎯 Exemples d'Utilisation

### Exemple 1 : Utiliser la mémoire à long terme

```python
from agent_uam import _user_memory

# L'utilisateur mentionne qu'il est intéressé par la FAST
_user_memory.save_user_preference("user_123", "faculte_interesse", "FAST")

# Plus tard, l'agent peut utiliser cette information
prefs = _user_memory.get_user_preferences("user_123")
# L'agent peut personnaliser ses réponses selon les préférences
```

### Exemple 2 : Utiliser les outils spécialisés

```python
# L'agent peut appeler automatiquement ces outils
# Exemple : "Quels sont les frais pour une licence à la FAST ?"
# → L'agent appelle calculate_fees("licence", "FAST")
```

### Exemple 3 : Interface Streamlit

```bash
# Lancer l'interface
streamlit run app_streamlit.py

# Accéder à http://localhost:8501
```

### Exemple 4 : Multi-agents

```python
from multi_agents import create_multi_agent_graph

# Créer le système multi-agents
multi_agent = create_multi_agent_graph(vectorstore, llm)

# Question sur la FAST → Routage automatique vers FAST Agent
# Question générale → Routage vers General Agent
```

## 🔧 Configuration

### Variables d'environnement

Créez un fichier `.env` :
```env
GROQ_API_KEY=votre_cle
# ou
OPENAI_API_KEY=votre_cle
# ou
ANTHROPIC_API_KEY=votre_cle
```

### Personnalisation

- **Mémoire** : Modifier `user_memory.json` pour changer le format
- **Outils** : Ajouter de nouveaux outils dans `agent_uam.py`
- **Agents** : Ajouter de nouveaux agents dans `multi_agents.py`
- **Interface** : Personnaliser `app_streamlit.py` pour le design

## 📊 Performance

- **Mémoire** : Stockage JSON léger et rapide
- **Multi-agents** : Routage intelligent pour des réponses plus rapides
- **Streamlit** : Interface réactive avec mise en cache

## 🐛 Dépannage

### Erreur : "reportlab not found"
```bash
pip install reportlab
```

### Erreur : "streamlit not found"
```bash
pip install streamlit
```

### Erreur : "user_memory.json not found"
Le fichier sera créé automatiquement au premier usage.

## 🚀 Prochaines Étapes

- [ ] Intégration avec base de données pour la mémoire
- [ ] Interface Flask alternative
- [ ] Analytics et métriques d'utilisation
- [ ] Support multilingue
- [ ] Intégration avec API externes


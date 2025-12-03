# 🛠️ Guide de Développement - Agent UAM

## 🎯 Comment prendre la main sur le projet

Ce guide vous explique comment comprendre, modifier et améliorer l'application étape par étape.

---

## 📖 Comprendre le code

### Structure des fichiers

```
agent-uam/
├── agent_uam.py          # ⭐ FICHIER PRINCIPAL - Cœur de l'application
├── multi_agents.py       # Système multi-agents par faculté
├── app_streamlit.py      # Interface web Streamlit
├── export_utils.py       # Export PDF/JSON
├── documents_uam/        # Documents sources (PDF/TXT)
├── user_memory.json      # Mémoire persistante (généré)
└── requirements.txt      # Dépendances
```

### Parcours de lecture recommandé

1. **Commencer par** : `agent_uam.py` lignes 1-100
   - Imports et configuration de base
   - Structure `UAM_STRUCTURES` (connaissances structurées)

2. **Ensuite** : `agent_uam.py` lignes 250-350
   - `AgentState` : Structure de l'état
   - `initialize_llm()` : Comment le LLM est initialisé

3. **Puis** : `agent_uam.py` lignes 380-500
   - `load_and_index_documents()` : Chargement des documents
   - Création du vectorstore FAISS

4. **Ensuite** : `agent_uam.py` lignes 590-700
   - Outils (@tool) : Fonctions disponibles pour l'agent
   - `get_tools()` : Liste des outils

5. **Puis** : `agent_uam.py` lignes 800-950
   - Nœuds du graphe : `route_question()`, `call_model()`, `should_continue()`
   - Logique de routage et décision

6. **Enfin** : `agent_uam.py` lignes 950-1100
   - `create_agent_graph()` : Construction du graphe LangGraph
   - Intégration de tous les composants

---

## 🔍 Comprendre le flux d'exécution

### Scénario 1 : Question simple

```
Utilisateur: "Quelles sont les formations à la FAST ?"
    │
    ▼
1. route_question() détecte "FAST" → Route vers "agent"
    │
    ▼
2. call_model() appelle le LLM avec outils bindés
    │
    ├─→ LLM décide d'utiliser search_uam_knowledge("formations FAST")
    │
    ▼
3. ToolNode exécute search_uam_knowledge
    │
    ├─→ Recherche dans FAISS vectorstore
    │
    ▼
4. Retour à call_model() avec résultats
    │
    ▼
5. LLM génère réponse finale avec contexte
    │
    ▼
6. Réponse affichée à l'utilisateur
```

### Scénario 2 : Question avec multi-agents

```
Utilisateur: "Parlez-moi de la Faculté des Sciences et Techniques"
    │
    ▼
1. route_to_faculty_agent() détecte "Faculté des Sciences et Techniques"
    │
    ├─→ detect_structure_in_text() trouve "FAST"
    │
    ▼
2. Routage vers "fast_agent"
    │
    ▼
3. fast_agent recherche spécifiquement pour FAST
    │
    ├─→ Prompt spécialisé FAST
    │
    ▼
4. Génération réponse avec expertise FAST
    │
    ▼
5. Réponse spécialisée retournée
```

---

## 🎨 Comment modifier le code

### Modification 1 : Changer le prompt système

**Fichier** : `agent_uam.py`  
**Ligne** : ~620

```python
# AVANT
system_prompt = """Tu es l'assistant virtuel officiel de l'UAM.
CONSIGNES :
- Réponds de manière claire...
"""

# APRÈS (votre modification)
system_prompt = """Tu es l'assistant virtuel officiel de l'UAM.
CONSIGNES :
- Réponds de manière claire...
- NOUVELLE CONSIGNE : Toujours mentionner les contacts
- NOUVELLE CONSIGNE : Inclure des exemples concrets
"""
```

### Modification 2 : Ajouter un nouvel outil

**Fichier** : `agent_uam.py`  
**Ligne** : Après les autres outils (~650)

```python
@tool
def get_contact_info(service: str) -> str:
    """
    Obtient les informations de contact d'un service.
    
    Args:
        service: Nom du service (ex: "scolarité", "bibliothèque")
        
    Returns:
        Informations de contact
    """
    # Votre logique ici
    contacts = {
        "scolarité": "Tel: 20 73 20 00",
        "bibliothèque": "Tel: 20 73 21 00"
    }
    return contacts.get(service.lower(), "Contact non trouvé")
```

**Puis ajouter à `get_tools()`** :

```python
def get_tools():
    return [
        # ... outils existants ...
        get_contact_info  # ← Nouvel outil
    ]
```

### Modification 3 : Améliorer la détection de structures

**Fichier** : `agent_uam.py`  
**Ligne** : ~80-180 (section `UAM_STRUCTURES`)

```python
# Ajouter plus de variantes pour améliorer la détection
"FAST": {
    "nom_complet": "Faculté des Sciences et Techniques",
    "variantes": [
        # Variantes existantes...
        "sciences techniques",  # ← Nouvelle variante
        "fast uam",             # ← Nouvelle variante
        "faculté sciences"      # ← Nouvelle variante
    ]
}
```

### Modification 4 : Personnaliser l'interface Streamlit

**Fichier** : `app_streamlit.py`

**Ajouter un widget** :

```python
# Dans la sidebar, après les autres widgets
st.subheader("🎨 Personnalisation")

theme = st.selectbox(
    "Thème",
    ["Clair", "Sombre", "Auto"],
    index=0
)

font_size = st.slider("Taille de police", 10, 20, 14)
```

---

## 🧪 Tester vos modifications

### Test unitaire d'un outil

**Créer** : `test_tools.py`

```python
from agent_uam import calculate_fees, get_structure_info

# Test calculate_fees
result = calculate_fees.invoke({"level": "licence", "faculty": "FAST"})
print(f"Test calculate_fees: {result}")

# Test get_structure_info
info = get_structure_info("FAST")
print(f"Test get_structure_info: {info}")
```

**Exécuter** :
```bash
python test_tools.py
```

### Test du graphe complet

**Créer** : `test_graph.py`

```python
from agent_uam import (
    initialize_llm, LLMProvider,
    load_and_index_documents,
    create_agent_graph
)
from langchain_core.messages import HumanMessage

# Initialiser
llm = initialize_llm(LLMProvider.LLAMA_GROQ)
vectorstore = load_and_index_documents("./documents_uam", LLMProvider.LLAMA_GROQ)
agent = create_agent_graph(vectorstore, llm)

# Tester
state = {
    "messages": [HumanMessage(content="Quelles formations à la FAST ?")],
    "question": "Quelles formations à la FAST ?",
    "is_relevant": False,
    "context": "",
    "response": "",
    "need_clarification": False,
    "user_id": "test_user",
    "user_preferences": {}
}

config = {"configurable": {"thread_id": "test_thread"}}
result = agent.invoke(state, config)
print(f"Réponse: {result.get('response', 'Pas de réponse')}")
```

### Test de l'interface Streamlit

```bash
streamlit run app_streamlit.py
```

Puis tester manuellement dans le navigateur.

---

## 🐛 Déboguer

### Activer les logs détaillés

**Ajouter au début de `agent_uam.py`** :

```python
import logging

# Configurer le logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

**Utiliser dans le code** :

```python
logger.debug(f"État actuel: {state}")
logger.info(f"Routage vers: {next_node}")
logger.error(f"Erreur: {e}")
```

### Ajouter des points de contrôle

```python
def call_model(state: AgentState, llm_with_tools) -> AgentState:
    # Point de contrôle
    print(f"🔍 DEBUG: call_model appelé avec {len(state['messages'])} messages")
    
    messages = state["messages"]
    # ... reste du code ...
    
    print(f"🔍 DEBUG: Réponse générée: {response[:100]}...")
    return {...}
```

### Vérifier les variables d'environnement

```python
import os
print(f"GROQ_API_KEY présente: {bool(os.getenv('GROQ_API_KEY'))}")
print(f"Valeur: {os.getenv('GROQ_API_KEY', 'NON TROUVÉE')[:20]}...")
```

---

## 📦 Ajouter une dépendance

### 1. Ajouter au requirements.txt

```txt
# Nouvelle dépendance
nouvelle-bibliotheque>=1.0.0
```

### 2. Installer

```bash
pip install nouvelle-bibliotheque
```

### 3. Importer dans le code

```python
from nouvelle_bibliotheque import MaClasse
```

---

## 🔄 Workflow de développement recommandé

### 1. Créer une branche de développement

```bash
git checkout -b feature/ma-nouvelle-fonctionnalite
```

### 2. Faire des modifications incrémentales

- Modifier une petite partie à la fois
- Tester après chaque modification
- Commit fréquent avec messages clairs

### 3. Tester avant de commit

```bash
# Test unitaire
python test_tools.py

# Test intégration
python test_graph.py

# Test interface
streamlit run app_streamlit.py
```

### 4. Documenter les changements

- Mettre à jour `FEATURES.md` si nouvelle fonctionnalité
- Mettre à jour `README.md` si changement majeur
- Ajouter des commentaires dans le code

---

## 🎓 Exemples concrets d'améliorations

### Exemple 1 : Ajouter un système de notation

**Objectif** : Permettre à l'utilisateur de noter les réponses

**Modification** :

1. **Ajouter dans `app_streamlit.py`** :

```python
# Après chaque réponse
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("👍 Utile"):
        # Sauvegarder la notation
        _user_memory.save_user_preference(
            st.session_state.user_id,
            f"rating_{len(st.session_state.conversation_history)}",
            "useful"
        )
with col2:
    if st.button("👎 Pas utile"):
        _user_memory.save_user_preference(
            st.session_state.user_id,
            f"rating_{len(st.session_state.conversation_history)}",
            "not_useful"
        )
```

### Exemple 2 : Ajouter un système de suggestions

**Objectif** : Suggérer des questions similaires

**Modification** :

```python
@tool
def suggest_similar_questions(question: str) -> str:
    """
    Suggère des questions similaires basées sur l'historique.
    """
    # Rechercher dans l'historique des conversations
    # Retourner des suggestions
    suggestions = [
        "Quelles sont les conditions d'admission ?",
        "Comment s'inscrire ?",
        "Quels sont les frais de scolarité ?"
    ]
    return "Questions suggérées:\n" + "\n".join(f"- {s}" for s in suggestions)
```

### Exemple 3 : Ajouter un système de cache

**Objectif** : Éviter de recalculer les mêmes réponses

**Modification** :

```python
from functools import lru_cache
import hashlib

# Cache pour les recherches
@lru_cache(maxsize=100)
def cached_search(query: str) -> str:
    """Recherche avec cache"""
    if _vectorstore is None:
        return "Erreur"
    docs = _vectorstore.similarity_search(query, k=4)
    return "\n\n---\n\n".join([doc.page_content for doc in docs])

@tool
def search_uam_knowledge(query: str) -> str:
    """Version avec cache"""
    return cached_search(query)
```

---

## 📝 Checklist pour une nouvelle fonctionnalité

- [ ] Comprendre le besoin utilisateur
- [ ] Identifier où modifier le code
- [ ] Créer un script de test
- [ ] Implémenter la fonctionnalité
- [ ] Tester unitairement
- [ ] Tester l'intégration
- [ ] Documenter dans FEATURES.md
- [ ] Mettre à jour README.md si nécessaire
- [ ] Vérifier la compatibilité avec les autres fonctionnalités
- [ ] Commit avec message descriptif

---

## 🚨 Erreurs courantes et solutions

### Erreur : "Module not found"

**Solution** :
```bash
pip install -r requirements.txt
```

### Erreur : "API key not found"

**Solution** :
1. Vérifier que `.env` existe
2. Vérifier le format : `GROQ_API_KEY=votre_cle`
3. Redémarrer l'application

### Erreur : "Vectorstore is None"

**Solution** :
- Vérifier que `set_vectorstore()` est appelé avant d'utiliser les outils
- Vérifier que les documents sont chargés

### Erreur : "Tool not found"

**Solution** :
- Vérifier que l'outil est dans `get_tools()`
- Vérifier que `bind_tools()` inclut tous les outils

---

## 💡 Conseils pour bien développer

1. **Lire d'abord** : Comprendre le code existant avant de modifier
2. **Tester souvent** : Tester après chaque petite modification
3. **Documenter** : Commenter votre code et mettre à jour la doc
4. **Rester modulaire** : Garder les fonctions petites et focalisées
5. **Gérer les erreurs** : Toujours gérer les cas d'erreur
6. **Versionner** : Utiliser Git pour suivre les changements

---

## 🎯 Prochaines étapes suggérées

1. **Explorer le code** : Lire `agent_uam.py` en entier
2. **Tester manuellement** : Lancer l'application et tester
3. **Faire une petite modification** : Ajouter un outil simple
4. **Comprendre LangGraph** : Lire la doc officielle
5. **Expérimenter** : Essayer différentes configurations

---

**Bon développement ! 🚀**


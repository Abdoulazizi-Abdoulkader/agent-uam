# 📖 Explication Simple du Fonctionnement

## 🎯 En résumé

L'application est un **chatbot intelligent** qui répond aux questions sur l'Université UAM en utilisant :
- Des **documents PDF/TXT** comme base de connaissances
- Un **modèle de langage (LLM)** pour comprendre et répondre
- Un **système de graphe (LangGraph)** pour orchestrer les réponses
- Des **outils spécialisés** pour des tâches précises

---

## 🔄 Comment ça marche ? (Version simple)

```
1. Vous posez une question
   ↓
2. L'agent vérifie si c'est pertinent (sur l'UAM)
   ↓
3. Si pertinent → L'agent cherche dans les documents
   ↓
4. L'agent utilise le LLM pour générer une réponse
   ↓
5. Vous recevez la réponse
```

---

## 🏗️ Architecture en 3 couches

### Couche 1 : Interface (Ce que vous voyez)
- **Streamlit** : Interface web avec chat
- **Console** : Mode texte simple

### Couche 2 : Intelligence (Le cerveau)
- **LangGraph** : Orchestre les étapes
- **LLM** : Comprend et génère du texte
- **Outils** : Fonctions spécialisées (recherche, calcul, etc.)

### Couche 3 : Données (La mémoire)
- **FAISS** : Base de données vectorielle (documents)
- **JSON** : Mémoire utilisateur (préférences)
- **Python Dict** : Connaissances structurées (facultés)

---

## 📝 Exemple concret : "Quelles formations à la FAST ?"

### Étape par étape :

1. **Vous tapez** : "Quelles formations à la FAST ?"
   ```
   Interface → agent_uam.py
   ```

2. **L'agent route la question** :
   ```python
   route_question() détecte "FAST" → Route vers agent principal
   ```

3. **Le LLM décide d'utiliser un outil** :
   ```python
   LLM: "Je dois chercher des informations sur les formations FAST"
   → Appelle search_uam_knowledge("formations FAST")
   ```

4. **L'outil recherche dans les documents** :
   ```python
   search_uam_knowledge() 
   → Cherche dans FAISS vectorstore
   → Trouve des documents pertinents
   → Retourne le contexte
   ```

5. **Le LLM génère la réponse** :
   ```python
   LLM reçoit le contexte
   → Génère une réponse claire et structurée
   → "La FAST propose les formations suivantes..."
   ```

6. **Vous recevez la réponse** :
   ```
   Interface ← Réponse générée
   ```

---

## 🛠️ Les outils disponibles

L'agent a accès à plusieurs "outils" (fonctions spécialisées) :

| Outil | Ce qu'il fait | Exemple d'utilisation |
|-------|---------------|------------------------|
| `search_uam_knowledge` | Cherche dans les documents | "Recherche informations sur les inscriptions" |
| `calculate_fees` | Calcule les frais | "Combien coûte une licence ?" |
| `search_formations` | Trouve les formations | "Quelles formations en Master ?" |
| `get_faculty_info` | Infos sur une faculté | "Parlez-moi de la FAST" |
| `get_structure_by_abbreviation` | Nom complet depuis abréviation | "FAST = ?" |
| `list_all_structures` | Liste toutes les structures | "Quelles sont les facultés ?" |

**Important** : Le LLM décide **automatiquement** quel outil utiliser !

---

## 🤖 Système Multi-Agents

### Concept

Au lieu d'un seul agent général, il y a **7 agents spécialisés** + 1 général :

```
Question sur FAST → Agent FAST (spécialisé sciences)
Question sur FLSH → Agent FLSH (spécialisé lettres)
Question générale → Agent Général
```

### Avantage

Chaque agent a un **prompt spécialisé** et connaît mieux son domaine.

---

## 💾 Mémoire à long terme

### Ce qui est sauvegardé

1. **Préférences utilisateur** :
   - Faculté d'intérêt
   - Niveau d'étude
   - Autres préférences

2. **Historique des conversations** :
   - Toutes les questions/réponses
   - Avec timestamps

### Où c'est stocké

- **Fichier** : `user_memory.json`
- **Format** : JSON structuré
- **Persistance** : Entre les sessions

---

## 🎨 Comment améliorer l'application

### Niveau 1 : Modifications simples

#### Ajouter un nouvel outil

**Fichier** : `agent_uam.py` (ligne ~650)

```python
@tool
def mon_nouvel_outil(param: str) -> str:
    """Description de l'outil"""
    # Votre code ici
    return "Résultat"

# Puis ajouter à get_tools()
def get_tools():
    return [
        # ... outils existants ...
        mon_nouvel_outil  # ← Ajouter ici
    ]
```

#### Modifier le prompt

**Fichier** : `agent_uam.py` (ligne ~620)

```python
system_prompt = """Tu es l'assistant virtuel officiel de l'UAM.

CONSIGNES :
- Réponds de manière claire...
- NOUVELLE CONSIGNE : [Votre nouvelle consigne]
"""
```

### Niveau 2 : Modifications moyennes

#### Ajouter une nouvelle structure

**Fichier** : `agent_uam.py` (ligne ~80)

```python
UAM_STRUCTURES = {
    "facultes": {
        # ... structures existantes ...
        "NOUVELLE": {
            "nom_complet": "Nouvelle Faculté",
            "variantes": ["nouvelle", "NOUVELLE"]
        }
    }
}
```

#### Ajouter un nouvel agent

**Fichier** : `multi_agents.py`

1. Ajouter dans `FACULTIES`
2. Ajouter dans `route_to_faculty_agent()`
3. Créer l'agent avec `create_faculty_agent()`

### Niveau 3 : Modifications avancées

#### Changer le système de mémoire

Remplacer `UserMemory` (JSON) par une base de données :
- SQLite (simple)
- PostgreSQL (avancé)

#### Ajouter une API REST

Créer `api.py` avec FastAPI :
```python
from fastapi import FastAPI
app = FastAPI()

@app.post("/chat")
def chat(message: str):
    # Utiliser l'agent
    return {"response": "..."}
```

---

## 📍 Où modifier quoi ?

| Ce que vous voulez modifier | Fichier | Ligne approximative |
|----------------------------|---------|-------------------|
| Ajouter un outil | `agent_uam.py` | ~650 |
| Modifier le prompt | `agent_uam.py` | ~620 |
| Ajouter une structure | `agent_uam.py` | ~80 |
| Changer le routage | `agent_uam.py` | ~570 |
| Ajouter un agent | `multi_agents.py` | ~50 |
| Modifier l'interface | `app_streamlit.py` | Partout |
| Changer l'export | `export_utils.py` | Partout |
| Modifier la mémoire | `agent_uam.py` | ~520 |

---

## 🧪 Tester vos modifications

### Test rapide d'un outil

```python
# test.py
from agent_uam import mon_nouvel_outil

result = mon_nouvel_outil.invoke({"param": "test"})
print(result)
```

### Test du graphe complet

```python
# test_complet.py
from agent_uam import initialize_llm, LLMProvider, load_and_index_documents, create_agent_graph

llm = initialize_llm(LLMProvider.LLAMA_GROQ)
vectorstore = load_and_index_documents("./documents_uam", LLMProvider.LLAMA_GROQ)
agent = create_agent_graph(vectorstore, llm)

# Tester avec une question
state = {"messages": [HumanMessage(content="Test")], ...}
result = agent.invoke(state, config)
print(result)
```

---

## 🎓 Par où commencer ?

### Si vous êtes débutant

1. **Lire** : `EXPLICATION.md` (ce fichier)
2. **Explorer** : Ouvrir `agent_uam.py` et lire les commentaires
3. **Tester** : Lancer l'application et poser des questions
4. **Modifier** : Changer un petit détail (ex: un message)
5. **Tester** : Vérifier que ça fonctionne

### Si vous êtes expérimenté

1. **Lire** : `ARCHITECTURE.md` pour comprendre l'architecture
2. **Lire** : `DEVELOPMENT_GUIDE.md` pour le guide de développement
3. **Identifier** : Ce que vous voulez améliorer
4. **Implémenter** : Faire les modifications
5. **Tester** : Vérifier que tout fonctionne

---

## 💡 Idées d'améliorations

### Faciles (1-2 heures)

- ✅ Ajouter plus de variantes dans `UAM_STRUCTURES`
- ✅ Modifier les messages d'accueil
- ✅ Ajouter des emojis dans les réponses
- ✅ Changer les couleurs de l'interface Streamlit

### Moyennes (1 journée)

- ✅ Ajouter un nouvel outil (ex: calcul de moyenne)
- ✅ Améliorer la détection de structures
- ✅ Ajouter un système de feedback (👍/👎)
- ✅ Créer un système de suggestions de questions

### Avancées (plusieurs jours)

- ✅ Remplacer JSON par base de données
- ✅ Ajouter authentification utilisateur
- ✅ Créer une API REST
- ✅ Ajouter support multilingue
- ✅ Intégrer avec calendrier/événements

---

## 📚 Documentation complète

Pour aller plus loin :

- **[ARCHITECTURE.md](ARCHITECTURE.md)** : Architecture détaillée avec diagrammes
- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** : Guide complet de développement
- **[FEATURES.md](FEATURES.md)** : Détails des fonctionnalités
- **[README.md](README.md)** : Documentation principale

---

## ❓ Questions fréquentes

### Q: Comment l'agent sait-il quelle réponse donner ?

**R** : Il combine :
1. La recherche dans les documents (FAISS)
2. Les connaissances structurées (UAM_STRUCTURES)
3. L'intelligence du LLM pour générer une réponse naturelle

### Q: Comment ajouter de nouveaux documents ?

**R** : Simplement ajouter des fichiers PDF ou TXT dans `documents_uam/`. Au prochain démarrage, ils seront automatiquement chargés.

### Q: Comment changer le modèle LLM ?

**R** : Dans `agent_uam.py` ligne ~1240, changer :
```python
PROVIDER = LLMProvider.LLAMA_GROQ  # ou OPENAI, CLAUDE, etc.
MODEL_NAME = "llama-3.3-70b-versatile"  # ou autre modèle
```

### Q: Comment améliorer les réponses ?

**R** : 
1. Améliorer les documents sources (plus d'infos = meilleures réponses)
2. Modifier le prompt système (ligne ~620)
3. Ajouter plus d'outils spécialisés

---

**Vous êtes maintenant prêt à comprendre et améliorer l'application ! 🚀**


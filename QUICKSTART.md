# 🚀 Guide de Démarrage Rapide - Agent UAM

## Installation Rapide

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Configurer les clés API (créer un fichier .env)
echo "GROQ_API_KEY=votre_cle_ici" > .env

# 3. Lancer l'interface Streamlit
streamlit run app_streamlit.py
```

## Utilisation de Base

### Mode Console (CLI)

```bash
python agent_uam.py
```

### Mode Interface Web (Streamlit)

```bash
streamlit run app_streamlit.py
```

Puis ouvrez votre navigateur sur `http://localhost:8501`

## Fonctionnalités Principales

### 1. 💾 Mémoire à Long Terme

L'agent se souvient automatiquement de vos préférences :
- Faculté d'intérêt
- Niveau d'étude
- Autres préférences personnalisées

### 2. 🛠️ Outils Spécialisés

L'agent peut :
- Calculer les frais de scolarité
- Rechercher des formations
- Obtenir des informations sur les facultés

### 3. 🌐 Interface Moderne

Interface web avec :
- Chat en temps réel
- Historique des conversations
- Export JSON/PDF
- Configuration avancée

### 4. 📄 Export

Exportez vos conversations :
- Format JSON (données structurées)
- Format PDF (document formaté)

### 5. 🤖 Multi-Agents

Agents spécialisés par faculté pour des réponses plus précises.

## Exemples de Questions

```
"Quelles sont les filières disponibles à la Faculté des Sciences ?"
"Combien coûtent les frais de scolarité pour une licence ?"
"Quelles sont les conditions d'admission en Master à la FAST ?"
"Comment s'inscrire à l'UAM ?"
```

## Configuration

### Providers LLM Supportés

- **Groq** (recommandé) : Rapide et gratuit jusqu'à un quota
- **OpenAI** : GPT-4o
- **Claude** : Anthropic Claude Sonnet 4
- **Ollama** : Modèles locaux

### Changer de Provider

Dans `app_streamlit.py` ou via l'interface web, sélectionnez le provider dans la sidebar.

## Dépannage

### Erreur : "Module not found"
```bash
pip install -r requirements.txt
```

### Erreur : "API key not found"
Vérifiez que votre fichier `.env` contient la bonne clé API.

### Erreur : "Documents not found"
Assurez-vous que le dossier `documents_uam/` contient des fichiers PDF ou TXT.

## Support

Pour plus d'informations, consultez :
- `README.md` : Documentation complète
- `FEATURES.md` : Détails des fonctionnalités
- `requirements.txt` : Liste des dépendances


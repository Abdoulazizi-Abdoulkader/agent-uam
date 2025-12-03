#!/bin/bash

# Script de configuration rapide pour l'Agent UAM avec Groq
# Pour Windows, utilisez Git Bash ou WSL

echo "🎓 Configuration de l'Agent Conversationnel UAM"
echo "================================================"
echo ""

# Couleurs pour le terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Étape 1 : Vérifier Python
echo -e "${YELLOW}Étape 1/6 : Vérification de Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    echo -e "${GREEN}✓ Python trouvé : $(python3 --version)${NC}"
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
    echo -e "${GREEN}✓ Python trouvé : $(python --version)${NC}"
else
    echo -e "${RED}✗ Python n'est pas installé. Installez Python 3.8+${NC}"
    exit 1
fi
echo ""

# Étape 2 : Créer l'environnement virtuel
echo -e "${YELLOW}Étape 2/6 : Création de l'environnement virtuel...${NC}"
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo -e "${GREEN}✓ Environnement virtuel créé${NC}"
else
    echo -e "${GREEN}✓ Environnement virtuel déjà existant${NC}"
fi
echo ""

# Étape 3 : Activer l'environnement
echo -e "${YELLOW}Étape 3/6 : Activation de l'environnement...${NC}"
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi
echo -e "${GREEN}✓ Environnement activé${NC}"
echo ""

# Étape 4 : Installer les dépendances
echo -e "${YELLOW}Étape 4/6 : Installation des dépendances...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Dépendances installées${NC}"
else
    echo -e "${RED}✗ Erreur lors de l'installation${NC}"
    exit 1
fi
echo ""

# Étape 5 : Créer la structure
echo -e "${YELLOW}Étape 5/6 : Création de la structure du projet...${NC}"

# Créer le dossier documents
if [ ! -d "documents_uam" ]; then
    mkdir documents_uam
    echo -e "${GREEN}✓ Dossier documents_uam/ créé${NC}"
    echo -e "${YELLOW}  ⚠️  Placez vos PDFs dans ce dossier${NC}"
else
    echo -e "${GREEN}✓ Dossier documents_uam/ existe${NC}"
    PDF_COUNT=$(ls -1 documents_uam/*.pdf 2>/dev/null | wc -l)
    if [ $PDF_COUNT -eq 0 ]; then
        echo -e "${YELLOW}  ⚠️  Aucun PDF trouvé. Ajoutez vos documents${NC}"
    else
        echo -e "${GREEN}  ✓ $PDF_COUNT PDF(s) trouvé(s)${NC}"
    fi
fi

# Créer le fichier .env si nécessaire
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}  Configuration de la clé API Groq...${NC}"
    echo ""
    echo "  Pour obtenir votre clé gratuite :"
    echo "  1. Allez sur https://console.groq.com/"
    echo "  2. Créez un compte (gratuit)"
    echo "  3. Générez une API Key"
    echo ""
    read -p "  Entrez votre clé Groq (gsk_...): " GROQ_KEY
    
    if [ -n "$GROQ_KEY" ]; then
        echo "GROQ_API_KEY=$GROQ_KEY" > .env
        echo -e "${GREEN}  ✓ Clé API sauvegardée dans .env${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Pas de clé fournie. Créez manuellement le fichier .env${NC}"
    fi
else
    echo -e "${GREEN}✓ Fichier .env existe${NC}"
fi
echo ""

# Étape 6 : Vérification finale
echo -e "${YELLOW}Étape 6/6 : Vérification de la configuration...${NC}"

CHECKS_PASSED=true

# Vérifier le fichier .env
if [ -f ".env" ] && grep -q "GROQ_API_KEY" .env; then
    echo -e "${GREEN}✓ Clé API Groq configurée${NC}"
else
    echo -e "${RED}✗ Clé API manquante dans .env${NC}"
    CHECKS_PASSED=false
fi

# Vérifier les PDFs
PDF_COUNT=$(ls -1 documents_uam/*.pdf 2>/dev/null | wc -l)
if [ $PDF_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Documents PDF présents ($PDF_COUNT fichier(s))${NC}"
else
    echo -e "${YELLOW}⚠️  Aucun PDF dans documents_uam/${NC}"
    CHECKS_PASSED=false
fi

# Vérifier le script principal
if [ -f "agent_uam.py" ]; then
    echo -e "${GREEN}✓ Script agent_uam.py présent${NC}"
else
    echo -e "${RED}✗ Script agent_uam.py manquant${NC}"
    CHECKS_PASSED=false
fi

echo ""
echo "================================================"

if [ "$CHECKS_PASSED" = true ]; then
    echo -e "${GREEN}✅ Configuration terminée avec succès !${NC}"
    echo ""
    echo "Pour lancer l'agent :"
    echo "  1. Activez l'environnement : source venv/bin/activate"
    echo "  2. Mode console : python agent_uam.py"
    echo "  3. Mode interface web : streamlit run app_streamlit.py"
    echo ""
    
    # Proposer de lancer directement
    read -p "Voulez-vous lancer l'agent maintenant ? (o/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[OoYy]$ ]]; then
        echo ""
        echo "Choisissez le mode :"
        echo "  1) Console (CLI)"
        echo "  2) Interface Web (Streamlit)"
        read -p "Votre choix (1 ou 2) : " MODE_CHOICE
        echo ""
        if [ "$MODE_CHOICE" = "2" ]; then
            echo "🚀 Lancement de l'interface Streamlit..."
            echo "   Ouvrez http://localhost:8501 dans votre navigateur"
            echo ""
            streamlit run app_streamlit.py
        else
            echo "🚀 Lancement de l'agent en mode console..."
            echo ""
            $PYTHON_CMD agent_uam.py
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Configuration incomplète${NC}"
    echo ""
    echo "Actions nécessaires :"
    [ ! -f ".env" ] && echo "  - Créez le fichier .env avec votre GROQ_API_KEY"
    [ $PDF_COUNT -eq 0 ] && echo "  - Ajoutez des PDFs dans documents_uam/"
    [ ! -f "agent_uam.py" ] && echo "  - Créez le fichier agent_uam.py avec le code fourni"
    echo ""
fi
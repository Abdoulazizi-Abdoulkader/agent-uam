#!/bin/bash
# Script pour lancer l'interface Streamlit

echo "🚀 Lancement de l'interface Streamlit pour l'Agent UAM..."
echo ""

# Vérifier que Streamlit est installé
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit n'est pas installé."
    echo "Installez-le avec: pip install streamlit"
    exit 1
fi

# Lancer Streamlit
streamlit run app_streamlit.py --server.port 8501 --server.address localhost


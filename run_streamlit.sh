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

# Vérifier la limite inotify
CURRENT_WATCHES=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo "0")
if [ "$CURRENT_WATCHES" -lt 100000 ]; then
    echo "⚠️  Attention: La limite inotify est faible ($CURRENT_WATCHES watches)"
    echo "   Cela peut causer des erreurs 'inotify watch limit reached'"
    echo ""
    echo "💡 Pour corriger ce problème, exécutez:"
    echo "   sudo ./fix_inotify_limit.sh"
    echo ""
    echo "   Ou manuellement:"
    echo "   sudo sysctl fs.inotify.max_user_watches=524288"
    echo "   sudo sysctl fs.inotify.max_user_instances=512"
    echo ""
    read -p "Continuer quand même? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
    echo ""
fi

# Lancer Streamlit
streamlit run app_streamlit.py --server.port 8501 --server.address localhost


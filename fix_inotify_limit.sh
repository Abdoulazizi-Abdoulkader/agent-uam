#!/bin/bash
# Script pour augmenter la limite inotify (nécessite sudo)

echo "🔧 Configuration de la limite inotify pour Streamlit..."
echo ""

# Vérifier les limites actuelles
CURRENT_WATCHES=$(cat /proc/sys/fs/inotify/max_user_watches)
CURRENT_INSTANCES=$(cat /proc/sys/fs/inotify/max_user_instances)

echo "Limites actuelles:"
echo "  - max_user_watches: $CURRENT_WATCHES"
echo "  - max_user_instances: $CURRENT_INSTANCES"
echo ""

# Augmenter temporairement (pour la session actuelle)
echo "📝 Augmentation temporaire des limites..."
sudo sysctl fs.inotify.max_user_watches=524288
sudo sysctl fs.inotify.max_user_instances=512

# Vérifier si le fichier sysctl.conf existe et contient déjà ces valeurs
SYSCTL_FILE="/etc/sysctl.conf"
if [ -f "$SYSCTL_FILE" ]; then
    if grep -q "fs.inotify.max_user_watches" "$SYSCTL_FILE"; then
        echo "⚠️  La configuration existe déjà dans $SYSCTL_FILE"
        echo "   Vérifiez les valeurs avec: cat $SYSCTL_FILE | grep inotify"
    else
        echo "📝 Ajout de la configuration permanente dans $SYSCTL_FILE..."
        echo "" | sudo tee -a "$SYSCTL_FILE" > /dev/null
        echo "# Augmentation de la limite inotify pour Streamlit et autres outils" | sudo tee -a "$SYSCTL_FILE" > /dev/null
        echo "fs.inotify.max_user_watches=524288" | sudo tee -a "$SYSCTL_FILE" > /dev/null
        echo "fs.inotify.max_user_instances=512" | sudo tee -a "$SYSCTL_FILE" > /dev/null
        echo "✅ Configuration permanente ajoutée"
    fi
else
    echo "⚠️  Le fichier $SYSCTL_FILE n'existe pas, création..."
    echo "# Configuration inotify" | sudo tee "$SYSCTL_FILE" > /dev/null
    echo "fs.inotify.max_user_watches=524288" | sudo tee -a "$SYSCTL_FILE" > /dev/null
    echo "fs.inotify.max_user_instances=512" | sudo tee -a "$SYSCTL_FILE" > /dev/null
    echo "✅ Configuration permanente créée"
fi

echo ""
echo "✅ Limites mises à jour:"
echo "  - max_user_watches: $(cat /proc/sys/fs/inotify/max_user_watches)"
echo "  - max_user_instances: $(cat /proc/sys/fs/inotify/max_user_instances)"
echo ""
echo "💡 Note: Les changements permanents prendront effet au prochain redémarrage."
echo "   Pour appliquer immédiatement sans redémarrer, exécutez:"
echo "   sudo sysctl -p"


#!/usr/bin/env bash
#
# Lance le site web de l'UAM avec l'assistant intégré.
#
#   ./run_api.sh              → http://localhost:8000
#   ./run_api.sh 9000         → autre port
#
# Un seul worker volontairement : chaque worker chargerait sa propre copie du
# modèle d'embeddings HuggingFace (~1 Go de RAM).

set -euo pipefail

cd "$(dirname "$0")"

PORT="${1:-8000}"

if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

if [ ! -f ".env" ]; then
  echo "❌ Fichier .env manquant — la clé OPENROUTER_API_KEY est requise." >&2
  exit 1
fi

echo "🎓 Université Abdou Moumouni — démarrage du serveur"
echo "   Chargement du modèle d'embeddings et de l'index FAISS (5 à 15 s)…"
echo "   Site : http://localhost:${PORT}"
echo

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT}" --workers 1

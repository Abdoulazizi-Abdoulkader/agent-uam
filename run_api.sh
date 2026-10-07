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

# Deux serveurs sur la même machine chargeraient chacun leur copie du modèle
# d'embeddings (~1 Go) et se disputeraient le CPU — c'est arrivé le 28/08, en
# croyant relancer un service qui ne répondait plus.
if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
  # Le PID est donné explicitement : `pkill -f uvicorn` tuerait aussi le shell
  # depuis lequel la commande est tapée, puisque sa propre ligne de commande
  # contient le motif recherché.
  OCCUPANT="$(ss -ltnp "sport = :${PORT}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
  echo "❌ Un serveur écoute déjà sur le port ${PORT}." >&2
  if [ -n "${OCCUPANT}" ]; then
    echo "   Arrêtez-le : kill ${OCCUPANT}" >&2
  fi
  echo "   Ou choisissez un autre port : ./run_api.sh 9000" >&2
  exit 1
fi

echo "🎓 Université Abdou Moumouni — démarrage du serveur"
echo "   Chargement du modèle d'embeddings et de l'index FAISS (5 à 15 s)…"
echo "   Site : http://localhost:${PORT}"
echo

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT}" --workers 1

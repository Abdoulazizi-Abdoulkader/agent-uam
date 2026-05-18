#!/usr/bin/env bash
# Exécute l'évaluation baseline et agent, puis génère un rapport comparatif.
# Usage : ./run_comparison.sh [--limit N] [--no-ragas]

set -euo pipefail

LIMIT_ARGS=""
RAGAS_ARGS=""
for arg in "$@"; do
    case $arg in
        --limit*) LIMIT_ARGS="$arg" ;;
        --no-ragas) RAGAS_ARGS="--no-ragas" ;;
    esac
done

OUTDIR="./evaluation_results"
mkdir -p "$OUTDIR"

echo "=== Étape 1 : Baseline RAG séquentielle ==="
python evaluate.py --baseline $LIMIT_ARGS $RAGAS_ARGS --output "$OUTDIR"
BASELINE_JSON=$(ls -t "$OUTDIR"/evaluation_complete_*.json | head -1)
cp "$BASELINE_JSON" "$OUTDIR/results_baseline.json"
echo "→ Résultats baseline : $OUTDIR/results_baseline.json"

echo ""
echo "=== Étape 2 : Agent LangGraph ==="
python evaluate.py $LIMIT_ARGS $RAGAS_ARGS --output "$OUTDIR"
AGENT_JSON=$(ls -t "$OUTDIR"/evaluation_complete_*.json | head -1)
cp "$AGENT_JSON" "$OUTDIR/results_agent.json"
echo "→ Résultats agent : $OUTDIR/results_agent.json"

echo ""
echo "=== Étape 3 : Rapport comparatif ==="
python - <<'PYEOF'
import json
from pathlib import Path

base  = json.loads(Path("evaluation_results/results_baseline.json").read_text())
agent = json.loads(Path("evaluation_results/results_agent.json").read_text())

def get(d, *keys, default="N/A"):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return default
        cur = cur.get(k, default)
    return cur

def fmt(v):
    if isinstance(v, float): return f"{v:.4f}"
    return str(v)

lines = [
    "# Rapport comparatif : Baseline RAG vs Agent LangGraph",
    "",
    "| Métrique | Baseline RAG | Agent LangGraph |",
    "|---|---|---|",
    f"| Exactitude classification | {fmt(get(base,'metrics','relevance_classification','accuracy'))} | {fmt(get(agent,'metrics','relevance_classification','accuracy'))} |",
    f"| F1 routage | {fmt(get(base,'metrics','relevance_classification','f1_score'))} | {fmt(get(agent,'metrics','relevance_classification','f1_score'))} |",
    f"| RAGAS faithfulness | {fmt(get(base,'metrics','ragas','faithfulness'))} | {fmt(get(agent,'metrics','ragas','faithfulness'))} |",
    f"| RAGAS answer_relevancy | {fmt(get(base,'metrics','ragas','answer_relevancy'))} | {fmt(get(agent,'metrics','ragas','answer_relevancy'))} |",
    f"| Latence moyenne (ms) | {fmt(get(base,'metrics','performance','response_time_mean_ms'))} | {fmt(get(agent,'metrics','performance','response_time_mean_ms'))} |",
    f"| Latence P90 (ms) | {fmt(get(base,'metrics','performance','response_time_p90_ms'))} | {fmt(get(agent,'metrics','performance','response_time_p90_ms'))} |",
    f"| Longueur moy. réponse (mots) | {fmt(get(base,'metrics','performance','response_length_mean_words'))} | {fmt(get(agent,'metrics','performance','response_length_mean_words'))} |",
    "",
    "> Baseline : retrieve → generate, sans graphe LangGraph ni outils spécialisés.",
    "> Agent : graphe d'états LangGraph + ReAct + ~47 outils @tool + mémoire de session.",
]
report = "\n".join(lines)
Path("COMPARISON_REPORT.md").write_text(report, encoding="utf-8")
print(report)
print("\n→ Rapport écrit dans COMPARISON_REPORT.md")
PYEOF

echo ""
echo "Terminé. Voir COMPARISON_REPORT.md"

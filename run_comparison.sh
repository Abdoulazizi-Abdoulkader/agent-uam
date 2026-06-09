#!/usr/bin/env bash
# Exécute les trois approches d'évaluation, puis génère un rapport comparatif.
#
# Approches comparées :
#   1. LLM seul       — génération directe, sans retrieval ni outils
#   2. RAG séquentielle — retrieve → generate, sans graphe ni outils spécialisés
#   3. Agent LangGraph — graphe d'états + ReAct + ~47 outils @tool + mémoire
#
# Usage : ./run_comparison.sh [--limit N] [--no-ragas]

set -euo pipefail

LIMIT_ARGS=""
RAGAS_ARGS=""
RAGAS_LIMIT_ARGS=""
RAGAS_WORKERS_ARGS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --limit=*)         LIMIT_ARGS="$1";                      shift ;;
        --limit)           LIMIT_ARGS="--limit $2";              shift 2 ;;
        --no-ragas)        RAGAS_ARGS="--no-ragas";              shift ;;
        --ragas-limit=*)   RAGAS_LIMIT_ARGS="$1";                shift ;;
        --ragas-limit)     RAGAS_LIMIT_ARGS="--ragas-limit $2";  shift 2 ;;
        --ragas-workers=*) RAGAS_WORKERS_ARGS="$1";              shift ;;
        --ragas-workers)   RAGAS_WORKERS_ARGS="--ragas-workers $2"; shift 2 ;;
        *)                 shift ;;
    esac
done

OUTDIR="./evaluation_results"
mkdir -p "$OUTDIR"

# ── Étape 1 : LLM seul ────────────────────────────────────────────────────────
echo "=== Étape 1 : LLM seul ==="
python evaluate.py --llm-only $LIMIT_ARGS $RAGAS_ARGS $RAGAS_LIMIT_ARGS $RAGAS_WORKERS_ARGS --output "$OUTDIR"
LLM_JSON=$(ls -t "$OUTDIR"/evaluation_complete_*.json | head -1)
cp "$LLM_JSON" "$OUTDIR/results_llm_only.json"
echo "→ Résultats LLM seul : $OUTDIR/results_llm_only.json"

echo ""
# ── Étape 2 : Baseline RAG séquentielle ──────────────────────────────────────
echo "=== Étape 2 : Baseline RAG séquentielle ==="
python evaluate.py --baseline $LIMIT_ARGS $RAGAS_ARGS $RAGAS_LIMIT_ARGS $RAGAS_WORKERS_ARGS --output "$OUTDIR"
BASELINE_JSON=$(ls -t "$OUTDIR"/evaluation_complete_*.json | head -1)
cp "$BASELINE_JSON" "$OUTDIR/results_baseline.json"
echo "→ Résultats baseline : $OUTDIR/results_baseline.json"

echo ""
# ── Étape 3 : Agent LangGraph ─────────────────────────────────────────────────
echo "=== Étape 3 : Agent LangGraph ==="
python evaluate.py $LIMIT_ARGS $RAGAS_ARGS $RAGAS_LIMIT_ARGS $RAGAS_WORKERS_ARGS --output "$OUTDIR"
AGENT_JSON=$(ls -t "$OUTDIR"/evaluation_complete_*.json | head -1)
cp "$AGENT_JSON" "$OUTDIR/results_agent.json"
echo "→ Résultats agent : $OUTDIR/results_agent.json"

echo ""
# ── Étape 4 : Rapport comparatif ─────────────────────────────────────────────
echo "=== Étape 4 : Rapport comparatif ==="
python - <<'PYEOF'
import json
from pathlib import Path
from datetime import datetime

llm  = json.loads(Path("evaluation_results/results_llm_only.json").read_text())
base = json.loads(Path("evaluation_results/results_baseline.json").read_text())
agnt = json.loads(Path("evaluation_results/results_agent.json").read_text())

def get(d, *keys, default="N/A"):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur

def fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)

def delta(base_val, new_val, higher_better=True):
    """Calcule le delta entre deux valeurs numériques avec signe."""
    if not isinstance(base_val, (int, float)) or not isinstance(new_val, (int, float)):
        return ""
    diff = new_val - base_val
    if diff == 0:
        return " (=)"
    sign = "+" if diff > 0 else ""
    if higher_better:
        color = "↑" if diff > 0 else "↓"
    else:
        color = "↓" if diff > 0 else "↑"
    return f" ({color}{sign}{diff:.4f})"

lines = [
    "# Rapport comparatif : LLM seul vs RAG séquentielle vs Agent LangGraph",
    f"> Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
    "",
    "## Méthodologie",
    "",
    "| Approche | Description |",
    "|---|---|",
    "| **LLM seul** | Génération directe à partir des connaissances du modèle, sans retrieval ni outils |",
    "| **RAG séquentielle** | Retrieve top-4 documents → generate avec contexte, sans graphe ni outils spécialisés |",
    "| **Agent LangGraph** | Graphe d'états + ReAct + ~47 outils @tool + routage + mémoire de session |",
    "",
    "## Résultats comparatifs",
    "",
    "### Classification pertinence / hors-sujet",
    "",
    "| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |",
    "|---|---|---|---|",
    f"| Exactitude | {fmt(get(llm,'metrics','relevance_classification','accuracy'))} | "
    f"{fmt(get(base,'metrics','relevance_classification','accuracy'))} | "
    f"{fmt(get(agnt,'metrics','relevance_classification','accuracy'))} |",
    f"| Précision | {fmt(get(llm,'metrics','relevance_classification','precision'))} | "
    f"{fmt(get(base,'metrics','relevance_classification','precision'))} | "
    f"{fmt(get(agnt,'metrics','relevance_classification','precision'))} |",
    f"| Rappel | {fmt(get(llm,'metrics','relevance_classification','recall'))} | "
    f"{fmt(get(base,'metrics','relevance_classification','recall'))} | "
    f"{fmt(get(agnt,'metrics','relevance_classification','recall'))} |",
    f"| F1-Score | {fmt(get(llm,'metrics','relevance_classification','f1_score'))} | "
    f"{fmt(get(base,'metrics','relevance_classification','f1_score'))} | "
    f"{fmt(get(agnt,'metrics','relevance_classification','f1_score'))} |",
    "",
    "### Qualité des réponses (RAGAS)",
    "",
    "> \\* LLM seul : RAGAS non applicable — Faithfulness et Answer Relevancy mesurent l'ancrage",
    "> dans un contexte récupéré ; sans retrieval, ces métriques sont vides de sens.",
    "",
    "| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |",
    "|---|---|---|---|",
    f"| Faithfulness | \\* — | "
    f"{fmt(get(base,'metrics','ragas','faithfulness'))} | "
    f"{fmt(get(agnt,'metrics','ragas','faithfulness'))} |",
    f"| Answer Relevancy | \\* — | "
    f"{fmt(get(base,'metrics','ragas','answer_relevancy'))} | "
    f"{fmt(get(agnt,'metrics','ragas','answer_relevancy'))} |",
    "",
    "### Ancrage factuel (Keyword Recall)",
    "",
    "| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |",
    "|---|---|---|---|",
    f"| Recall moyen | {fmt(get(llm,'metrics','keyword_recall','mean'))} | "
    f"{fmt(get(base,'metrics','keyword_recall','mean'))} | "
    f"{fmt(get(agnt,'metrics','keyword_recall','mean'))} |",
    "",
    "### Performance système",
    "",
    "| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |",
    "|---|---|---|---|",
    f"| Latence moyenne (ms) | {fmt(get(llm,'metrics','performance','response_time_mean_ms'))} | "
    f"{fmt(get(base,'metrics','performance','response_time_mean_ms'))} | "
    f"{fmt(get(agnt,'metrics','performance','response_time_mean_ms'))} |",
    f"| Latence P90 (ms) | {fmt(get(llm,'metrics','performance','response_time_p90_ms'))} | "
    f"{fmt(get(base,'metrics','performance','response_time_p90_ms'))} | "
    f"{fmt(get(agnt,'metrics','performance','response_time_p90_ms'))} |",
    f"| Longueur moy. réponse (mots) | {fmt(get(llm,'metrics','performance','response_length_mean_words'))} | "
    f"{fmt(get(base,'metrics','performance','response_length_mean_words'))} | "
    f"{fmt(get(agnt,'metrics','performance','response_length_mean_words'))} |",
    f"| Taux d'erreur | {fmt(get(llm,'metrics','performance','error_rate'))} | "
    f"{fmt(get(base,'metrics','performance','error_rate'))} | "
    f"{fmt(get(agnt,'metrics','performance','error_rate'))} |",
    "",
    "## Interprétation",
    "",
    "- **LLM seul → RAG séquentielle** : mesure la contribution du retrieval documentaire",
    "- **RAG séquentielle → Agent LangGraph** : mesure la valeur ajoutée de l'orchestration agentique",
    "  (routage intelligent, outils spécialisés, mémoire de session, gestion des profils utilisateur)",
    "",
    "> LLM seul : génération sans document. "
    "RAG séquentielle : retrieve → generate. "
    "Agent : graphe LangGraph + ReAct + outils + mémoire.",
]

report = "\n".join(lines)
Path("COMPARISON_REPORT.md").write_text(report, encoding="utf-8")
print(report)
print("\n→ Rapport écrit dans COMPARISON_REPORT.md")
PYEOF

echo ""
echo "Terminé. Voir COMPARISON_REPORT.md"

"""
Script d'évaluation automatique du chatbot UAM
Génère toutes les métriques pour le mémoire de Master 2

Usage:
    python evaluate.py                        # évaluation complète
    python evaluate.py --dataset mon_test.csv # dataset personnalisé
    python evaluate.py --limit 10             # seulement 10 questions (test rapide)
    python evaluate.py --no-ragas             # sans RAGAS (plus rapide)
"""

import os
import sys
import csv
import json
import time
import argparse
import warnings
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

warnings.filterwarnings("ignore")

# ── Chargement de l'environnement ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.append(str(Path(__file__).parent))

# ── Imports projet ─────────────────────────────────────────────────────────────
from app_config import LLMProvider
from llm_utils import initialize_llm, initialize_embeddings
from document_loader import load_and_index_documents
from agent_graph import create_agent_graph
from app_config import get_config
from logger_config import get_logger

logger = get_logger(__name__)

# ── Couleurs console ───────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════════
# 1. CHARGEMENT DU DATASET
# ══════════════════════════════════════════════════════════════════════════════

def load_dataset(path: str) -> List[Dict[str, Any]]:
    """Charge le dataset CSV d'évaluation.

    Colonne optionnelle ``mots_cles`` : mots-clés attendus dans la réponse,
    séparés par ``|`` (ex: ``inscription|baccalauréat|dossier``).
    """
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mots_cles_raw = row.get("mots_cles", "").strip()
            mots_cles = (
                [kw.strip() for kw in mots_cles_raw.split("|") if kw.strip()]
                if mots_cles_raw else []
            )
            samples.append({
                "question":          row["question"].strip(),
                "ground_truth":      row.get("ground_truth", "").strip(),
                "category":          row.get("category", "inconnu").strip(),
                "expected_relevant": row.get("expected_relevant", "true").strip().lower() == "true",
                "mots_cles":         mots_cles,
            })
    return samples


# ══════════════════════════════════════════════════════════════════════════════
# 2. EXÉCUTION DE L'AGENT SUR CHAQUE QUESTION
# ══════════════════════════════════════════════════════════════════════════════

def run_agent_on_dataset(
    agent,
    vectorstore,
    samples: List[Dict],
    config: Any,
) -> List[Dict]:
    """Appelle l'agent sur chaque question et collecte les résultats."""
    from langchain_core.messages import HumanMessage
    import uuid

    results = []
    total = len(samples)

    print(f"\n{BOLD}═══ Exécution de l'agent sur {total} questions ═══{RESET}\n")

    for i, sample in enumerate(samples, 1):
        question = sample["question"]
        print(f"[{i:2}/{total}] {question[:70]}{'…' if len(question) > 70 else ''}", end=" ", flush=True)

        thread_id = str(uuid.uuid4())
        # Chaque cycle ReAct = 2 étapes (agent + tools) + routage + réponse finale
        # → limite = iterations * 3 + 10 pour absorber les grands modèles
        run_cfg = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": config.max_tool_iterations * 3 + 10,
        }
        state = {
            "messages":          [HumanMessage(content=question)],
            "question":          question,
            "is_relevant":       False,
            "context":           "",
            "response":          "",
            "need_clarification": False,
            "user_id":           thread_id,
            "user_preferences":  {},
            "tool_iterations":   0,
        }

        t0 = time.perf_counter()
        try:
            result = agent.invoke(state, run_cfg)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            # Extraire la réponse
            response_text = result.get("response", "")
            if not response_text:
                for m in reversed(result.get("messages", [])):
                    if (
                        hasattr(m, "content") and m.content
                        and not getattr(m, "tool_calls", None)
                    ):
                        response_text = m.content
                        break

            # Récupérer les documents contextuels depuis FAISS
            retrieved_docs = []
            try:
                docs = vectorstore.similarity_search(question, k=4)
                retrieved_docs = [d.page_content for d in docs]
            except Exception:
                pass

            actual_relevant = result.get("is_relevant", True)

            print(f"{GREEN}✓{RESET} {elapsed_ms} ms")

            results.append({
                **sample,
                "response":        response_text,
                "actual_relevant": actual_relevant,
                "retrieved_docs":  retrieved_docs,
                "elapsed_ms":      elapsed_ms,
                "error":           None,
            })

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            print(f"{RED}✗ ERREUR : {e}{RESET}")
            results.append({
                **sample,
                "response":        "",
                "actual_relevant": False,
                "retrieved_docs":  [],
                "elapsed_ms":      elapsed_ms,
                "error":           str(e),
            })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 3. MÉTRIQUES DE CLASSIFICATION (PERTINENCE)
# ══════════════════════════════════════════════════════════════════════════════

def compute_relevance_metrics(results: List[Dict]) -> Dict[str, float]:
    """
    Calcule Précision, Rappel, F1 et Exactitude pour la classification
    pertinent / hors-sujet.
    """
    tp = fp = tn = fn = 0
    for r in results:
        exp = r["expected_relevant"]
        act = r["actual_relevant"]
        if exp and act:   tp += 1
        elif not exp and not act: tn += 1
        elif not exp and act:     fp += 1
        elif exp and not act:     fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    accuracy  = (tp + tn) / len(results) if results else 0.0

    return {
        "precision":        round(precision, 4),
        "recall":           round(recall, 4),
        "f1_score":         round(f1, 4),
        "accuracy":         round(accuracy, 4),
        "true_positives":   tp,
        "true_negatives":   tn,
        "false_positives":  fp,
        "false_negatives":  fn,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. MÉTRIQUES ROUGE (qualité du texte généré)
# ══════════════════════════════════════════════════════════════════════════════

def compute_rouge_metrics(results: List[Dict]) -> Dict[str, float]:
    """Calcule ROUGE-1, ROUGE-2 et ROUGE-L sur les questions avec ground_truth."""
    try:
        from rouge_score import rouge_scorer
    except ImportError:
        print(f"  {YELLOW}⚠ rouge-score non installé → pip install rouge-score{RESET}")
        return {}

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
    r1_list, r2_list, rl_list = [], [], []

    for r in results:
        if not r["ground_truth"] or not r["response"] or r["error"]:
            continue
        scores = scorer.score(r["ground_truth"], r["response"])
        r1_list.append(scores["rouge1"].fmeasure)
        r2_list.append(scores["rouge2"].fmeasure)
        rl_list.append(scores["rougeL"].fmeasure)

    if not r1_list:
        return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}

    return {
        "rouge1": round(sum(r1_list) / len(r1_list), 4),
        "rouge2": round(sum(r2_list) / len(r2_list), 4),
        "rougeL": round(sum(rl_list) / len(rl_list), 4),
        "n_evaluated": len(r1_list),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. KEYWORD RECALL (ancrage factuel par mots-clés)
# ══════════════════════════════════════════════════════════════════════════════

def compute_keyword_recall(results: List[Dict]) -> Dict[str, Any]:
    """
    Calcule le keyword recall : proportion de mots-clés attendus présents dans la réponse.

    S'applique uniquement aux entrées du dataset qui disposent d'une colonne
    ``mots_cles`` (liste non vide).  La recherche est insensible à la casse.

    Retourne un dict vide si aucune entrée n'a de mots-clés définis.
    """
    scores: List[float] = []
    per_category: Dict[str, List[float]] = {}

    for r in results:
        mots_cles = r.get("mots_cles", [])
        if not mots_cles or not r.get("response") or r.get("error"):
            continue

        response_lower = r["response"].lower()
        found = sum(1 for kw in mots_cles if kw.lower() in response_lower)
        recall = found / len(mots_cles)
        scores.append(recall)

        cat = r["category"]
        per_category.setdefault(cat, []).append(recall)

    if not scores:
        return {}

    return {
        "mean":         round(sum(scores) / len(scores), 4),
        "min":          round(min(scores), 4),
        "max":          round(max(scores), 4),
        "n_evaluated":  len(scores),
        "per_category": {
            cat: round(sum(v) / len(v), 4) for cat, v in per_category.items()
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. MÉTRIQUES RAGAS (RAG spécifiques)
# ══════════════════════════════════════════════════════════════════════════════

def compute_ragas_metrics(results: List[Dict], llm, embeddings) -> Dict[str, float]:
    """
    Calcule Faithfulness et Answer Relevancy via RAGAS.

    Réutilise le LLM principal du projet pour les appels RAGAS.
    RAGAS nécessite que OPENAI_API_KEY soit définie (même fictive) pour
    initialiser certains composants internes.
    """
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from datasets import Dataset
    except ImportError:
        print(f"  {YELLOW}⚠ ragas/datasets non installés → pip install ragas datasets{RESET}")
        return {}

    # RAGAS cherche OPENAI_API_KEY en interne même avec un LLM personnalisé
    os.environ.setdefault("OPENAI_API_KEY", "sk-ragas-placeholder")

    try:
        ragas_llm = LangchainLLMWrapper(llm)
        ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)
    except Exception as e:
        print(f"  {YELLOW}⚠ Impossible d'initialiser le LLM RAGAS : {e}{RESET}")
        return {}

    valid = [
        r for r in results
        if r["expected_relevant"]
        and r["response"]
        and r["retrieved_docs"]
        and not r["error"]
    ]

    if len(valid) < 3:
        print(f"  {YELLOW}⚠ Pas assez de données valides pour RAGAS ({len(valid)} < 3){RESET}")
        return {}

    data = {
        "question":     [r["question"]       for r in valid],
        "answer":       [r["response"]       for r in valid],
        "contexts":     [r["retrieved_docs"] for r in valid],
        "ground_truth": [r["ground_truth"]   for r in valid],
    }
    dataset = Dataset.from_dict(data)

    try:
        print(f"  Calcul RAGAS sur {len(valid)} exemples…")
        score = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=ragas_llm,
            embeddings=ragas_embeddings,
            raise_exceptions=False,
        )
        # RAGAS 0.2+ renvoie un EvaluationResult — on passe par pandas
        try:
            import pandas as pd
            df = score.to_pandas()
            metric_cols = [c for c in df.columns
                           if c not in ("question", "answer", "contexts", "ground_truth", "reference")]
            out = {}
            for c in metric_cols:
                col_numeric = pd.to_numeric(df[c], errors="coerce").dropna()
                if len(col_numeric) > 0:
                    out[c] = round(float(col_numeric.mean()), 4)
            if not out:
                print(f"  {YELLOW}⚠ RAGAS : toutes les métriques sont NaN (réponses vides ou erreurs LLM){RESET}")
                return {}
            return out
        except AttributeError:
            # RAGAS 0.1 : dict-like direct
            return {k: round(float(v), 4) for k, v in score.items() if v == v}
    except Exception as e:
        print(f"  {RED}Erreur RAGAS : {e}{RESET}")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# 6. MÉTRIQUES DE PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_performance_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Calcule les métriques de temps de réponse et de longueur."""
    valid = [r for r in results if not r["error"]]
    if not valid:
        return {}

    times = [r["elapsed_ms"] for r in valid]
    lengths = [len(r["response"].split()) for r in valid if r["response"]]

    def percentile(lst, p):
        lst_sorted = sorted(lst)
        idx = int(len(lst_sorted) * p / 100)
        return lst_sorted[min(idx, len(lst_sorted) - 1)]

    return {
        "response_time_mean_ms":   round(sum(times) / len(times), 1),
        "response_time_min_ms":    min(times),
        "response_time_max_ms":    max(times),
        "response_time_p50_ms":    percentile(times, 50),
        "response_time_p90_ms":    percentile(times, 90),
        "response_length_mean_words": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "error_rate":              round(len([r for r in results if r["error"]]) / len(results), 4),
        "total_evaluated":         len(results),
        "successful":              len(valid),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. MÉTRIQUES PAR CATÉGORIE
# ══════════════════════════════════════════════════════════════════════════════

def compute_per_category_metrics(results: List[Dict]) -> Dict[str, Dict]:
    """Calcule l'exactitude de classification par catégorie."""
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0, "times": []}
        categories[cat]["total"] += 1
        if r["expected_relevant"] == r["actual_relevant"]:
            categories[cat]["correct"] += 1
        categories[cat]["times"].append(r["elapsed_ms"])

    summary = {}
    for cat, data in categories.items():
        times = data["times"]
        summary[cat] = {
            "total":        data["total"],
            "accuracy":     round(data["correct"] / data["total"], 4),
            "mean_time_ms": round(sum(times) / len(times), 1),
        }
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# 8. AFFICHAGE DU RAPPORT
# ══════════════════════════════════════════════════════════════════════════════

def print_report(
    relevance: Dict,
    rouge: Dict,
    keyword_recall: Dict,
    ragas: Dict,
    performance: Dict,
    per_category: Dict,
):
    sep = "─" * 60

    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}")
    print(f"{BOLD}{BLUE}   RAPPORT D'ÉVALUATION — CHATBOT UAM{RESET}")
    print(f"{BOLD}{BLUE}   {datetime.now().strftime('%d/%m/%Y %H:%M')}{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 60}{RESET}\n")

    # ── Classification pertinence ──────────────────────────────────────────
    print(f"{BOLD}1. CLASSIFICATION PERTINENCE / HORS-SUJET{RESET}")
    print(sep)
    print(f"  Précision        : {BOLD}{relevance['precision']:.4f}{RESET}  ({relevance['precision']*100:.1f}%)")
    print(f"  Rappel           : {BOLD}{relevance['recall']:.4f}{RESET}  ({relevance['recall']*100:.1f}%)")
    print(f"  F1-Score         : {BOLD}{relevance['f1_score']:.4f}{RESET}  ({relevance['f1_score']*100:.1f}%)")
    print(f"  Exactitude       : {BOLD}{relevance['accuracy']:.4f}{RESET}  ({relevance['accuracy']*100:.1f}%)")
    print(f"  TP={relevance['true_positives']}  TN={relevance['true_negatives']}"
          f"  FP={relevance['false_positives']}  FN={relevance['false_negatives']}")

    # ── Keyword Recall ─────────────────────────────────────────────────────
    if keyword_recall:
        print(f"\n{BOLD}2. KEYWORD RECALL (ancrage factuel){RESET}")
        print(sep)
        n = keyword_recall.get("n_evaluated", "?")
        mean = keyword_recall["mean"]
        bar = "█" * int(mean * 20)
        print(f"  Évalué sur {n} questions avec mots-clés définis")
        print(f"  Recall moyen : {BOLD}{mean:.4f}{RESET}  ({mean*100:.1f}%)  |{bar:<20}|")
        print(f"  Min          : {keyword_recall['min']:.4f}   Max : {keyword_recall['max']:.4f}")
        if keyword_recall.get("per_category"):
            print(f"  {'Catégorie':<28} {'Recall':>8}")
            print(f"  {'-'*28} {'-'*8}")
            for cat, val in sorted(keyword_recall["per_category"].items()):
                bar_cat = "█" * int(val * 10)
                print(f"  {cat:<28} {val:.4f}  |{bar_cat:<10}|")
    else:
        print(f"\n{YELLOW}2. KEYWORD RECALL : non calculé (colonne 'mots_cles' absente du CSV){RESET}")

    # ── ROUGE ─────────────────────────────────────────────────────────────
    if rouge:
        print(f"\n{BOLD}3. MÉTRIQUES ROUGE (qualité du texte){RESET}")
        print(sep)
        n = rouge.get("n_evaluated", "?")
        print(f"  Évalué sur {n} questions avec ground_truth")
        print(f"  ROUGE-1  : {BOLD}{rouge.get('rouge1', 0):.4f}{RESET}")
        print(f"  ROUGE-2  : {BOLD}{rouge.get('rouge2', 0):.4f}{RESET}")
        print(f"  ROUGE-L  : {BOLD}{rouge.get('rougeL', 0):.4f}{RESET}")
    else:
        print(f"\n{YELLOW}3. ROUGE : non calculé (rouge-score non installé){RESET}")

    # ── RAGAS ─────────────────────────────────────────────────────────────
    if ragas:
        print(f"\n{BOLD}4. MÉTRIQUES RAGAS (évaluation RAG){RESET}")
        print(sep)
        for metric, val in ragas.items():
            bar = "█" * int(val * 20)
            print(f"  {metric:<25}: {BOLD}{val:.4f}{RESET}  |{bar:<20}|")
    else:
        print(f"\n{YELLOW}4. RAGAS : non calculé (ragas non installé ou données insuffisantes){RESET}")

    # ── Performance ────────────────────────────────────────────────────────
    if performance:
        print(f"\n{BOLD}5. PERFORMANCE SYSTÈME{RESET}")
        print(sep)
        print(f"  Questions évaluées  : {performance['total_evaluated']}")
        print(f"  Réussies            : {performance['successful']}")
        print(f"  Taux d'erreur       : {performance['error_rate']*100:.1f}%")
        print(f"  Temps moyen         : {BOLD}{performance['response_time_mean_ms']} ms{RESET}")
        print(f"  Temps médian (P50)  : {performance['response_time_p50_ms']} ms")
        print(f"  Percentile 90 (P90) : {performance['response_time_p90_ms']} ms")
        print(f"  Longueur moy. réponse: {performance['response_length_mean_words']} mots")

    # ── Par catégorie ──────────────────────────────────────────────────────
    if per_category:
        print(f"\n{BOLD}6. RÉSULTATS PAR CATÉGORIE{RESET}")
        print(sep)
        print(f"  {'Catégorie':<20} {'Total':>6} {'Exactitude':>12} {'Temps moy.':>12}")
        print(f"  {'-'*20} {'-'*6} {'-'*12} {'-'*12}")
        for cat, data in sorted(per_category.items()):
            acc_pct = f"{data['accuracy']*100:.1f}%"
            print(f"  {cat:<20} {data['total']:>6} {acc_pct:>12} {data['mean_time_ms']:>10.0f} ms")

    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════════
# 9. SAUVEGARDE DES RÉSULTATS
# ══════════════════════════════════════════════════════════════════════════════

def save_results(
    results: List[Dict],
    relevance: Dict,
    rouge: Dict,
    keyword_recall: Dict,
    ragas: Dict,
    performance: Dict,
    per_category: Dict,
    output_dir: str = "./evaluation_results",
):
    """Sauvegarde les résultats dans plusieurs formats."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── CSV détaillé (une ligne par question) ──────────────────────────────
    csv_path = out / f"evaluation_detail_{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "question", "category", "expected_relevant", "actual_relevant",
            "correct_classification", "keyword_recall", "response", "ground_truth",
            "elapsed_ms", "response_length_words", "error"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            # Calcul du keyword recall individuel pour ce résultat
            mots_cles = r.get("mots_cles", [])
            if mots_cles and r.get("response") and not r.get("error"):
                found = sum(1 for kw in mots_cles if kw.lower() in r["response"].lower())
                kw_recall = round(found / len(mots_cles), 4)
            else:
                kw_recall = ""
            writer.writerow({
                "question":               r["question"],
                "category":               r["category"],
                "expected_relevant":      r["expected_relevant"],
                "actual_relevant":        r["actual_relevant"],
                "correct_classification": r["expected_relevant"] == r["actual_relevant"],
                "keyword_recall":         kw_recall,
                "response":               r["response"][:500],
                "ground_truth":           r["ground_truth"][:300],
                "elapsed_ms":             r["elapsed_ms"],
                "response_length_words":  len(r["response"].split()) if r["response"] else 0,
                "error":                  r["error"] or "",
            })
    print(f"  ✅ Détail  → {csv_path}")

    # ── CSV résumé des métriques (pour copier dans le mémoire) ────────────
    summary_path = out / f"evaluation_summary_{ts}.csv"
    rows = []
    rows += [("SECTION", "MÉTRIQUE", "VALEUR", "INTERPRÉTATION")]
    rows += [
        ("Classification", "Précision",  f"{relevance.get('precision',0):.4f}", "> 0.80 = bon"),
        ("Classification", "Rappel",     f"{relevance.get('recall',0):.4f}",    "> 0.80 = bon"),
        ("Classification", "F1-Score",   f"{relevance.get('f1_score',0):.4f}",  "> 0.80 = bon"),
        ("Classification", "Exactitude", f"{relevance.get('accuracy',0):.4f}",  "> 0.85 = bon"),
    ]
    if keyword_recall:
        rows += [
            ("Keyword Recall", "Recall moyen", f"{keyword_recall.get('mean',0):.4f}", "> 0.70 = bon"),
            ("Keyword Recall", "Recall min",   f"{keyword_recall.get('min',0):.4f}",  "—"),
            ("Keyword Recall", "Recall max",   f"{keyword_recall.get('max',0):.4f}",  "—"),
        ]
    if rouge:
        rows += [
            ("ROUGE", "ROUGE-1", f"{rouge.get('rouge1',0):.4f}", "> 0.40 = acceptable"),
            ("ROUGE", "ROUGE-2", f"{rouge.get('rouge2',0):.4f}", "> 0.20 = acceptable"),
            ("ROUGE", "ROUGE-L", f"{rouge.get('rougeL',0):.4f}", "> 0.35 = acceptable"),
        ]
    if ragas:
        for k, v in ragas.items():
            rows.append(("RAGAS", k, f"{v:.4f}", "> 0.70 = bon"))
    if performance:
        rows += [
            ("Performance", "Temps moyen (ms)",  str(performance["response_time_mean_ms"]), "< 5000 ms = bon"),
            ("Performance", "Temps P90 (ms)",    str(performance["response_time_p90_ms"]),  "< 10000 ms = bon"),
            ("Performance", "Taux d'erreur",     f"{performance['error_rate']:.4f}",         "< 0.05 = bon"),
            ("Performance", "Longueur moy. (mots)", str(performance["response_length_mean_words"]), "50-300 mots = idéal"),
        ]

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"  ✅ Résumé  → {summary_path}")

    # ── JSON complet (archive) ─────────────────────────────────────────────
    json_path = out / f"evaluation_complete_{ts}.json"
    full_report = {
        "metadata": {
            "date":           datetime.now().isoformat(),
            "total_questions": len(results),
        },
        "metrics": {
            "relevance_classification": relevance,
            "keyword_recall":           keyword_recall,
            "rouge":                    rouge,
            "ragas":                    ragas,
            "performance":              performance,
            "per_category":             per_category,
        },
        "details": [
            {k: v for k, v in r.items() if k not in ("retrieved_docs", "mots_cles")}
            for r in results
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Complet → {json_path}")

    return str(out)


# ══════════════════════════════════════════════════════════════════════════════
# 10. GÉNÉRATION DU TABLEAU LATEX (pour mémoire)
# ══════════════════════════════════════════════════════════════════════════════

def generate_latex_table(
    relevance: Dict,
    rouge: Dict,
    keyword_recall: Dict,
    ragas: Dict,
    performance: Dict,
    output_dir: str = "./evaluation_results",
):
    """Génère des tableaux LaTeX prêts à coller dans le mémoire."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"tableau_latex_{ts}.tex"

    lines = []
    lines.append("% ═══════════════════════════════════════════════════")
    lines.append("% TABLEAUX D'ÉVALUATION — CHATBOT UAM")
    lines.append(f"% Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    lines.append("% ═══════════════════════════════════════════════════")
    lines.append("")

    # Table 1 : Classification
    lines += [
        "\\begin{table}[h]",
        "\\centering",
        "\\caption{Métriques de classification pertinence/hors-sujet}",
        "\\label{tab:classification}",
        "\\begin{tabular}{lcc}",
        "\\hline",
        "\\textbf{Métrique} & \\textbf{Valeur} & \\textbf{Seuil acceptable} \\\\",
        "\\hline",
        f"Précision & {relevance.get('precision',0):.4f} & $> 0.80$ \\\\",
        f"Rappel & {relevance.get('recall',0):.4f} & $> 0.80$ \\\\",
        f"F1-Score & {relevance.get('f1_score',0):.4f} & $> 0.80$ \\\\",
        f"Exactitude & {relevance.get('accuracy',0):.4f} & $> 0.85$ \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ]

    # Table 2 : Keyword Recall (si disponible)
    if keyword_recall:
        n = keyword_recall.get("n_evaluated", "?")
        lines += [
            "\\begin{table}[h]",
            "\\centering",
            f"\\caption{{Keyword Recall par catégorie ({n} questions évaluées)}}",
            "\\label{tab:keyword_recall}",
            "\\begin{tabular}{lcc}",
            "\\hline",
            "\\textbf{Catégorie} & \\textbf{Recall} & \\textbf{Seuil acceptable} \\\\",
            "\\hline",
        ]
        for cat, val in sorted(keyword_recall.get("per_category", {}).items()):
            lines.append(f"{cat.replace('_', ' ').title()} & {val:.4f} & $> 0.70$ \\\\")
        lines += [
            "\\hline",
            f"\\textbf{{Moyenne}} & \\textbf{{{keyword_recall.get('mean',0):.4f}}} & $> 0.70$ \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]

    # Table 3 : ROUGE (si disponible)
    if rouge:
        lines += [
            "\\begin{table}[h]",
            "\\centering",
            f"\\caption{{Métriques ROUGE sur {rouge.get('n_evaluated','?')} questions}}",
            "\\label{tab:rouge}",
            "\\begin{tabular}{lcc}",
            "\\hline",
            "\\textbf{Métrique} & \\textbf{Valeur} & \\textbf{Seuil acceptable} \\\\",
            "\\hline",
            f"ROUGE-1 & {rouge.get('rouge1',0):.4f} & $> 0.40$ \\\\",
            f"ROUGE-2 & {rouge.get('rouge2',0):.4f} & $> 0.20$ \\\\",
            f"ROUGE-L & {rouge.get('rougeL',0):.4f} & $> 0.35$ \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]

    # Table 4 : RAGAS (si disponible)
    if ragas:
        lines += [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Métriques RAGAS (évaluation du système RAG)}",
            "\\label{tab:ragas}",
            "\\begin{tabular}{lcc}",
            "\\hline",
            "\\textbf{Métrique} & \\textbf{Valeur} & \\textbf{Seuil acceptable} \\\\",
            "\\hline",
        ]
        for k, v in ragas.items():
            lines.append(f"{k.replace('_', ' ').title()} & {v:.4f} & $> 0.70$ \\\\")
        lines += [
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]

    # Table 5 : Performance
    if performance:
        lines += [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Métriques de performance système}",
            "\\label{tab:performance}",
            "\\begin{tabular}{lc}",
            "\\hline",
            "\\textbf{Métrique} & \\textbf{Valeur} \\\\",
            "\\hline",
            f"Questions évaluées & {performance['total_evaluated']} \\\\",
            f"Taux de succès & {(1-performance['error_rate'])*100:.1f}\\% \\\\",
            f"Temps de réponse moyen & {performance['response_time_mean_ms']} ms \\\\",
            f"Temps médian (P50) & {performance['response_time_p50_ms']} ms \\\\",
            f"Percentile 90 (P90) & {performance['response_time_p90_ms']} ms \\\\",
            f"Longueur moyenne des réponses & {performance['response_length_mean_words']} mots \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✅ LaTeX   → {path}")


# ══════════════════════════════════════════════════════════════════════════════
# 11. POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Évaluation automatique du chatbot UAM"
    )
    parser.add_argument(
        "--dataset",  default="dataset_evaluation.csv",
        help="Chemin vers le CSV de test (défaut: dataset_evaluation.csv)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limiter à N questions (pour test rapide)"
    )
    parser.add_argument(
        "--no-ragas", action="store_true",
        help="Ne pas calculer les métriques RAGAS"
    )
    parser.add_argument(
        "--output", default="./evaluation_results",
        help="Dossier de sortie des résultats"
    )
    parser.add_argument(
        "--provider", default=None,
        help="Provider LLM (seul 'openrouter' est supporté)"
    )
    args = parser.parse_args()

    # ── Configuration ──────────────────────────────────────────────────────
    config = get_config()
    provider_str = args.provider or config.llm.provider or "openrouter"
    provider = LLMProvider.OPENROUTER

    print(f"\n{BOLD}🎓 ÉVALUATION DU CHATBOT UAM{RESET}")
    print(f"   Dataset    : {args.dataset}")
    print(f"   Provider   : {provider_str}")
    print(f"   RAGAS      : {'désactivé' if args.no_ragas else 'activé'}")
    print(f"   Sortie     : {args.output}\n")

    # ── Chargement dataset ─────────────────────────────────────────────────
    print(f"{BOLD}► Chargement du dataset…{RESET}")
    samples = load_dataset(args.dataset)
    if args.limit:
        samples = samples[:args.limit]
    print(f"  {len(samples)} questions chargées")

    # ── Initialisation agent ───────────────────────────────────────────────
    print(f"\n{BOLD}► Initialisation de l'agent…{RESET}")
    llm        = initialize_llm(provider, config.llm.model_name)
    embeddings = initialize_embeddings(provider)
    vectorstore = load_and_index_documents(config.documents_directory, provider)
    agent       = create_agent_graph(vectorstore, llm)
    print(f"  Agent initialisé ({provider_str})")

    # ── Exécution ──────────────────────────────────────────────────────────
    results = run_agent_on_dataset(agent, vectorstore, samples, config)

    # ── Calcul des métriques ───────────────────────────────────────────────
    print(f"\n{BOLD}► Calcul des métriques…{RESET}")

    relevance       = compute_relevance_metrics(results)
    rouge           = compute_rouge_metrics(results)
    kw_recall       = compute_keyword_recall(results)
    ragas_scores    = {} if args.no_ragas else compute_ragas_metrics(results, llm, embeddings)
    performance     = compute_performance_metrics(results)
    per_category    = compute_per_category_metrics(results)

    n_kw = kw_recall.get("n_evaluated", 0)
    if n_kw:
        print(f"  Keyword recall calculé sur {n_kw} questions  (recall moyen : {kw_recall['mean']:.4f})")
    else:
        print(f"  {YELLOW}Keyword recall : colonne 'mots_cles' absente du dataset — ajoutez-la pour activer cette métrique{RESET}")

    # ── Rapport ────────────────────────────────────────────────────────────
    print_report(relevance, rouge, kw_recall, ragas_scores, performance, per_category)

    # ── Sauvegarde ─────────────────────────────────────────────────────────
    print(f"{BOLD}► Sauvegarde des résultats…{RESET}")
    save_results(results, relevance, rouge, kw_recall, ragas_scores, performance, per_category, args.output)
    generate_latex_table(relevance, rouge, kw_recall, ragas_scores, performance, args.output)

    print(f"\n{GREEN}{BOLD}✅ Évaluation terminée !{RESET}")
    print(f"   Résultats dans : {Path(args.output).resolve()}\n")


if __name__ == "__main__":
    main()

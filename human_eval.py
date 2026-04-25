"""
Script de traitement de l'évaluation humaine du chatbot UAM
Calcule les scores et l'accord inter-juges pour le mémoire de Master 2

Usage:
    # 1. Remplir le fichier human_eval_template.csv avec vos juges
    # 2. Lancer :
    python human_eval.py --input human_eval_filled.csv
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ══════════════════════════════════════════════════════════════════════════════
# DIMENSIONS D'ÉVALUATION
# ══════════════════════════════════════════════════════════════════════════════

DIMENSIONS = {
    "pertinence":   ("Pertinence",   "La réponse est-elle en rapport avec la question ?"),
    "exactitude":   ("Exactitude",   "Les informations données sont-elles correctes ?"),
    "completude":   ("Complétude",   "La réponse est-elle suffisamment détaillée ?"),
    "fluidite":     ("Fluidité",     "La réponse est-elle naturelle et bien formulée ?"),
    "utilite":      ("Utilité",      "Cette réponse vous aiderait-elle concrètement ?"),
}

WEIGHTS = {
    "pertinence": 0.20,
    "exactitude": 0.30,
    "completude": 0.20,
    "fluidite":   0.10,
    "utilite":    0.20,
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. GÉNÉRATION DU TEMPLATE VIDE
# ══════════════════════════════════════════════════════════════════════════════

def generate_template(questions_file: str, output: str = "human_eval_template.csv"):
    """
    Génère un fichier CSV vide à remplir par les juges humains.
    Chaque juge reçoit une copie du fichier et le remplit.

    Échelle de Likert :
        1 = Très mauvais   2 = Mauvais   3 = Acceptable   4 = Bon   5 = Très bon
    """
    # Charger les questions depuis le dataset d'évaluation
    questions = []
    if Path(questions_file).exists():
        with open(questions_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("expected_relevant", "true").lower() == "true":
                    questions.append(row["question"].strip())

    if not questions:
        questions = [
            "Quelles sont les facultés de l'UAM ?",
            "Comment s'inscrire à l'UAM ?",
            "Quels sont les frais de scolarité ?",
        ]

    with open(output, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["juge_id", "question_id", "question", "reponse_chatbot"] + list(DIMENSIONS.keys()) + ["commentaire"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # En-tête avec instructions
        f.write("# FEUILLE D'ÉVALUATION HUMAINE — CHATBOT UAM\n")
        f.write("# Échelle : 1=Très mauvais  2=Mauvais  3=Acceptable  4=Bon  5=Très bon\n")
        f.write(f"# Dimensions :\n")
        for key, (name, desc) in DIMENSIONS.items():
            f.write(f"#   {name} : {desc}\n")
        f.write("#\n")
        f.write("# INSTRUCTIONS :\n")
        f.write("#   1. Remplacez JUGE_X par votre identifiant (ex: J1, J2...)\n")
        f.write("#   2. Remplissez les colonnes de notes (1 à 5)\n")
        f.write("#   3. Le champ 'commentaire' est optionnel\n")
        f.write("#\n")

        writer.writeheader()
        for i, q in enumerate(questions, 1):
            writer.writerow({
                "juge_id":       "JUGE_X",
                "question_id":   f"Q{i:02d}",
                "question":      q,
                "reponse_chatbot": "(à remplir avec la réponse réelle du chatbot)",
                "pertinence":    "",
                "exactitude":    "",
                "completude":    "",
                "fluidite":      "",
                "utilite":       "",
                "commentaire":   "",
            })

    print(f"✅ Template généré : {output}")
    print(f"   {len(questions)} questions à évaluer")
    print(f"   Instructions dans les commentaires (#) du fichier")


# ══════════════════════════════════════════════════════════════════════════════
# 2. CHARGEMENT DES ÉVALUATIONS
# ══════════════════════════════════════════════════════════════════════════════

def load_evaluations(path: str) -> List[Dict[str, Any]]:
    """Charge le CSV d'évaluations rempli par les juges."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        # Ignorer les lignes de commentaires
        lines = [l for l in f if not l.strip().startswith("#")]

    reader = csv.DictReader(lines)
    for row in reader:
        try:
            scores = {}
            valid = True
            for dim in DIMENSIONS:
                val = row.get(dim, "").strip()
                if not val:
                    valid = False
                    break
                score = float(val)
                if not (1 <= score <= 5):
                    valid = False
                    break
                scores[dim] = score

            if valid:
                rows.append({
                    "juge_id":     row.get("juge_id", "").strip(),
                    "question_id": row.get("question_id", "").strip(),
                    "question":    row.get("question", "").strip(),
                    "scores":      scores,
                    "commentaire": row.get("commentaire", "").strip(),
                })
        except (ValueError, KeyError):
            continue

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# 3. SCORES MOYENS PAR DIMENSION
# ══════════════════════════════════════════════════════════════════════════════

def compute_dimension_scores(evaluations: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Calcule les scores moyens et écarts-types par dimension."""
    from statistics import mean, stdev

    dim_scores = {dim: [] for dim in DIMENSIONS}
    for ev in evaluations:
        for dim, score in ev["scores"].items():
            dim_scores[dim].append(score)

    results = {}
    for dim, scores in dim_scores.items():
        if scores:
            results[dim] = {
                "mean":   round(mean(scores), 3),
                "stdev":  round(stdev(scores), 3) if len(scores) > 1 else 0.0,
                "min":    min(scores),
                "max":    max(scores),
                "n":      len(scores),
            }

    # Score global pondéré
    if results:
        global_score = sum(
            results[dim]["mean"] * WEIGHTS.get(dim, 0)
            for dim in results
        )
        results["global_pondere"] = {"mean": round(global_score, 3)}

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 4. ACCORD INTER-JUGES (Kappa de Cohen / Alpha de Krippendorff)
# ══════════════════════════════════════════════════════════════════════════════

def compute_inter_rater_agreement(evaluations: List[Dict]) -> Dict[str, Any]:
    """
    Calcule l'accord inter-juges.
    - Si 2 juges : Kappa de Cohen (sklearn)
    - Si N juges : Alpha de Krippendorff (krippendorff)
    - Fallback : corrélation de Pearson entre juges
    """
    # Organiser par (question_id, juge_id)
    by_q = {}
    for ev in evaluations:
        qid = ev["question_id"]
        jid = ev["juge_id"]
        if qid not in by_q:
            by_q[qid] = {}
        # Score global simple (moyenne des dimensions)
        by_q[qid][jid] = round(sum(ev["scores"].values()) / len(ev["scores"]), 1)

    # Trouver les questions évaluées par tous les juges
    all_judges = list({ev["juge_id"] for ev in evaluations})
    common_qs = [q for q, j_dict in by_q.items() if all(j in j_dict for j in all_judges)]

    if len(common_qs) < 3 or len(all_judges) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Besoin d'au moins 2 juges et 3 questions communes (actuel: {len(all_judges)} juges, {len(common_qs)} questions)."
        }

    results = {
        "n_judges":        len(all_judges),
        "n_questions":     len(common_qs),
        "judges":          all_judges,
    }

    # Kappa de Cohen (2 juges)
    if len(all_judges) == 2:
        try:
            from sklearn.metrics import cohen_kappa_score
            j1_scores = [round(by_q[q][all_judges[0]]) for q in common_qs]
            j2_scores = [round(by_q[q][all_judges[1]]) for q in common_qs]
            kappa = cohen_kappa_score(j1_scores, j2_scores)
            results["cohen_kappa"] = round(kappa, 4)
            results["kappa_interpretation"] = _interpret_kappa(kappa)
        except ImportError:
            results["cohen_kappa"] = "sklearn non installé"

    # Alpha de Krippendorff (N juges)
    try:
        import krippendorff
        data = [[by_q[q].get(j, None) for q in common_qs] for j in all_judges]
        alpha = krippendorff.alpha(reliability_data=data, level_of_measurement="ordinal")
        results["krippendorff_alpha"] = round(alpha, 4)
        results["alpha_interpretation"] = _interpret_kappa(alpha)
    except ImportError:
        pass  # krippendorff optionnel

    # Corrélation de Pearson (toujours disponible, pour 2 juges)
    if len(all_judges) == 2:
        try:
            from statistics import correlation
            s1 = [by_q[q][all_judges[0]] for q in common_qs]
            s2 = [by_q[q][all_judges[1]] for q in common_qs]
            r = correlation(s1, s2)
            results["pearson_r"] = round(r, 4)
        except (ImportError, Exception):
            pass

    return results


def _interpret_kappa(k: float) -> str:
    if k < 0:       return "Désaccord (κ < 0)"
    elif k < 0.20:  return "Léger (0 < κ < 0.20)"
    elif k < 0.40:  return "Passable (0.20 ≤ κ < 0.40)"
    elif k < 0.60:  return "Modéré (0.40 ≤ κ < 0.60)"
    elif k < 0.80:  return "Substantiel (0.60 ≤ κ < 0.80) ✓"
    else:           return "Quasi-parfait (κ ≥ 0.80) ✓✓"


# ══════════════════════════════════════════════════════════════════════════════
# 5. SCORES PAR QUESTION ET PAR CATÉGORIE
# ══════════════════════════════════════════════════════════════════════════════

def compute_per_question_scores(evaluations: List[Dict]) -> List[Dict]:
    """Score moyen de toutes les dimensions pour chaque question."""
    from statistics import mean

    by_q: Dict[str, List[Dict]] = {}
    for ev in evaluations:
        qid = ev["question_id"]
        if qid not in by_q:
            by_q[qid] = []
        by_q[qid].append(ev)

    per_question = []
    for qid, evs in sorted(by_q.items()):
        dim_means = {}
        for dim in DIMENSIONS:
            vals = [e["scores"][dim] for e in evs if dim in e["scores"]]
            dim_means[dim] = round(mean(vals), 2) if vals else 0

        global_w = sum(dim_means.get(d, 0) * WEIGHTS.get(d, 0) for d in DIMENSIONS)
        per_question.append({
            "question_id":   qid,
            "question":      evs[0]["question"][:60] + "…" if len(evs[0]["question"]) > 60 else evs[0]["question"],
            "n_judges":      len(evs),
            "dim_scores":    dim_means,
            "global_score":  round(global_w, 2),
        })

    return per_question


# ══════════════════════════════════════════════════════════════════════════════
# 6. AFFICHAGE + SAUVEGARDE
# ══════════════════════════════════════════════════════════════════════════════

def print_human_report(dim_scores: Dict, agreement: Dict, per_question: List[Dict]):
    sep = "─" * 60

    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}")
    print(f"{BOLD}{BLUE}   RAPPORT ÉVALUATION HUMAINE — CHATBOT UAM{RESET}")
    print(f"{BOLD}{BLUE}   {datetime.now().strftime('%d/%m/%Y %H:%M')}{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 60}{RESET}\n")

    # Scores par dimension
    print(f"{BOLD}1. SCORES MOYENS PAR DIMENSION (échelle 1–5){RESET}")
    print(sep)
    print(f"  {'Dimension':<22} {'Moyenne':>8} {'Écart-type':>12} {'Min':>5} {'Max':>5} {'N':>4}")
    print(f"  {'-'*22} {'-'*8} {'-'*12} {'-'*5} {'-'*5} {'-'*4}")

    for dim, (name, _) in DIMENSIONS.items():
        if dim in dim_scores:
            d = dim_scores[dim]
            stars = "★" * int(round(d["mean"]))
            pct = d["mean"] / 5 * 100
            print(f"  {name:<22} {d['mean']:>8.3f} {d['stdev']:>12.3f} "
                  f"{d['min']:>5.1f} {d['max']:>5.1f} {d['n']:>4}  ({pct:.0f}%)")

    if "global_pondere" in dim_scores:
        g = dim_scores["global_pondere"]["mean"]
        print(f"\n  {'Score global pondéré':<22} {BOLD}{g:>8.3f}{RESET}  /5.000  ({g/5*100:.1f}%)")

    # Accord inter-juges
    print(f"\n{BOLD}2. ACCORD INTER-JUGES{RESET}")
    print(sep)
    if agreement.get("status") == "insufficient_data":
        print(f"  {YELLOW}⚠ {agreement['message']}{RESET}")
    else:
        print(f"  Nombre de juges     : {agreement.get('n_judges', '?')}")
        print(f"  Questions communes  : {agreement.get('n_questions', '?')}")
        if "cohen_kappa" in agreement:
            k = agreement["cohen_kappa"]
            print(f"  Kappa de Cohen (κ)  : {BOLD}{k}{RESET}  — {agreement.get('kappa_interpretation','')}")
        if "krippendorff_alpha" in agreement:
            a = agreement["krippendorff_alpha"]
            print(f"  Alpha Krippendorff  : {BOLD}{a}{RESET}  — {agreement.get('alpha_interpretation','')}")
        if "pearson_r" in agreement:
            print(f"  Corrélation Pearson : {agreement['pearson_r']}")

    # Scores par question (top/bottom)
    if per_question:
        print(f"\n{BOLD}3. SCORES PAR QUESTION (top 5 et bottom 5){RESET}")
        print(sep)
        sorted_q = sorted(per_question, key=lambda x: x["global_score"], reverse=True)

        print(f"  {BOLD}Meilleures réponses :{RESET}")
        for item in sorted_q[:5]:
            score = item["global_score"]
            color = GREEN if score >= 4 else YELLOW if score >= 3 else RED
            print(f"  {color}[{item['question_id']}] {score:.2f}/5{RESET}  {item['question']}")

        if len(sorted_q) > 5:
            print(f"\n  {BOLD}Réponses à améliorer :{RESET}")
            for item in sorted_q[-3:]:
                score = item["global_score"]
                print(f"  {RED}[{item['question_id']}] {score:.2f}/5{RESET}  {item['question']}")

    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}\n")


def save_human_results(
    dim_scores: Dict,
    agreement: Dict,
    per_question: List[Dict],
    evaluations: List[Dict],
    output_dir: str = "./evaluation_results",
):
    """Sauvegarde les résultats de l'évaluation humaine."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV résumé par dimension
    csv_path = out / f"human_eval_summary_{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Dimension", "Moyenne /5", "Ecart-type", "Min", "Max", "N", "Seuil acceptable"])
        for dim, (name, _) in DIMENSIONS.items():
            if dim in dim_scores:
                d = dim_scores[dim]
                writer.writerow([name, d["mean"], d["stdev"], d["min"], d["max"], d["n"], ">= 3.5"])
        if "global_pondere" in dim_scores:
            g = dim_scores["global_pondere"]["mean"]
            writer.writerow(["Score global pondéré", g, "", "", "", "", ">= 3.5"])

        writer.writerow([])
        writer.writerow(["ACCORD INTER-JUGES"])
        for k, v in agreement.items():
            if k not in ("status", "judges"):
                writer.writerow([k, v])

    print(f"  ✅ Résumé  → {csv_path}")

    # CSV détaillé par question
    q_path = out / f"human_eval_per_question_{ts}.csv"
    with open(q_path, "w", newline="", encoding="utf-8") as f:
        if per_question:
            fieldnames = (["question_id", "question", "n_judges", "global_score"]
                         + list(DIMENSIONS.keys()))
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in per_question:
                row = {
                    "question_id":  item["question_id"],
                    "question":     item["question"],
                    "n_judges":     item["n_judges"],
                    "global_score": item["global_score"],
                }
                row.update(item["dim_scores"])
                writer.writerow(row)
    print(f"  ✅ Par question → {q_path}")

    # LaTeX
    _save_human_latex(dim_scores, agreement, out, ts)


def _save_human_latex(dim_scores, agreement, out, ts):
    path = out / f"human_eval_latex_{ts}.tex"
    lines = [
        "% TABLEAUX ÉVALUATION HUMAINE — CHATBOT UAM",
        f"% Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        "",
        "\\begin{table}[h]",
        "\\centering",
        "\\caption{Résultats de l'évaluation humaine du chatbot UAM (échelle Likert 1--5)}",
        "\\label{tab:eval-humaine}",
        "\\begin{tabular}{lcccc}",
        "\\hline",
        "\\textbf{Dimension} & \\textbf{Moyenne} & \\textbf{Écart-type} & \\textbf{Min} & \\textbf{Max} \\\\",
        "\\hline",
    ]
    for dim, (name, _) in DIMENSIONS.items():
        if dim in dim_scores:
            d = dim_scores[dim]
            lines.append(f"{name} & {d['mean']:.3f} & {d['stdev']:.3f} & {d['min']:.1f} & {d['max']:.1f} \\\\")

    if "global_pondere" in dim_scores:
        g = dim_scores["global_pondere"]["mean"]
        lines += [
            "\\hline",
            f"\\textbf{{Score global pondéré}} & \\textbf{{{g:.3f}}} & -- & -- & -- \\\\",
        ]
    lines += ["\\hline", "\\end{tabular}", "\\end{table}", ""]

    # Table accord inter-juges
    if agreement.get("status") != "insufficient_data":
        lines += [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Accord inter-juges}",
            "\\label{tab:accord}",
            "\\begin{tabular}{ll}",
            "\\hline",
            "\\textbf{Mesure} & \\textbf{Valeur} \\\\",
            "\\hline",
        ]
        for k, v in agreement.items():
            if k not in ("status", "judges", "kappa_interpretation", "alpha_interpretation"):
                lines.append(f"{k.replace('_', ' ').title()} & {v} \\\\")
        lines += ["\\hline", "\\end{tabular}", "\\end{table}"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✅ LaTeX   → {path}")


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Traitement évaluation humaine du chatbot UAM")
    parser.add_argument("--generate-template", action="store_true",
                        help="Générer le template CSV vide pour les juges")
    parser.add_argument("--input",   default="human_eval_filled.csv",
                        help="CSV d'évaluations rempli par les juges")
    parser.add_argument("--dataset", default="dataset_evaluation.csv",
                        help="Dataset source (pour le template)")
    parser.add_argument("--output",  default="./evaluation_results",
                        help="Dossier de sortie")
    args = parser.parse_args()

    if args.generate_template:
        generate_template(args.dataset)
        print("\n📋 Distribuez ce fichier à vos juges.")
        print("   Chaque juge remplit sa propre copie et vous la renvoie.")
        print("   Fusionnez toutes les copies dans un seul CSV, puis lancez :")
        print("   python human_eval.py --input human_eval_filled.csv")
        return

    print(f"\n{BOLD}🎓 ÉVALUATION HUMAINE — CHATBOT UAM{RESET}")
    print(f"   Fichier : {args.input}")

    if not Path(args.input).exists():
        print(f"\n{RED}Fichier '{args.input}' introuvable.{RESET}")
        print("Générez d'abord le template :")
        print("  python human_eval.py --generate-template")
        return

    evaluations = load_evaluations(args.input)
    if not evaluations:
        print(f"{RED}Aucune évaluation valide trouvée dans {args.input}.{RESET}")
        return

    judges   = list({e["juge_id"] for e in evaluations})
    print(f"\n  {len(evaluations)} évaluations chargées — {len(judges)} juge(s) : {', '.join(judges)}")

    dim_scores   = compute_dimension_scores(evaluations)
    agreement    = compute_inter_rater_agreement(evaluations)
    per_question = compute_per_question_scores(evaluations)

    print_human_report(dim_scores, agreement, per_question)

    print(f"{BOLD}► Sauvegarde des résultats…{RESET}")
    save_human_results(dim_scores, agreement, per_question, evaluations, args.output)

    print(f"\n{GREEN}{BOLD}✅ Évaluation humaine traitée !{RESET}")
    print(f"   Résultats dans : {Path(args.output).resolve()}\n")


if __name__ == "__main__":
    main()

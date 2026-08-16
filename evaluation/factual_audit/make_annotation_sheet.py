#!/usr/bin/env python3
"""
Génère une feuille d'annotation de la fidélité factuelle à partir des résultats
d'évaluation de l'agent (results_agent.json ou evaluation_complete_*.json).

Ne conserve par défaut que les questions UAM légitimes (expected_relevant = True),
seules pertinentes pour juger la correction factuelle des réponses.

Voir PROTOCOLE_ANNOTATION.md pour la sémantique des colonnes.

Usage:
    python make_annotation_sheet.py --results ../../evaluation_results/1352/results_agent.json \
                                    --out annotation_agent.csv [--shuffle] [--include-offtopic] \
                                    [--sample N]
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

# Colonnes à remplir par l'annotateur (laissées vides ici).
ANNOTATION_COLUMNS = [
    "verdict_factuel",   # C / P / I / NV   (obligatoire)
    "exactitude",        # 1-5  (optionnel)
    "completude",        # 1-5  (optionnel)
    "clarte",            # 1-5  (optionnel)
    "utilite",           # 1-5  (optionnel)
    "notes",             # justification (obligatoire si P ou I)
]


def load_items(path: Path):
    """Charge la liste d'items quelle que soit la forme du JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("details", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(
        f"Format JSON non reconnu dans {path} : attendu une liste ou une clé 'details'."
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, help="Chemin du JSON de résultats de l'agent")
    ap.add_argument("--out", default="annotation_agent.csv", help="CSV de sortie")
    ap.add_argument("--include-offtopic", action="store_true",
                    help="Inclure aussi les questions hors-sujet (expected_relevant=False)")
    ap.add_argument("--shuffle", action="store_true",
                    help="Mélanger l'ordre (annotation à l'aveugle), graine fixée à 42")
    ap.add_argument("--sample", type=int, default=None,
                    help="Tirer un sous-échantillon aléatoire de N items (graine 42)")
    args = ap.parse_args()

    src = Path(args.results)
    if not src.exists():
        sys.exit(f"Fichier introuvable : {src}")

    items = load_items(src)

    if not args.include_offtopic:
        items = [r for r in items if r.get("expected_relevant")]

    # Identifiant stable basé sur l'ordre original du dataset
    for idx, r in enumerate(items, 1):
        r["_id"] = idx

    if args.sample and args.sample < len(items):
        random.seed(42)
        items = random.sample(items, args.sample)

    if args.shuffle:
        random.seed(42)
        random.shuffle(items)

    fieldnames = ["id", "category", "expected_relevant", "question",
                  "ground_truth", "response"] + ANNOTATION_COLUMNS

    out = Path(args.out)
    # utf-8-sig : ouverture correcte des accents dans Excel/LibreOffice
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in items:
            row = {
                "id": r["_id"],
                "category": r.get("category", ""),
                "expected_relevant": r.get("expected_relevant", ""),
                "question": (r.get("question") or "").strip(),
                "ground_truth": (r.get("ground_truth") or "").strip(),
                "response": (r.get("response") or "").strip(),
            }
            for c in ANNOTATION_COLUMNS:
                row[c] = ""
            w.writerow(row)

    n_gt = sum(1 for r in items if (r.get("ground_truth") or "").strip())
    print(f"✅ Feuille d'annotation : {out}")
    print(f"   {len(items)} questions à annoter  (dont {n_gt} avec réponse de référence).")
    print(f"   Remplir la colonne 'verdict_factuel' avec C / P / I / NV.")
    print(f"   Puis : python compute_factual_accuracy.py {out.name}")


if __name__ == "__main__":
    main()

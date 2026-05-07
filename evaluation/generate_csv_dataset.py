"""
Convertit `test_dataset_uam.py` en CSV consommable par `evaluate.py`.

Sortie : `dataset_evaluation.csv` à la racine du projet.
Colonnes : question, ground_truth, category, expected_relevant, mots_cles

- expected_relevant vaut "false" uniquement pour la catégorie "hors_sujet"
- ground_truth est laissé vide (les métriques ROUGE seront ignorées) ;
  remplissez-le manuellement pour activer ROUGE
- mots_cles est une chaîne pipe-séparée (ex: "inscription|baccalauréat|dossier")
"""
from pathlib import Path
import csv
import sys

# Permet l'import depuis ce sous-dossier
sys.path.insert(0, str(Path(__file__).parent))

from test_dataset_uam import TEST_DATASET  # noqa: E402

OUTPUT = Path(__file__).resolve().parent.parent / "dataset_evaluation.csv"


def main() -> None:
    rows = []
    for item in TEST_DATASET:
        category = item["categorie"]
        rows.append({
            "question":          item["question"],
            "ground_truth":      "",
            "category":          category,
            "expected_relevant": "false" if category == "hors_sujet" else "true",
            "mots_cles":         "|".join(item["mots_cles_attendus"]),
        })

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["question", "ground_truth", "category",
                        "expected_relevant", "mots_cles"],
        )
        writer.writeheader()
        writer.writerows(rows)

    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1

    print(f"Écrit : {OUTPUT}")
    print(f"Total : {len(rows)} cas")
    for cat, n in sorted(by_cat.items()):
        marker = " (hors-sujet)" if cat == "hors_sujet" else ""
        print(f"  {cat:30s} : {n}{marker}")


if __name__ == "__main__":
    main()

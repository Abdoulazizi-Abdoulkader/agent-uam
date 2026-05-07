"""
Met à jour automatiquement le Chapitre 4 de Memoire.docx à partir d'un
rapport JSON produit par `evaluate.py`.

Workflow :

  1. python evaluate.py --dataset dataset_evaluation.csv
     → produit `evaluation_results/evaluation_complete_<TS>.json`

  2. python evaluation/update_memoire_chapter4.py \
         --json evaluation_results/evaluation_complete_<TS>.json \
         --docx Memoire.docx \
         --out  Memoire_updated.docx

Les modifications sont appliquées sous forme de *tracked changes*
(auteur "Claude") : ouvrez le fichier de sortie dans Word et utilisez
"Révision → Suivi des modifications" pour les accepter ou rejeter.

Limitations connues :
  - Seuls les remplacements *unicité élevée* (phrases ou nombres avec
    décimales/séparateurs) sont automatisés. Les nombres simples comme
    "35", "6", "0" qui apparaissent dans plusieurs tableaux ne sont PAS
    remplacés ; le script imprime à la fin une liste de corrections
    manuelles à faire dans le Tableau 4.4 (TP/TN/FP/FN).
  - Les libellés de catégorie du Tableau 4.3 et 4.6 ne sont pas mis à
    jour automatiquement (ils dépendent de votre dataset).
  - Si un texte cible n'est pas trouvé (parce qu'il a déjà été modifié),
    la modification est silencieusement ignorée et signalée en fin
    d'exécution.

Dépendances : seulement la bibliothèque standard Python.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape


AUTHOR = "Claude"


# ── Helpers de formatage français ────────────────────────────────────────────
def fmt_score(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def fmt_int_thousands(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def fmt_decimal_thousands(value: float, decimals: int = 1) -> str:
    int_part, _, frac = f"{value:.{decimals}f}".partition(".")
    int_fmt = f"{int(int_part):,}".replace(",", " ")
    return f"{int_fmt},{frac}" if frac else int_fmt


def fmt_words(value: float) -> str:
    """Ex: 134.8 → '134,8' ; 142.0 → '142'."""
    s = f"{value:.1f}".replace(".", ",")
    return s.rstrip("0").rstrip(",") or "0"


def fmt_pct_simple(value: float) -> str:
    """0.0 → '0 %' ; 0.025 → '2,5 %'."""
    if value == 0:
        return "0 %"
    return f"{value * 100:.1f} %".replace(".", ",")


def fmt_pct_dec(value: float) -> str:
    """0.0 → '0,0 %'."""
    return f"{value * 100:.1f} %".replace(".", ",")


# ── Construction de la table de remplacements ───────────────────────────────
def build_replacements(report: Dict) -> List[Tuple[str, str, str]]:
    m = report.get("metrics", {})
    rel = m.get("relevance_classification", {})
    rouge = m.get("rouge", {})
    perf = m.get("performance", {})

    repl: List[Tuple[str, str, str]] = []

    total = perf.get("total_evaluated") or report.get("metadata", {}).get("total_questions", 0)
    tp = rel.get("true_positives", 0)
    tn = rel.get("true_negatives", 0)
    fp = rel.get("false_positives", 0)
    fn = rel.get("false_negatives", 0)
    n_uam = tp + fn
    n_off = tn + fp

    mean_ms = perf.get("response_time_mean_ms", 0.0)
    p50_ms = perf.get("response_time_p50_ms", 0)
    p90_ms = perf.get("response_time_p90_ms", 0)
    min_ms = perf.get("response_time_min_ms", 0)
    max_ms = perf.get("response_time_max_ms", 0)
    err = perf.get("error_rate", 0.0)
    n_words = perf.get("response_length_mean_words", 0.0)

    # ─── §4.2.3 / phrases narratives sur la taille du jeu de test ──────────
    repl += [
        ("Le jeu de test effectivement évalué comprend 41 cas",
         f"Le jeu de test effectivement évalué comprend {total} cas",
         "§4.2.3 — total cas"),
        ("Sur les 41 cas, 35 portent sur des questions effectivement liées",
         f"Sur les {total} cas, {n_uam} portent sur des questions effectivement liées",
         "§4.2.3 — répartition UAM"),
        ("et 6 sont des questions hors périmètre",
         f"et {n_off} sont des questions hors périmètre",
         "§4.2.3 — répartition hors-sujet"),
        ("Sur les 41 cas évalués, le système a produit",
         f"Sur les {total} cas évalués, le système a produit",
         "§4.3.1 — phrase intro"),
        ("(35 UAM + 6 hors-sujet)",
         f"({n_uam} UAM + {n_off} hors-sujet)",
         "ch.4 — répartition synthèse"),
    ]

    # ─── §4.3.2 — ROUGE ────────────────────────────────────────────────────
    if rouge:
        repl += [
            ("Tableau 4.5, Scores ROUGE sur les 41 questions",
             f"Tableau 4.5, Scores ROUGE sur les {total} questions",
             "§4.3.2 — titre tableau"),
            ("0,2577", fmt_score(rouge.get("rouge1", 0.0)), "§4.3.2 — ROUGE-1"),
            ("0,1380", fmt_score(rouge.get("rouge2", 0.0)), "§4.3.2 — ROUGE-2"),
            ("0,2066", fmt_score(rouge.get("rougeL", 0.0)), "§4.3.2 — ROUGE-L"),
        ]

    # ─── §4.3.4 — Tableau 4.7 (cellules à valeur unique) ──────────────────
    repl += [
        ("5 669,9", fmt_decimal_thousands(mean_ms), "§4.3.4 — t moyen (cellule)"),
        ("6 047",   fmt_int_thousands(int(p50_ms)), "§4.3.4 — P50 (cellule)"),
        ("8 847",   fmt_int_thousands(int(p90_ms)), "§4.3.4 — P90 (cellule)"),
        ("11 128",  fmt_int_thousands(int(max_ms)), "§4.3.4 — t max (cellule)"),
        ("134,8",   fmt_words(n_words),             "§4.3.4 — longueur (cellule)"),
    ]

    # ─── §4.3.4 — phrases d'analyse ────────────────────────────────────────
    repl += [
        ("La latence moyenne de 5 669,9 ms",
         f"La latence moyenne de {fmt_decimal_thousands(mean_ms)} ms",
         "§4.3.4 — analyse latence"),
        ("Le percentile 90 (P90) à 8 847 ms",
         f"Le percentile 90 (P90) à {fmt_int_thousands(int(p90_ms))} ms",
         "§4.3.4 — analyse P90"),
        ("La longueur moyenne des réponses (134,8 mots)",
         f"La longueur moyenne des réponses ({fmt_words(n_words)} mots)",
         "§4.3.4 — analyse longueur"),
        ("longueur moyenne de 134,8 mots",
         f"longueur moyenne de {fmt_words(n_words)} mots",
         "§4.3.2 — longueur dans analyse ROUGE"),
        ("le taux d'erreur de 0 %",
         f"le taux d'erreur de {fmt_pct_simple(err)}",
         "§4.3.4 — analyse taux d'erreur"),
    ]

    # ─── §4.6 — Synthèse ───────────────────────────────────────────────────
    repl += [
        ("La latence moyenne de 5 670 ms",
         f"La latence moyenne de {fmt_int_thousands(int(round(mean_ms)))} ms",
         "§4.6 — synthèse latence"),
        ("P90 à 8 847 ms",
         f"P90 à {fmt_int_thousands(int(p90_ms))} ms",
         "§4.6 — synthèse P90"),
    ]
    if rouge:
        repl.append((
            "Les scores ROUGE-1 (0,2577), ROUGE-2 (0,1380) et ROUGE-L (0,2066)",
            f"Les scores ROUGE-1 ({fmt_score(rouge.get('rouge1', 0))}), "
            f"ROUGE-2 ({fmt_score(rouge.get('rouge2', 0))}) et "
            f"ROUGE-L ({fmt_score(rouge.get('rougeL', 0))})",
            "§4.6 — synthèse ROUGE",
        ))

    # ─── Tableau 4.1 — date d'évaluation ────────────────────────────────────
    if "date" in report.get("metadata", {}):
        try:
            dt = datetime.fromisoformat(report["metadata"]["date"])
            mois_fr = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                       "juillet", "août", "septembre", "octobre", "novembre",
                       "décembre"]
            new_date = f"{dt.day} {mois_fr[dt.month]} {dt.year}, {dt.hour}h{dt.minute:02d}"
            repl.append(("23 avril 2026, 18h51", new_date, "Tableau 4.1 — date évaluation"))
        except Exception:
            pass

    # Dédoublonnage en conservant l'ordre
    seen = set()
    unique = []
    for old, new, label in repl:
        key = (old, new)
        if key in seen or old == new:
            continue
        seen.add(key)
        unique.append((old, new, label))

    return unique


# ── Application des tracked changes au document.xml ─────────────────────────
TRACKED_ID = [10000]


def next_id() -> int:
    TRACKED_ID[0] += 1
    return TRACKED_ID[0]


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_tracked_change(xml: str, current: str, new: str,
                         replace_all: bool = True) -> Tuple[str, int]:
    """
    Cherche `current` dans le contenu d'un `<w:t>` et applique un tracked
    change (del + ins) sur cette sous-chaîne. Par défaut, *toutes* les
    occurrences sont remplacées (utile pour les valeurs comme "0,2577"
    ou "5 669,9" qui apparaissent à la fois dans le tableau principal et
    dans les tableaux de synthèse).

    Stratégie pour chaque match :
      <w:t>AVANT{current}APRÈS</w:t>
        →
      <w:t>AVANT</w:t></w:r>
      <w:del><w:r><w:delText>{current}</w:delText></w:r></w:del>
      <w:ins><w:r><w:t>{new}</w:t></w:r></w:ins>
      <w:r><w:t>APRÈS</w:t>

    Retourne (xml_modifié, nb_occurrences_modifiées).
    """
    current_xml = escape(current)
    new_xml_text = escape(new)

    pattern = re.compile(
        r"(<w:t(?:\s+xml:space=\"preserve\")?>)"
        r"([^<]*?)"
        + re.escape(current_xml)
        + r"([^<]*?)"
        r"(</w:t>)"
    )

    space_attr = ' xml:space="preserve"'
    n_replaced = 0

    def repl(match: "re.Match") -> str:
        nonlocal n_replaced
        n_replaced += 1
        open_tag = match.group(1)
        before = match.group(2)
        after = match.group(3)
        close_tag = match.group(4)
        open_tag_pres = open_tag if "xml:space" in open_tag else f"<w:t{space_attr}>"

        del_id = next_id()
        ins_id = next_id()
        date = now_iso()

        return (
            f"{open_tag_pres}{before}{close_tag}"
            f"</w:r>"
            f'<w:del w:id="{del_id}" w:author="{AUTHOR}" w:date="{date}">'
            f"<w:r><w:delText{space_attr}>{current_xml}</w:delText></w:r>"
            f"</w:del>"
            f'<w:ins w:id="{ins_id}" w:author="{AUTHOR}" w:date="{date}">'
            f"<w:r><w:t{space_attr}>{new_xml_text}</w:t></w:r>"
            f"</w:ins>"
            f"<w:r>{open_tag_pres}{after}{close_tag}"
        )

    count = 0 if replace_all else 1
    new_xml = pattern.sub(repl, xml, count=count)
    return new_xml, n_replaced


def process_docx(docx_in: Path, docx_out: Path,
                 replacements: List[Tuple[str, str, str]]) -> None:
    print(f"\n→ Lecture de {docx_in}")
    if not docx_in.exists():
        sys.exit(f"Fichier introuvable : {docx_in}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(docx_in, "r") as z:
            z.extractall(tmp_dir)

        doc_xml_path = tmp_dir / "word" / "document.xml"
        xml = doc_xml_path.read_text(encoding="utf-8")

        applied: List[str] = []
        skipped: List[str] = []
        ambiguous: List[str] = []

        for current, new, label in replacements:
            xml, n_matches = apply_tracked_change(xml, current, new)
            if n_matches == 0:
                skipped.append(label)
                print(f"  · {label}: '{current}' introuvable (ignoré)")
            else:
                applied.append(label)
                msg = f"  ✓ {label}: {current!r} → {new!r}"
                if n_matches > 1:
                    ambiguous.append(label)
                    msg += f"  [{n_matches} occurrences modifiées]"
                print(msg)

        doc_xml_path.write_text(xml, encoding="utf-8")

        if docx_out.exists():
            docx_out.unlink()
        with zipfile.ZipFile(docx_out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in tmp_dir.rglob("*"):
                if f.is_file():
                    z.write(f, arcname=f.relative_to(tmp_dir).as_posix())

        # ─── Synthèse ──────────────────────────────────────────────────────
        print(f"\n→ Écrit : {docx_out}")
        print(f"  Modifications appliquées       : {len(applied)}")
        print(f"  Ignorées (texte non trouvé)    : {len(skipped)}")
        if ambiguous:
            print(f"  Patterns avec >1 occurrence    : {len(ambiguous)} (toutes modifiées)")

        if skipped:
            print("\nLes éléments suivants n'ont pas été trouvés dans le document.")
            print("Causes possibles : valeur déjà à jour, ou libellé modifié.")
            for label in skipped:
                print(f"    · {label}")

        # ─── Liste des corrections manuelles obligatoires ─────────────────
        print()
        print("=" * 70)
        print("À FAIRE MANUELLEMENT dans Memoire (cellules ambiguës) :")
        print("=" * 70)
        print("Tableau 4.4 — Métriques de classification (§4.3.1) :")
        print("  · Précision   : remplacer '1,00' par la valeur calculée")
        print("  · Rappel      : remplacer '1,00' par la valeur calculée")
        print("  · F1-Score    : remplacer '1,00' par la valeur calculée")
        print("  · Exactitude  : remplacer '1,00' par la valeur calculée")
        print("  · TP=35, TN=6, FP=0, FN=0 → vos vraies valeurs")
        print()
        print("Tableau 4.3 (§4.2.3) et 4.6 (§4.3.3) — Catégories :")
        print("  · Si vos catégories diffèrent (ex: inscription_premiere vs ")
        print("    structures), réécrivez les lignes du tableau à la main.")
        print("  · Mettez à jour les compteurs par catégorie.")
        print()
        print("Date d'évaluation (Tableau 4.1) : déjà mise à jour si présente")
        print("dans le JSON (sinon valeur conservée).")
        print("=" * 70)


# ── Point d'entrée ──────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Met à jour le Chapitre 4 de Memoire.docx avec les "
                    "résultats de evaluate.py (tracked changes)."
    )
    parser.add_argument("--json", required=True,
                        help="Fichier evaluation_complete_*.json")
    parser.add_argument("--docx", required=True, help="Memoire.docx d'entrée")
    parser.add_argument("--out", default="Memoire_updated.docx",
                        help="Fichier de sortie (défaut: Memoire_updated.docx)")
    args = parser.parse_args()

    json_path = Path(args.json)
    if not json_path.exists():
        sys.exit(f"Rapport JSON introuvable : {json_path}")

    report = json.loads(json_path.read_text(encoding="utf-8"))
    replacements = build_replacements(report)
    print(f"→ {len(replacements)} remplacements préparés depuis {json_path.name}")

    process_docx(Path(args.docx), Path(args.out), replacements)


if __name__ == "__main__":
    main()

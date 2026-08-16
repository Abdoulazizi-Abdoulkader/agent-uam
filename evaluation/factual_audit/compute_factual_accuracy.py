#!/usr/bin/env python3
"""
Calcule l'exactitude factuelle RÉELLE à partir d'une (ou deux) feuille(s)
d'annotation remplie(s) — voir PROTOCOLE_ANNOTATION.md.

Cette métrique remplace l'« exactitude » du mémoire qui mesurait en fait le
routage (expected_relevant == actual_relevant), non la fidélité factuelle.

Métriques produites :
  - Exactitude factuelle stricte = #C / (#C + #P + #I)        [NV exclus]
  - Exactitude factuelle large   = (#C + #P) / (#C + #P + #I)
  - Intervalle de Wilson 95 % sur l'exactitude stricte
  - Décomposition par catégorie
  - Likert moyens (si colonnes renseignées)
  - Kappa de Cohen (si deux fichiers fournis)

Usage:
    python compute_factual_accuracy.py annot1.csv [annot2.csv] [--latex]
"""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

VALID = {"C", "P", "I", "NV"}
LIKERT_COLS = ["exactitude", "completude", "clarte", "utilite"]


def read_annotation(path: Path):
    """Retourne {id: row} ; valide la colonne verdict_factuel."""
    rows = {}
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "verdict_factuel" not in (reader.fieldnames or []):
            sys.exit(f"{path}: colonne 'verdict_factuel' absente.")
        for r in reader:
            v = (r.get("verdict_factuel") or "").strip().upper()
            if v == "":
                continue  # non encore annoté
            if v not in VALID:
                sys.exit(f"{path} (id={r.get('id')}): verdict '{v}' invalide "
                         f"(attendu C/P/I/NV).")
            r["verdict_factuel"] = v
            rows[r.get("id")] = r
    if not rows:
        sys.exit(f"{path}: aucune ligne annotée (colonne 'verdict_factuel' vide).")
    return rows


def wilson(k: int, n: int, z: float = 1.96):
    """Intervalle de confiance de Wilson pour une proportion."""
    if n == 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def summarize(rows: dict):
    counts = defaultdict(int)
    by_cat = defaultdict(lambda: defaultdict(int))
    likert = defaultdict(list)
    for r in rows.values():
        v = r["verdict_factuel"]
        counts[v] += 1
        by_cat[r.get("category", "?")][v] += 1
        for c in LIKERT_COLS:
            val = (r.get(c) or "").strip().replace(",", ".")
            if val:
                try:
                    likert[c].append(float(val))
                except ValueError:
                    pass
    return counts, by_cat, likert


def acc_strict(c):
    denom = c["C"] + c["P"] + c["I"]
    return (c["C"] / denom, denom) if denom else (0.0, 0)


def acc_large(c):
    denom = c["C"] + c["P"] + c["I"]
    return ((c["C"] + c["P"]) / denom, denom) if denom else (0.0, 0)


def print_report(rows: dict):
    counts, by_cat, likert = summarize(rows)
    n = sum(counts.values())
    strict, denom = acc_strict(counts)
    large, _ = acc_large(counts)
    lo, hi = wilson(counts["C"], denom)

    print("\n" + "=" * 64)
    print("  EXACTITUDE FACTUELLE RÉELLE (audit manuel)")
    print("=" * 64)
    print(f"  Réponses annotées      : {n}")
    print(f"    Correct (C)          : {counts['C']}")
    print(f"    Partiel (P)          : {counts['P']}")
    print(f"    Incorrect (I)        : {counts['I']}")
    print(f"    Non vérifiable (NV)  : {counts['NV']}  (exclus du dénominateur)")
    print("-" * 64)
    print(f"  Exactitude STRICTE  (C / (C+P+I))     : {strict:.3f}  ({strict*100:.1f} %)")
    print(f"    IC Wilson 95 %                       : [{lo:.3f} ; {hi:.3f}]")
    print(f"  Exactitude LARGE    ((C+P) / (C+P+I)) : {large:.3f}  ({large*100:.1f} %)")
    seuil = 0.80
    verdict = "≥ 80 % → H1 soutenue" if strict >= seuil else "< 80 % → H1 NON soutenue (strict)"
    print(f"  Seuil H1 (0,80) sur exactitude stricte : {verdict}")

    print("\n  Décomposition par catégorie (exactitude stricte) :")
    print(f"  {'Catégorie':<28}{'C':>3}{'P':>3}{'I':>3}{'NV':>4}{'Acc.':>8}")
    print("  " + "-" * 50)
    for cat in sorted(by_cat):
        c = by_cat[cat]
        a, d = acc_strict(c)
        acc = f"{a*100:.0f}%" if d else "—"
        print(f"  {cat:<28}{c['C']:>3}{c['P']:>3}{c['I']:>3}{c['NV']:>4}{acc:>8}")

    if any(likert.values()):
        print("\n  Critères qualitatifs (moyennes Likert 1–5) :")
        for col in LIKERT_COLS:
            vals = likert.get(col, [])
            if vals:
                print(f"    {col:<14}: {sum(vals)/len(vals):.2f}/5  (n={len(vals)})")
    print("=" * 64 + "\n")
    return counts, strict, lo, hi


def cohen_kappa(a: dict, b: dict):
    """Kappa de Cohen sur verdict_factuel pour les ids communs."""
    ids = sorted(set(a) & set(b))
    if not ids:
        print("⚠ Aucun id commun entre les deux fichiers — kappa non calculable.")
        return
    labels = sorted(VALID)
    n = len(ids)
    agree = sum(1 for i in ids if a[i]["verdict_factuel"] == b[i]["verdict_factuel"])
    po = agree / n
    ca = defaultdict(int)
    cb = defaultdict(int)
    for i in ids:
        ca[a[i]["verdict_factuel"]] += 1
        cb[b[i]["verdict_factuel"]] += 1
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 1.0

    def interp(k):
        if k < 0.20: return "faible"
        if k < 0.40: return "passable"
        if k < 0.60: return "modéré"
        if k < 0.80: return "substantiel"
        return "presque parfait"

    print("=" * 64)
    print("  ACCORD INTER-ANNOTATEURS (Kappa de Cohen)")
    print("=" * 64)
    print(f"  Items communs annotés : {n}")
    print(f"  Accord observé (po)   : {po:.3f}")
    print(f"  Accord attendu (pe)   : {pe:.3f}")
    print(f"  Kappa de Cohen        : {kappa:.3f}  ({interp(kappa)})")
    print("=" * 64 + "\n")


def emit_latex(counts, strict, lo, hi):
    n = counts["C"] + counts["P"] + counts["I"]
    print("% --- Tableau LaTeX : exactitude factuelle réelle ---")
    print("\\begin{table}[H]\n\\centering")
    print("\\caption{Exactitude factuelle réelle (audit manuel des réponses UAM)}")
    print("\\label{tab:exactitude-factuelle}\n\\small")
    print("\\begin{tabularx}{\\textwidth}{X r}")
    print("\\toprule")
    print("\\textbf{Indicateur} & \\textbf{Valeur}\\\\")
    print("\\midrule")
    print(f"Réponses correctes (C) & {counts['C']}\\\\")
    print(f"Partiellement correctes (P) & {counts['P']}\\\\")
    print(f"Incorrectes (I) & {counts['I']}\\\\")
    print(f"Non vérifiables (NV, exclues) & {counts['NV']}\\\\")
    print("\\midrule")
    formule = "$C/(C{+}P{+}I)$"
    print("Exactitude factuelle stricte (" + formule + ") & "
          f"{strict:.3f} ({strict*100:.1f}\\%)\\\\")
    print(f"IC Wilson 95\\% & $[{lo:.3f}\\,;\\,{hi:.3f}]$\\\\")
    print("\\bottomrule")
    print("\\end{tabularx}\n\\end{table}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="1 ou 2 CSV d'annotation remplis")
    ap.add_argument("--latex", action="store_true", help="Émettre un tableau LaTeX")
    args = ap.parse_args()

    if len(args.files) > 2:
        sys.exit("Au plus deux fichiers (deux annotateurs).")

    annots = [read_annotation(Path(p)) for p in args.files]

    print(f"\n### Annotateur 1 : {args.files[0]}")
    counts, strict, lo, hi = print_report(annots[0])

    if len(annots) == 2:
        print(f"### Annotateur 2 : {args.files[1]}")
        print_report(annots[1])
        cohen_kappa(annots[0], annots[1])

    if args.latex:
        emit_latex(counts, strict, lo, hi)


if __name__ == "__main__":
    main()

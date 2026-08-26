#!/usr/bin/env python3
"""Différentiel de `check_question_relevance` : état d'avant le chantier
(commit f4bf621, `tools.py` monolithique) contre l'état actuel (`tools/`).

Contexte (finding 1, revue finale de branche) : une tâche antérieure a
corrigé BUG-04 en resserrant la recherche des abréviations UAM (« fa »,
« ens »…) au mot entier — juste, car en sous-chaîne elles matchaient « fait »,
« famille », « pense ». Mais ce match accidentel était aussi le seul filet
qui rattrapait de vraies questions d'étudiants, faute d'un vocabulaire assez
riche dans `keywords_uam`. Ce script mesure, phrase par phrase, si la
correction du vocabulaire (ajout de mots dans `keywords_uam`,
`tools/conversation.py`) a comblé ce trou sans rien perdre d'autre.

Usage :
    venv/bin/python scripts/diff_relevance_f4bf621.py

Critère de sortie (non négociable) : zéro PERTE. Une PERTE est une ligne où
le verdict baseline est PERTINENT et le verdict actuel est HORS_SUJET — une
vraie question qui serait désormais éconduite. Les GAINS (HORS_SUJET →
PERTINENT) sont bienvenus et ne font pas échouer le script.

Isolation : ce script importe `tools.py` de f4bf621 depuis une copie
temporaire (renommée pour ne pas entrer en collision avec le paquet `tools/`
actuel). Cette copie importe transitivement `memory.py`, qui ouvre une
connexion SQLite au chargement du module — les variables d'environnement
ci-dessous la détournent vers un fichier jetable, jamais vers
`user_memory.db` (voir CLAUDE.md : bases non versionnées à ne jamais
toucher).
"""
import os
import sys
import tempfile
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── Isolation des bases réelles avant tout import (même mécanisme que
# tests/conftest.py) : l'import de tools.py (baseline) charge memory.py, qui
# ouvre une connexion SQLite au chargement du module.
_scratch = tempfile.mkdtemp(prefix="uam-diff-relevance-")
os.environ.setdefault("UAM_MEMORY_DB", os.path.join(_scratch, "user_memory_scratch.db"))
os.environ.setdefault("UAM_MEMORY_FILE", os.path.join(_scratch, "user_memory_scratch.json"))
os.environ.setdefault("UAM_METRICS_DB", os.path.join(_scratch, "metrics_scratch.db"))
os.environ.setdefault("UAM_CHECKPOINT_DB", os.path.join(_scratch, "checkpoints_scratch.db"))

# ── Préparation du module baseline : `git show f4bf621:tools.py`, écrit sous
# un nom qui ne collisionne pas avec le paquet `tools/` actuel, dans un
# répertoire temporaire ajouté en tête de sys.path. Récupéré à l'exécution
# (pas de snapshot versionné) : la source de vérité reste l'historique git.
import subprocess  # noqa: E402

_baseline_dir = tempfile.mkdtemp(prefix="uam-baseline-tools-")
_baseline_dst = os.path.join(_baseline_dir, "tools_f4bf621.py")
_source = subprocess.run(
    ["git", "show", "f4bf621:tools.py"],
    cwd=REPO_ROOT, capture_output=True, check=True, text=True,
).stdout
with open(_baseline_dst, "w", encoding="utf-8") as f:
    f.write(_source)

sys.path.insert(0, _baseline_dir)  # pour `import tools_f4bf621`
sys.path.insert(0, REPO_ROOT)      # pour les dépendances (memory, app_config, ...) et `tools/`

import tools_f4bf621  # noqa: E402  (baseline, avant le chantier)
import importlib
import tools as tools_current  # noqa: E402  (état actuel)
importlib.reload(tools_current)

_check_baseline = tools_f4bf621.check_question_relevance.func
_check_current = tools_current.check_question_relevance.func


# ── Corpus : ≥ 40 phrases mêlant vraies questions d'étudiants et phrases
# hors sujet. Inclut nommément les exemples cités par le finding 1 qui
# relèvent de check_question_relevance (pas de detect_greeting — « Merci
# beaucoup, c'est parfait » est vérifié séparément, finding 2 ; pas non plus
# de relance elliptique du type « D'accord et ensuite ? », qui exige un
# accès à l'historique de conversation — BUG-10, hors périmètre de cette
# tâche).
CORPUS_VRAIES_QUESTIONS = [
    # Exemples cités tels quels par le finding 1
    "Quand sont les examens ?",
    "Je voudrais des renseignements",
    "Comment contacter mes enseignants",
    "Qu'est-ce qu'il faut faire après le bac ?",
    "Mon fils a eu son bac, que doit-il faire ?",
    # Variantes réalistes couvrant le même vocabulaire ajouté
    "Quelle est ma moyenne ce semestre ?",
    "Je veux connaître mes résultats d'examen",
    "Quand a lieu la rentrée universitaire ?",
    "Où se trouve le campus de la FAST ?",
    "Comment puis-je payer mes frais de scolarité ?",
    "Je n'ai pas encore reçu mon reçu de paiement",
    "Quelles matières sont enseignées en L1 ?",
    "Je veux m'inscrire pour la première fois",
    "Je souhaite m'inscrire en licence",
    "Comment m'inscrire à l'UAM ?",
    "Quel enseignant dois-je contacter pour ce cours ?",
    "J'ai raté un examen, que faire ?",
    "Puis-je avoir un renseignement sur les filières ?",
    "Quand débute le semestre prochain ?",
    "Quels sont mes résultats de fin d'année ?",
    "Comment consulter mes notes en ligne ?",
    # Formulations déjà couvertes avant la revue (non-régression interne)
    "Que propose la FA ?",
    "Quelles filières à la FAST ?",
    "Comment intégrer l'ENS ?",
    "Je veux m'inscrire à l'UAM",
    "Quelles formations à l'IRI ?",
    "Quels sont les frais d'inscription ?",
    "Comment obtenir mon relevé de notes ?",
    "Quelle est la procédure de réinscription ?",
    "Où est la faculté des sciences ?",
    "Quelles sont les conditions d'admission en master ?",
]

CORPUS_HORS_SUJET = [
    # Phrases réellement hors sujet et déjà HORS_SUJET en baseline (donc pas
    # concernées par le bug de BUG-04). Volontairement disjoint des phrases
    # de tests/test_bug_03_frais.py et tests/test_bug_05_accents.py
    # ("Il fait beau", "Je suis fatigué", "Le facteur est passé"...) : ces
    # phrases-là étaient de FAUX POSITIFS en baseline (contenaient "fa"/"ens"
    # en sous-chaîne) — leur bascule PERTINENT → HORS_SUJET est la correction
    # de BUG-04 elle-même, pas une perte. Elles sont déjà protégées par ces
    # fichiers de test (non modifiables) et n'ont pas leur place dans un
    # corpus qui mesure des pertes.
    "Quelle est la recette du couscous ?",
    "Quel temps fait-il à Niamey aujourd'hui ?",
    "Comment pirater le compte facebook d'un ami ?",
    "Quel est le score du match d'hier ?",
    "Le prix du mil a-t-il augmenté au marché ?",
    "Quel est le dernier film sorti au cinéma ?",
    "Peux-tu me raconter une blague ?",
    "Quelle est la capitale de la France ?",
    "Qui a gagné les élections présidentielles ?",
    "Où trouver un bon hôtel à Niamey ?",
    "Quelle est la recette du riz gras ?",
]

CORPUS = [(q, "VRAIE_QUESTION") for q in CORPUS_VRAIES_QUESTIONS] + \
         [(q, "HORS_SUJET_ATTENDU") for q in CORPUS_HORS_SUJET]


def main() -> int:
    assert len(CORPUS) >= 40, f"Corpus trop petit : {len(CORPUS)} phrases (minimum 40)"

    lignes = []
    pertes = []
    gains = 0
    identiques = 0

    for question, categorie in CORPUS:
        avant = _check_baseline(question=question)
        apres = _check_current(question=question)
        # Une PERTE au sens du finding 1 est spécifique aux vraies questions :
        # une phrase réellement liée à l'UAM qui était PERTINENT en baseline
        # et devient HORS_SUJET aujourd'hui. Pour les phrases hors sujet, la
        # même transition (PERTINENT → HORS_SUJET) est au contraire le
        # comportement voulu quand la baseline se trompait (c'est BUG-04) —
        # l'invariant à vérifier pour cette catégorie est simplement qu'elles
        # restent HORS_SUJET aujourd'hui.
        if categorie == "VRAIE_QUESTION" and avant == "PERTINENT" and apres == "HORS_SUJET":
            verdict = "PERTE"
            pertes.append((question, avant, apres))
        elif categorie == "HORS_SUJET_ATTENDU" and apres != "HORS_SUJET":
            verdict = "PERTE"
            pertes.append((question, avant, apres))
        elif avant == "HORS_SUJET" and apres == "PERTINENT":
            verdict = "GAIN"
            gains += 1
        else:
            verdict = "="
            identiques += 1
        lignes.append((categorie, question, avant, apres, verdict))

    # ── Tableau ──────────────────────────────────────────────────────────
    largeur_q = max(len(q) for _, q, _, _, _ in lignes)
    en_tete = f"{'catégorie':<19} {'question':<{largeur_q}} {'avant':<10} {'après':<10} verdict"
    print(en_tete)
    print("-" * len(en_tete))
    for categorie, question, avant, apres, verdict in lignes:
        print(f"{categorie:<19} {question:<{largeur_q}} {avant:<10} {apres:<10} {verdict}")

    print()
    print(f"Total : {len(lignes)} phrases — {gains} gains, {identiques} inchangées, {len(pertes)} pertes")

    if pertes:
        print("\nPERTES (doit être vide) :")
        for question, avant, apres in pertes:
            print(f"  - {question!r} : {avant} -> {apres}")
        return 1

    print("\nAucune perte. Critère de sortie du finding 1 satisfait.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

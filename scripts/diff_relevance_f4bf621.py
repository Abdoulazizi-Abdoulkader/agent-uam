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

Critère de sortie (non négociable), sur les deux corpus réunis :
1. Zéro PERTE parmi les vraies questions : aucune ligne où le verdict
   baseline est PERTINENT et le verdict actuel est HORS_SUJET — une vraie
   question qui serait désormais éconduite.
2. Zéro phrase hors sujet devenue PERTINENT aujourd'hui — sinon un
   vocabulaire élargi sans discernement viderait reject_query de son sens.
Les GAINS (HORS_SUJET → PERTINENT sur une vraie question) sont bienvenus et
ne font pas échouer le script.

Isolation : ce script importe `tools.py` de f4bf621 depuis une copie
temporaire (renommée pour ne pas entrer en collision avec le paquet `tools/`
actuel). Cette copie importe transitivement `memory.py`, qui ouvre une
connexion SQLite au chargement du module — les variables d'environnement
ci-dessous la détournent vers un fichier jetable, jamais vers
`user_memory.db` (voir CLAUDE.md : bases non versionnées à ne jamais
toucher).

Deux corpus, mesurés ensemble et jamais fusionnés silencieusement :
- CORPUS_CLAUDE_* : écrit lors du premier passage sur le finding 1.
- CORPUS_INDEPENDANT_* : re-revue post-finding-1. La re-revue a mesuré ce
  script sur un corpus qu'elle a construit indépendamment (24 vraies
  questions, 12 hors sujet) et trouvé une perte que CORPUS_CLAUDE_* ne
  couvrait pas (« Ma famille veut savoir si l'internat existe » — "internat"
  absent du vocabulaire). Corrigé (mot entier "internat", évite la collision
  avec "international"). Les deux corpus restent distincts pour qu'une
  correction future ne puisse plus passer l'un en échouant sur l'autre.
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


# ── Corpus 1/2 (CORPUS_CLAUDE_*) : ≥ 40 phrases mêlant vraies questions
# d'étudiants et phrases hors sujet, écrites lors du premier passage sur le
# finding 1. Inclut nommément les exemples cités par le finding 1 qui
# relèvent de check_question_relevance (pas de detect_greeting — « Merci
# beaucoup, c'est parfait » est vérifié séparément, finding 2 ; pas non plus
# de relance elliptique du type « D'accord et ensuite ? », qui exige un
# accès à l'historique de conversation — BUG-10, hors périmètre de cette
# tâche).
CORPUS_CLAUDE_VRAIES_QUESTIONS = [
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

CORPUS_CLAUDE_HORS_SUJET = [
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

# ── Corpus 2/2 (CORPUS_INDEPENDANT_*) : re-revue post-finding-1, construit
# indépendamment du corpus ci-dessus — c'est précisément ce qui lui a permis
# de trouver une perte que CORPUS_CLAUDE_* ne couvrait pas. Phrases reprises
# verbatim, ne pas paraphraser : un corpus de non-régression perd sa valeur
# de preuve si on le réécrit à sa main.
CORPUS_INDEPENDANT_VRAIES_QUESTIONS = [
    "Quand commencent les inscriptions ?",
    "Je veux m'inscrire en première année",
    "Quels sont les documents à fournir pour la rentrée ?",
    "Mon fils a eu son bac, quelles sont les démarches ?",
    "Y a-t-il des bourses pour les nouveaux bacheliers ?",
    "Où puis-je retirer mon relevé de notes ?",
    "Quelle est la moyenne exigée en médecine ?",
    "Comment se passe le paiement des frais ?",
    "Je cherche un logement près du campus",
    "Quelles matières sont enseignées en licence de droit ?",
    "À quelle date sortent les résultats du semestre ?",
    "Je suis en retard pour ma réinscription, que faire ?",
    "Comment obtenir une équivalence de mon diplôme ?",
    "Qui sont les enseignants de la faculté d'agronomie ?",
    "Il faut combien de temps pour finir une licence ?",
    "Ma famille veut savoir si l'internat existe",
    "Quand ont lieu les examens du premier semestre ?",
    "Je voudrais des renseignements sur le master",
    "Est-ce qu'il faut passer un concours pour entrer ?",
    "Comment faire pour changer de filière ?",
    "Bonjour, je veux étudier à l'UAM",
    "Quel est le montant de l'inscription en FAST ?",
    "Peut-on s'inscrire en ligne ?",
    "Les cours commencent quand cette année ?",
]

CORPUS_INDEPENDANT_HORS_SUJET = [
    "Comment faire une omelette au fromage ?",
    "Quelle est la capitale de l'Australie ?",
    "Donne-moi la recette du tiéboudienne",
    "Qui a gagné la coupe du monde 2022 ?",
    "Combien coûte un billet d'avion pour Paris ?",
    "Quel temps fera-t-il demain à Niamey ?",
    "Raconte-moi une blague",
    "Comment réparer une moto qui ne démarre pas ?",
    "Je cherche du travail dans une banque",
    "Quel est le prix du kilo de riz au marché ?",
    "Écris-moi un poème sur l'amour",
    "Quelles sont les frais à l'université française ?",
]

CORPUS = (
    [(q, "VRAIE_QUESTION", "claude") for q in CORPUS_CLAUDE_VRAIES_QUESTIONS] +
    [(q, "HORS_SUJET_ATTENDU", "claude") for q in CORPUS_CLAUDE_HORS_SUJET] +
    [(q, "VRAIE_QUESTION", "independant") for q in CORPUS_INDEPENDANT_VRAIES_QUESTIONS] +
    [(q, "HORS_SUJET_ATTENDU", "independant") for q in CORPUS_INDEPENDANT_HORS_SUJET]
)


def main() -> int:
    assert len(CORPUS) >= 40, f"Corpus trop petit : {len(CORPUS)} phrases (minimum 40)"

    lignes = []
    pertes = []
    gains_par_corpus = {"claude": 0, "independant": 0}
    identiques = 0

    for question, categorie, corpus in CORPUS:
        avant = _check_baseline(question=question)
        apres = _check_current(question=question)
        # Une PERTE au sens du finding 1 est spécifique aux vraies questions :
        # une phrase réellement liée à l'UAM qui était PERTINENT en baseline
        # et devient HORS_SUJET aujourd'hui. Pour les phrases hors sujet, la
        # même transition (PERTINENT → HORS_SUJET) est au contraire le
        # comportement voulu quand la baseline se trompait (c'est BUG-04) —
        # l'invariant à vérifier pour cette catégorie est simplement qu'elles
        # restent HORS_SUJET aujourd'hui (deuxième moitié du critère de
        # sortie : un vocabulaire élargi sans discernement viderait
        # reject_query de son sens).
        if categorie == "VRAIE_QUESTION" and avant == "PERTINENT" and apres == "HORS_SUJET":
            verdict = "PERTE"
            pertes.append((corpus, question, avant, apres))
        elif categorie == "HORS_SUJET_ATTENDU" and apres != "HORS_SUJET":
            verdict = "PERTE"
            pertes.append((corpus, question, avant, apres))
        elif avant == "HORS_SUJET" and apres == "PERTINENT":
            verdict = "GAIN"
            gains_par_corpus[corpus] += 1
        else:
            verdict = "="
            identiques += 1
        lignes.append((corpus, categorie, question, avant, apres, verdict))

    # ── Tableau ──────────────────────────────────────────────────────────
    largeur_q = max(len(q) for _, _, q, _, _, _ in lignes)
    en_tete = f"{'corpus':<12} {'catégorie':<19} {'question':<{largeur_q}} {'avant':<10} {'après':<10} verdict"
    print(en_tete)
    print("-" * len(en_tete))
    for corpus, categorie, question, avant, apres, verdict in lignes:
        print(f"{corpus:<12} {categorie:<19} {question:<{largeur_q}} {avant:<10} {apres:<10} {verdict}")

    gains = sum(gains_par_corpus.values())
    print()
    print(f"Total : {len(lignes)} phrases — {gains} gains "
          f"(claude : {gains_par_corpus['claude']}, indépendant : {gains_par_corpus['independant']}), "
          f"{identiques} inchangées, {len(pertes)} pertes")

    if pertes:
        print("\nPERTES (doit être vide) :")
        for corpus, question, avant, apres in pertes:
            print(f"  - [{corpus}] {question!r} : {avant} -> {apres}")
        return 1

    print("\nAucune perte sur les deux corpus. Critère de sortie satisfait "
          "(zéro perte, zéro hors-sujet devenu pertinent).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

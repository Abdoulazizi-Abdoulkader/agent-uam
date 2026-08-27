# tests/test_keywords_uam_corpus.py
"""Verrouille le vocabulaire ajouté à `keywords_uam` / `keywords_mot_entier`
dans `check_question_relevance` (finding 1 de la revue finale de branche,
commit `27f81f5`, complété par une re-revue indépendante, commit `b444648`).

BUG-04 a eu raison de resserrer la recherche des abréviations UAM (« fa »,
« ens »…) au mot entier — en sous-chaîne, elles matchaient « fait »,
« famille », « pense ». Mais ce match accidentel était aussi le seul filet
qui rattrapait de vraies questions d'étudiants, faute d'un vocabulaire assez
riche dans `keywords_uam`. Deux corpus, construits indépendamment l'un de
l'autre, ont mesuré ce trou et guidé les mots ajoutés :

- CORPUS_CLAUDE_* : écrit au premier passage sur le finding 1 (31 vraies
  questions, 11 phrases hors sujet).
- CORPUS_INDEPENDANT_* : construit par une re-revue sans connaissance du
  corpus ci-dessus (24 vraies questions, 12 phrases hors sujet) — c'est
  précisément cette indépendance qui lui a permis de trouver une perte que
  CORPUS_CLAUDE_* ne couvrait pas (« Ma famille veut savoir si l'internat
  existe » — "internat" absent du vocabulaire, corrigé en mot entier dans
  le même commit `b444648` pour éviter la collision avec "international").
  Phrases reprises verbatim, à ne pas paraphraser : un corpus de
  non-régression perd sa valeur de preuve si on le réécrit à sa main.

Ce fichier remplace `scripts/diff_relevance_f4bf621.py` (supprimé), qui
comparait ces corpus à l'état d'avant le chantier (commit `f4bf621`) pour
prouver l'absence de perte au moment du correctif. Cette comparaison était
l'outil qui a guidé la correction, pas l'invariant à conserver : ces tests
verrouillent directement le comportement voulu **aujourd'hui**, pour qu'une
correction future qui resserrerait un de ces mots ne puisse pas rouvrir
silencieusement les faux négatifs que ce vocabulaire a fermés.

Dette connue, volontairement non couverte ici : une re-revue a trouvé sept
tournures où ce même vocabulaire élargi (« matière », « examen », « note »,
« résultat », « bac »…) attrape aussi une question hors sujet en sous-chaîne
ou en mot entier trop large (« matières premières », « examen médical »,
« c'est noté », « résultat du match », « le bac [ferry] du fleuve Niger »).
Faux positifs bénins assumés au sens du critère du dépôt (un faux négatif
est grave, un faux positif ne fait au pire que répondre à côté) —
documentés et remontés par la revue à l'auteur, qui tranchera avec sa
connaissance de ses utilisateurs. Aucune des deux corpus ci-dessous ne
contient ces tournures : si une future revue les ajoute, elles doivent
aller dans une classe séparée à la `TestFauxPositifsAssumes` de
`tests/test_bug_05_accents.py`, jamais mélangées aux phrases hors sujet
« franches » ci-dessous.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools import check_question_relevance

CORPUS_CLAUDE_VRAIES_QUESTIONS = [
    'Quand sont les examens ?',
    'Je voudrais des renseignements',
    'Comment contacter mes enseignants',
    "Qu'est-ce qu'il faut faire après le bac ?",
    'Mon fils a eu son bac, que doit-il faire ?',
    'Quelle est ma moyenne ce semestre ?',
    "Je veux connaître mes résultats d'examen",
    'Quand a lieu la rentrée universitaire ?',
    'Où se trouve le campus de la FAST ?',
    'Comment puis-je payer mes frais de scolarité ?',
    "Je n'ai pas encore reçu mon reçu de paiement",
    'Quelles matières sont enseignées en L1 ?',
    "Je veux m'inscrire pour la première fois",
    "Je souhaite m'inscrire en licence",
    "Comment m'inscrire à l'UAM ?",
    'Quel enseignant dois-je contacter pour ce cours ?',
    "J'ai raté un examen, que faire ?",
    'Puis-je avoir un renseignement sur les filières ?',
    'Quand débute le semestre prochain ?',
    "Quels sont mes résultats de fin d'année ?",
    'Comment consulter mes notes en ligne ?',
    'Que propose la FA ?',
    'Quelles filières à la FAST ?',
    "Comment intégrer l'ENS ?",
    "Je veux m'inscrire à l'UAM",
    "Quelles formations à l'IRI ?",
    "Quels sont les frais d'inscription ?",
    'Comment obtenir mon relevé de notes ?',
    'Quelle est la procédure de réinscription ?',
    'Où est la faculté des sciences ?',
    "Quelles sont les conditions d'admission en master ?",
]

CORPUS_CLAUDE_HORS_SUJET = [
    'Quelle est la recette du couscous ?',
    "Quel temps fait-il à Niamey aujourd'hui ?",
    "Comment pirater le compte facebook d'un ami ?",
    "Quel est le score du match d'hier ?",
    'Le prix du mil a-t-il augmenté au marché ?',
    'Quel est le dernier film sorti au cinéma ?',
    'Peux-tu me raconter une blague ?',
    'Quelle est la capitale de la France ?',
    'Qui a gagné les élections présidentielles ?',
    'Où trouver un bon hôtel à Niamey ?',
    'Quelle est la recette du riz gras ?',
]

CORPUS_INDEPENDANT_VRAIES_QUESTIONS = [
    'Quand commencent les inscriptions ?',
    "Je veux m'inscrire en première année",
    'Quels sont les documents à fournir pour la rentrée ?',
    'Mon fils a eu son bac, quelles sont les démarches ?',
    'Y a-t-il des bourses pour les nouveaux bacheliers ?',
    'Où puis-je retirer mon relevé de notes ?',
    'Quelle est la moyenne exigée en médecine ?',
    'Comment se passe le paiement des frais ?',
    'Je cherche un logement près du campus',
    'Quelles matières sont enseignées en licence de droit ?',
    'À quelle date sortent les résultats du semestre ?',
    'Je suis en retard pour ma réinscription, que faire ?',
    'Comment obtenir une équivalence de mon diplôme ?',
    "Qui sont les enseignants de la faculté d'agronomie ?",
    'Il faut combien de temps pour finir une licence ?',
    "Ma famille veut savoir si l'internat existe",
    'Quand ont lieu les examens du premier semestre ?',
    'Je voudrais des renseignements sur le master',
    "Est-ce qu'il faut passer un concours pour entrer ?",
    'Comment faire pour changer de filière ?',
    "Bonjour, je veux étudier à l'UAM",
    "Quel est le montant de l'inscription en FAST ?",
    "Peut-on s'inscrire en ligne ?",
    'Les cours commencent quand cette année ?',
]

CORPUS_INDEPENDANT_HORS_SUJET = [
    'Comment faire une omelette au fromage ?',
    "Quelle est la capitale de l'Australie ?",
    'Donne-moi la recette du tiéboudienne',
    'Qui a gagné la coupe du monde 2022 ?',
    "Combien coûte un billet d'avion pour Paris ?",
    'Quel temps fera-t-il demain à Niamey ?',
    'Raconte-moi une blague',
    'Comment réparer une moto qui ne démarre pas ?',
    'Je cherche du travail dans une banque',
    'Quel est le prix du kilo de riz au marché ?',
    "Écris-moi un poème sur l'amour",
    "Quelles sont les frais à l'université française ?",
]


class TestCorpusClaudeVraiesQuestionsSontPertinentes:
    """31 vraies questions d'étudiants (corpus « claude », premier passage
    sur le finding 1) — l'acquis à protéger : chacune doit rester PERTINENT."""

    @pytest.mark.parametrize("question", CORPUS_CLAUDE_VRAIES_QUESTIONS)
    def test_question_est_pertinente(self, question):
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestCorpusClaudeHorsSujetResteHorsSujet:
    """11 phrases hors sujet du même corpus — non-régression : le
    vocabulaire ajouté au finding 1 ne doit pas les faire basculer PERTINENT."""

    @pytest.mark.parametrize("question", CORPUS_CLAUDE_HORS_SUJET)
    def test_question_reste_hors_sujet(self, question):
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestCorpusIndependantVraiesQuestionsSontPertinentes:
    """24 vraies questions d'étudiants nigériens (corpus « indépendant »,
    construit par une re-revue sans connaissance du corpus « claude » —
    c'est ce qui lui a permis de trouver « internat » manquant). L'acquis à
    protéger : chacune doit rester PERTINENT."""

    @pytest.mark.parametrize("question", CORPUS_INDEPENDANT_VRAIES_QUESTIONS)
    def test_question_est_pertinente(self, question):
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestCorpusIndependantHorsSujetResteHorsSujet:
    """12 phrases hors sujet du même corpus indépendant — non-régression."""

    @pytest.mark.parametrize("question", CORPUS_INDEPENDANT_HORS_SUJET)
    def test_question_reste_hors_sujet(self, question):
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

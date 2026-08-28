# tests/test_routage_hors_sujet.py
"""Précision du routage hors sujet : un mot générique seul ne suffit plus.

Contexte — arbitrage du 2026-08-28. La revue finale de branche avait signalé
« sept tournures » où le vocabulaire élargi de `keywords_uam` attrape une
question hors sujet, et les avait laissées comme faux positifs bénins, au nom
du critère du dépôt (un faux négatif éconduit une vraie question, un faux
positif ne fait au pire que répondre à côté). L'auteur a tranché l'inverse
pour la soutenance : **devant un jury qui teste les limites, un agent qui
accepte tout paraît moins maîtrisé**.

Remesuré avant correction, le défaut est plus large que sept tournures : ce
n'est pas une liste de cas à rustiner, c'est le mécanisme. `keywords_uam`
cherche en sous-chaîne des mots franchement génériques du français courant
(« cours », « service », « dossier », « note », « moyenne », « résultat »,
« matière », « pièces »…) et **un seul suffit** à classer PERTINENT. Mesuré
sur le corpus ci-dessous via `route_and_store` (le chemin réellement vécu par
l'utilisateur, pas l'outil isolé que la revue avait mesuré) : **21/21
messages hors sujet atteignaient l'agent**.

Mécanisme retenu — deux étages, plutôt qu'une liste de sept correctifs :

1. `keywords_forts` : les mots qui n'ont pas d'autre sens courant hors du
   contexte universitaire (« faculté », « inscription », « licence »,
   « semestre »…) déclenchent PERTINENT seuls, comme avant.
2. `keywords_faibles` : les mots génériques ne déclenchent PERTINENT que si
   la phrase ne porte **aucun marqueur de domaine concurrent**
   (`_DOMAINE_CONCURRENT_RE` : sport, santé, justice, commerce, transport
   fluvial, énergie…).

Propriété importante du garde-fou : un marqueur concurrent **saute l'étage
faible, il ne rejette pas**. Les mécanismes suivants (`uam_geo_patterns`,
`external_patterns`, `education_phrases`) peuvent toujours rattraper la
phrase — « payer les frais à la banque » reste PERTINENT via « les frais »
bien que « banque » soit un marqueur concurrent.

Ce fichier est le pendant en précision de `tests/test_keywords_uam_corpus.py`,
qui verrouille le rappel. Les deux doivent rester verts ensemble : c'est la
seule preuve que la précision gagnée ici ne s'est pas payée en vraies
questions éconduites.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_nodes import route_and_store
from tools import check_question_relevance

from test_keywords_uam_corpus import (
    CORPUS_CLAUDE_VRAIES_QUESTIONS,
    CORPUS_INDEPENDANT_VRAIES_QUESTIONS,
)

# Phrases hors sujet portant chacune au moins un mot générique de
# `keywords_uam`. Mesurées PERTINENT avant correction (21/21).
CORPUS_HORS_SUJET_GENERIQUE = [
    # "cours"
    "Le cours du pétrole a encore monté cette semaine",
    # "service"
    "Quel est le service client de Airtel Niger ?",
    "Le service de renseignement a démenti l'information",
    # "dossier"
    "Le dossier de l'affaire a été classé par le tribunal",
    # "pièces"
    "Où acheter des pièces détachées pour ma moto ?",
    # "calendrier"
    "Quel est le calendrier des matchs de la CAN ?",
    # "logement"
    "Je cherche un logement à louer à Lazaret",
    # "restauration"
    "La restauration de la mosquée a coûté cher",
    # "examen"
    "J'ai un examen médical demain à l'hôpital",
    # "note"
    "C'est noté",
    # "moyenne"
    "Quelle est la moyenne d'âge de la population du Niger ?",
    # "paiement"
    "Quels sont les modes de paiement acceptés par Orange Money ?",
    # "matière"
    "Le prix des matières premières a-t-il augmenté ?",
    # "résultat"
    "Quel est le résultat du match d'hier soir ?",
    # "horaire"
    "Quels sont les horaires d'ouverture de la banque ?",
    # "bac" (le bac-ferry du fleuve Niger, pas le baccalauréat)
    "Le bac du fleuve Niger fonctionne-t-il aujourd'hui ?",
    "Combien coûte la traversée en bac à Gaya ?",
    # "thèse" en sous-chaîne — BUG-06, corrigé ici par le mot entier
    "Quelle est ton hypothèse sur cette affaire ?",
    "Fais une synthèse de ce texte",
    # "relevé" homographe du verbe conjugué — BUG-06
    "Il a été relevé de ses fonctions par le ministre",
    # Deuxième passe de mesure, corpus « jury » : quatre fuites restantes,
    # dont deux dues au pluriel manquant des motifs de `_OFF_TOPIC_RE`
    # (`\belection\b` ne matchait pas « élections »).
    "Quel est le cours du dollar aujourd'hui ?",
    "Quel est le résultat des élections au Sénégal ?",
    "Le bac de Farié est-il en panne ?",
    "Quelle est la moyenne des températures à Niamey ?",
]

# Vraies questions exerçant spécifiquement les mots passés en mot entier par
# ce chantier ("thèse", "formation", "institut", "recteur") : le resserrement
# ne doit rien leur coûter.
CORPUS_MOTS_PASSES_EN_MOT_ENTIER = [
    "Je veux faire une thèse en agronomie",
    "Quelles formations propose la FAST ?",
    "Y a-t-il un institut de formation en informatique ?",
    "Qui est le recteur de l'UAM ?",
    "Quels sont les instituts rattachés à l'université Abdou Moumouni ?",
]


class TestHorsSujetGeneriqueEstRejete:
    """Un mot générique seul ne fait plus entrer une question hors sujet."""

    @pytest.mark.parametrize("question", CORPUS_HORS_SUJET_GENERIQUE)
    def test_outil_classe_hors_sujet(self, question):
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", CORPUS_HORS_SUJET_GENERIQUE)
    def test_routage_reel_rejette(self, question):
        """Mesure sur le chemin réel : `route_and_store`, pas l'outil isolé.

        C'est la mesure qui compte pour l'auteur — ce que le jury verra.
        """
        etat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert etat["routing_hint"] == "reject_query"


class TestMotsPassesEnMotEntier:
    """« thèse », « formation », « institut », « recteur » cherchés en mot
    entier : la collision de sous-chaîne disparaît sans perte de rappel.

    Mesuré avant correction : « hypothèse »/« synthèse » contenaient
    « thèse » (BUG-06), « l'information » contenait « formation »,
    « directeur » contenait « recteur », « institution » contenait
    « institut ».
    """

    @pytest.mark.parametrize("question", CORPUS_MOTS_PASSES_EN_MOT_ENTIER)
    def test_vraie_question_reste_pertinente(self, question):
        assert check_question_relevance.func(question=question) == "PERTINENT"

    @pytest.mark.parametrize("question", [
        "Le service de renseignement a démenti l'information",
        "Qui est le directeur de la banque ?",
        "Cette institution est-elle fiable ?",
    ])
    def test_collision_sous_chaine_fermee(self, question):
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestNonRegressionVraiesQuestions:
    """Le rappel ne doit pas être payé en vraies questions éconduites.

    Les 55 questions des deux corpus verrouillés par
    `tests/test_keywords_uam_corpus.py` sont rejouées ici sur le chemin réel
    (`route_and_store`), pas seulement sur l'outil : c'est l'invariant qui
    interdit de gagner la précision ci-dessus en resserrant trop.
    """

    @pytest.mark.parametrize(
        "question",
        CORPUS_CLAUDE_VRAIES_QUESTIONS + CORPUS_INDEPENDANT_VRAIES_QUESTIONS,
    )
    def test_vraie_question_atteint_agent(self, question):
        etat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert etat["routing_hint"] != "reject_query"


class TestGardeFouSauteSansRejeter:
    """Un marqueur de domaine concurrent saute l'étage faible, il ne rejette pas.

    Sans cette propriété, le garde-fou transformerait chaque marqueur en
    rejet définitif et rouvrirait les faux négatifs que le finding 1 de la
    revue finale de branche avait fermés.
    """

    @pytest.mark.parametrize("question", [
        # "banque" est un marqueur concurrent, mais "les frais" (education_phrases)
        # rattrape la phrase en aval du garde-fou.
        "Puis-je payer les frais à la banque ?",
        # "banque" est un marqueur concurrent, mais "inscription" est un mot fort.
        "Faut-il payer l'inscription à la banque ou en ligne ?",
        # "hôpital" est un marqueur concurrent, mais "faculté" est un mot fort.
        "Où est la faculté de médecine par rapport à l'hôpital national ?",
    ])
    def test_phrase_uam_avec_marqueur_concurrent_reste_pertinente(self, question):
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestEcartsResiduelsAssumes:
    """Ce que ce mécanisme ne peut pas trancher, et qu'on n'a pas prétendu clore.

    Une règle textuelle ne distingue pas ces emplois sans analyse sémantique.
    Ils restent PERTINENT (l'agent répond à côté) faute d'un marqueur de
    domaine concurrent dans la phrase. Documentés ici plutôt que masqués :
    même convention que `TestFauxPositifsAssumes` de
    `tests/test_bug_07_etudiant_etranger.py`.
    """

    @pytest.mark.parametrize("question", [
        # "dossier" dans un sens professionnel, sans marqueur de domaine.
        "Mon patron m'a demandé un dossier complet sur le projet",
        # "note" au sens d'un mot laissé, sans marqueur de domaine.
        "Il a laissé une note sur la porte",
        # "cours" au sens temporel, sans marqueur de domaine.
        "Au cours de la réunion, personne n'a pris la parole",
    ])
    def test_ecart_residuel_reste_pertinent(self, question):
        assert check_question_relevance.func(question=question) == "PERTINENT"

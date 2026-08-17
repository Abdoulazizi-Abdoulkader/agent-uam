"""BUG-05 : les questions tapées sans accents sont rejetées.

Les mots-clés de keywords_uam sont accentués et la comparaison est littérale.
La saisie sans accents est courante sur téléphone et clavier QWERTY.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PAIRES = [
    ("Comment se réinscrire ?", "Comment se reinscrire ?"),
    ("Quelles sont les filières ?", "Quelles sont les filieres ?"),
    ("Où est la faculté ?", "Ou est la faculte ?"),
    ("Quel diplôme obtient-on ?", "Quel diplome obtient-on ?"),
    ("Comment obtenir mon relevé de notes ?", "Comment obtenir mon releve de notes ?"),
    # Formulation courte sans "de notes" : "relevé" est reconnu en mot
    # entier (pluriel optionnel), via keywords_mot_entier — voir
    # TestReleveMotEntier pour la couverture complète des formulations
    # génériques ("un relevé", "mes relevés de notes"...).
    ("Comment obtenir mon relevé ?", "Comment obtenir mon releve ?"),
    ("Quelle est la procédure de préinscription ?", "Quelle est la procedure de preinscription ?"),
    ("Y a-t-il une cité universitaire ?", "Y a-t-il une cite universitaire ?"),
]


class TestInsensibiliteAuxAccents:

    @pytest.mark.parametrize("avec,sans", PAIRES)
    def test_les_deux_formes_sont_classees_pareil(self, avec, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == \
               check_question_relevance.func(question=avec)

    @pytest.mark.parametrize("_,sans", PAIRES)
    def test_la_forme_sans_accents_est_pertinente(self, _, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == "PERTINENT"


class TestPasDeRegression:
    """La normalisation ne doit pas rouvrir les faux positifs de BUG-03 et BUG-04."""

    @pytest.mark.parametrize("question", [
        "Il fait frais ce matin",
        "Comment faire une omelette ?",
        "Ma famille habite à Zinder",
        "Je pense que c'est une bonne idée",
        "Le facteur est passé",
        "Quelle est la recette du couscous ?",
    ])
    def test_les_phrases_hors_sujet_le_restent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        # BUG-05 (revue) : "relevé" désaccentué ("releve") était une
        # sous-chaîne littérale de "relever" — un faux positif entièrement
        # nouveau, introduit par la normalisation elle-même. Ces cas
        # gardent la garde-fou pour ce type de régression (un mot-clé
        # accentué qui, une fois désaccentué, chevauche un mot sans
        # rapport), pas seulement pour "relevé".
        "Il faut relever le defi",
        "Elle a su relever la tête après l'échec",
        "Le comité a dû relever plusieurs incohérences dans le rapport",
    ])
    def test_les_mots_qui_contiennent_un_mot_cle_desaccentue_restent_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        "Que propose la FA ?",
        "Comment intégrer l'ENS ?",
        "Quels sont les frais ?",
        "Quelles filières à la FAST ?",
    ])
    def test_les_acquis_des_taches_precedentes_tiennent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestReleveMotEntier:
    """BUG-05, trois revues sur le même mot-clé.

    Round 2 : resserrer "relevé" en "relevé de notes" / "mon relevé" a
    perdu les formulations génériques — article indéfini ("un relevé"),
    forme nue ("relevé de notes" sans "mon"), pluriel ("mes relevés de
    notes"). Un mot entier isolé ("relevé"/"relevés", \\b...\\b) les a
    restaurées sans rouvrir la collision avec l'infinitif "relever" (le
    "r" final bloque la frontière de mot).

    Round 3 : le nom "relevé" et le verbe conjugué "relève"/"relèves" sont
    des homographes exacts une fois désaccentués ("releve" des deux
    côtés) — \\b ne peut pas les distinguer, ils ne diffèrent pas en tant
    que chaînes. keywords_mot_entier (tools.py) revient donc à des
    tournures à déterminant explicite ("un relevé", "le relevé"...), un
    verbe conjugué n'étant jamais précédé d'un déterminant — mais
    toujours comparées en mot entier (\\b en tête de motif) : une simple
    sous-chaîne collisionnerait encore, "elle relève" contenant
    littéralement "le relevé" une fois désaccentué ("elle" se terminant
    par "le")."""

    @pytest.mark.parametrize("question", [
        "Je veux mon relevé de notes",
        "Je veux mon releve de notes",
        "relevé de notes",
        "releve de notes",
        "mon releve",
        "mon relevé",
        "Comment obtenir un relevé ?",
        "Comment obtenir un releve ?",
        "Je veux un relevé",
        "Je veux un releve",
        "un relevé svp",
        "un releve svp",
        "mes relevés de notes",
        "mes releves de notes",
    ])
    def test_les_formulations_generiques_sont_pertinentes(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"

    def test_relever_reste_hors_sujet(self):
        """Compagnon accentué de TestPasDeRegression::...["Il faut relever
        le defi"] : la reconnaissance en mot entier ne doit pas rouvrir la
        collision, accents ou pas."""
        from tools import check_question_relevance
        assert check_question_relevance.func(question="Il faut relever le défi") == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        # Round 3 : "relève"/"relèves" (présent de l'indicatif) sont des
        # homographes exacts de "relevé" une fois désaccentués — l'angle
        # mort qui a laissé passer deux régressions successives, faute de
        # tester une conjugaison autre que l'infinitif.
        "Ce village relève de la commune de Zinder",
        "Ce village releve de la commune de Zinder",
        "Elle relève la tête après l'échec",
        "Elle releve la tete apres l echec",
        "Le proviseur relève une anomalie",
        "Le proviseur releve une anomalie",
        "Tu relèves un défi chaque jour",
        "Tu releves un defi chaque jour",
        # "relève" est aussi un nom féminin (la relève) distinct du
        # document ; "la relevé" n'est délibérément pas dans
        # keywords_mot_entier pour cette raison.
        "Il faut prendre la relève",
        "Il faut prendre la releve",
    ])
    def test_les_formes_conjuguees_de_relever_restent_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestHelperSansAccents:

    @pytest.mark.parametrize("entree,attendu", [
        ("réinscrire", "reinscrire"),
        ("filière", "filiere"),
        ("diplôme", "diplome"),
        ("où", "ou"),
        ("cité universitaire", "cite universitaire"),
        ("sans accent", "sans accent"),
        ("", ""),
    ])
    def test_normalisation(self, entree, attendu):
        from tools import _sans_accents
        assert _sans_accents(entree) == attendu

    def test_la_casse_n_est_pas_modifiee(self):
        """Le helper normalise les accents, pas la casse : les deux
        responsabilités restent séparées."""
        from tools import _sans_accents
        assert _sans_accents("FACULTÉ") == "FACULTE"


class TestRoutage:

    @pytest.mark.parametrize("question", [
        "Ou est la faculte ?",
        "Comment se reinscrire ?",
        "Quelles sont les filieres ?",
    ])
    def test_les_questions_sans_accents_atteignent_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"

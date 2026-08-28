# tests/test_sec_01_dossier_etudiant.py
"""SEC-01 — le dossier étudiant n'est plus consultable sur le seul matricule.

Contexte — arbitrage du 2026-08-28. L'audit avait reporté SEC-01 en jugeant
le risque « actuellement nul », la base ne contenant que 58 étudiants
simulés, assorti d'un avertissement écrit. L'auteur a répondu que la base
portera en production les vraies données de scolarité de l'UAM : la faille se
transporte alors avec le code, et l'avertissement ne suffit plus.

Décision retenue : garder la démonstration jouable sur la base simulée, mais
**verrouiller l'accès par un second facteur** — la date de naissance, déjà
présente dans la table `etudiants`. Ce n'est pas une authentification (il
n'y a pas de session étudiant dans cette application, et en écrire une
dépasse ce chantier) ; c'est la barrière que le schéma existant permet de
poser sans en inventer une. L'authentification complète reste à faire au
moment du passage en production — voir l'entrée SEC-01 de l'audit.

Ce que ces tests verrouillent, au-delà du « il faut une date » :

1. **Aucune fuite partielle** sans le second facteur — pas de nom, pas de
   montant, pas de statut.
2. **Pas d'énumération** : un matricule inexistant et une date incorrecte
   produisent le *même* message, au caractère près. Sans cela, l'outil
   resterait un oracle permettant de découvrir quels matricules existent —
   la moitié de la faille d'origine, sur une base réelle.
3. **Non-divulgation** : la date de naissance ne ressort jamais dans la
   réponse, et ne quitte même pas la couche base de données (la
   vérification renvoie un booléen, pas la valeur).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CHEMIN_BASE = os.path.join(os.path.dirname(__file__), "..", "database", "scolarite_uam.db")

# Étudiant simulé de référence (database/simulation_scolarite.py, graine fixe).
MATRICULE = "UAM030001"
DATE_NAISSANCE = "2003-05-05"
NOM_ATTENDU = "Saidou"
MATRICULE_INEXISTANT = "UAM999999"


@pytest.fixture(autouse=True)
def _config_non_empoisonnee():
    """Même neutralisation de BUG-08 que tests/test_database_connector.py."""
    import app_config
    app_config._config = None


def _consulter(**kwargs):
    from tools import search_student_record
    return search_student_record.invoke({"matricule": MATRICULE, **kwargs})


class TestRefusSansSecondFacteur:
    """Le seul matricule ne suffit plus — c'est la faille SEC-01 elle-même."""

    def test_sans_date_le_dossier_n_est_pas_rendu(self):
        reponse = _consulter()
        assert NOM_ATTENDU not in reponse
        assert "Statut d'inscription" not in reponse
        assert "FCFA" not in reponse

    def test_sans_date_l_agent_sait_quoi_demander(self):
        """Le message doit permettre au LLM de réclamer la date à l'utilisateur."""
        reponse = _consulter().lower()
        assert "date de naissance" in reponse

    def test_date_vide_ou_blanche_equivaut_a_absente(self):
        for saisie in ("", "   ", "\t"):
            reponse = _consulter(date_naissance=saisie)
            assert NOM_ATTENDU not in reponse
            assert "date de naissance" in reponse.lower()


@pytest.mark.skipif(not os.path.exists(CHEMIN_BASE), reason="database/scolarite_uam.db absente")
class TestRefusSurSecondFacteurIncorrect:

    def test_mauvaise_date_ne_rend_pas_le_dossier(self):
        reponse = _consulter(date_naissance="01/01/1990", query_type="general")
        assert NOM_ATTENDU not in reponse
        assert "FCFA" not in reponse

    def test_pas_d_oracle_d_enumeration(self):
        """Matricule inexistant et date incorrecte : message identique.

        Sinon l'outil reste un oracle permettant de découvrir quels
        matricules existent — la moitié de la faille SEC-01 d'origine.
        """
        from tools import search_student_record
        mauvaise_date = search_student_record.invoke(
            {"matricule": MATRICULE, "date_naissance": "01/01/1990"}
        )
        matricule_inconnu = search_student_record.invoke(
            {"matricule": MATRICULE_INEXISTANT, "date_naissance": "01/01/1990"}
        )
        assert mauvaise_date == matricule_inconnu

    def test_le_refus_ne_repete_pas_le_matricule(self):
        """Le matricule sondé ne doit pas être renvoyé en écho : un message
        qui le reprend distingue déjà, à l'œil, un refus d'un autre."""
        reponse = _consulter(date_naissance="01/01/1990")
        assert MATRICULE not in reponse


@pytest.mark.skipif(not os.path.exists(CHEMIN_BASE), reason="database/scolarite_uam.db absente")
class TestAccesAvecSecondFacteurValide:
    """La démonstration reste jouable : la bonne date ouvre le dossier."""

    def test_bonne_date_rend_le_dossier(self):
        reponse = _consulter(date_naissance=DATE_NAISSANCE, query_type="general")
        assert NOM_ATTENDU in reponse
        assert "Statut d'inscription" in reponse

    @pytest.mark.parametrize("saisie", [
        "2003-05-05",   # format de la base
        "05/05/2003",   # format usuel à l'oral et à l'écrit
        "5/5/2003",     # sans zéro initial
        "05-05-2003",   # tirets
        "05.05.2003",   # points
        " 05/05/2003 ", # espaces parasites
        "5 mai 2003",   # mois en toutes lettres
    ])
    def test_formats_de_date_acceptes(self, saisie):
        """L'utilisateur tape sa date comme il la dit, pas au format SQL."""
        reponse = _consulter(date_naissance=saisie)
        assert NOM_ATTENDU in reponse

    @pytest.mark.parametrize("saisie", [
        "05/06/2003",   # bon jour, mauvais mois
        "06/05/2003",   # jour et mois permutés
        "05/05/2002",   # mauvaise année
        "n'importe quoi",
    ])
    def test_formats_proches_mais_faux_sont_refuses(self, saisie):
        reponse = _consulter(date_naissance=saisie)
        assert NOM_ATTENDU not in reponse


@pytest.mark.skipif(not os.path.exists(CHEMIN_BASE), reason="database/scolarite_uam.db absente")
class TestNonDivulgationDeLaDate:
    """Le second facteur ne doit pas devenir lui-même une fuite."""

    def test_la_date_n_apparait_pas_dans_le_dossier_rendu(self):
        reponse = _consulter(date_naissance=DATE_NAISSANCE, query_type="general")
        assert DATE_NAISSANCE not in reponse
        assert "05/05/2003" not in reponse

    def test_la_date_ne_quitte_pas_la_couche_base_de_donnees(self):
        """`search_students_db` ne doit pas rapatrier la date de naissance.

        La vérification se fait par une fonction dédiée qui renvoie un
        booléen : la valeur ne circule pas dans le dictionnaire que les
        outils formatent, donc aucun outil futur ne peut l'imprimer par
        inadvertance.
        """
        from database_connector import search_students_db
        etudiants = search_students_db(student_id=MATRICULE)
        assert etudiants, "étudiant de référence introuvable"
        champs = " ".join(str(v) for v in etudiants[0].values())
        assert DATE_NAISSANCE not in champs

    def test_la_verification_renvoie_un_booleen(self):
        from database_connector import verify_student_birthdate
        assert verify_student_birthdate(MATRICULE, DATE_NAISSANCE) is True
        assert verify_student_birthdate(MATRICULE, "01/01/1990") is False
        assert verify_student_birthdate(MATRICULE_INEXISTANT, DATE_NAISSANCE) is False

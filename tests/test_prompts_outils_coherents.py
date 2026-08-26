# tests/test_prompts_outils_coherents.py
"""Le guide d'outils de prompts.py doit rester aligné avec tools.get_tools().

build_tool_system_prompt() est appelée à chaque tour de l'agent
(graph_nodes.py:300) et construit un texte statique qui recommande au LLM des
outils par nom. Si ce texte nomme un outil que get_tools() n'expose pas dans
la même configuration, le LLM reçoit une instruction qu'il ne peut pas
honorer. C'est exactement le gap relevé en revue de la tâche 14 (round 1,
finding 1) : après l'introduction des drapeaux _db_backend_supporte_actualites
(BUG-01) et _db_backend_supporte_horaires (BUG-11), le guide continuait à
nommer search_latest_news et get_schedules_from_db sans condition.

Ce test est volontairement général : il ne code en dur ni "search_latest_news"
ni "get_schedules_from_db", mais dérive l'univers des noms d'outils possibles
de tools.get_tools() lui-même (configuration où la base est disponible et où
le backend documentaire supporte tout), pour attraper toute divergence future
entre le guide et l'inventaire — pas seulement celle déjà connue.

Étendu en revue round 2 (tâche 14) : `_db_available=False` est maintenant
couvert (test_installation_neuve_sans_base). `search_student_record` était
nommé dans le guide sans condition sur `_db_available`, alors que
`database/scolarite_uam.db` n'est pas versionnée (`*.db` dans .gitignore) —
`_db_available=False` n'est donc pas un cas limite mais le cas nominal de
toute installation neuve (clone du dépôt, jury, autre machine). Corrigé dans
prompts.py : la mention de search_student_record est désormais conditionnée
au même titre que search_latest_news et get_schedules_from_db.
"""
import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import prompts
import tools


def _univers_noms_outils() -> frozenset:
    """Tous les noms d'outils possibles : base disponible, backend documentaire
    complet (actualités + horaires) simulé."""
    with patch.object(tools, "_db_available", True), \
         patch.object(tools, "_db_backend_supporte_actualites", True), \
         patch.object(tools, "_db_backend_supporte_horaires", True):
        return frozenset(t.name for t in tools.get_tools())


def _noms_mentionnes(texte: str, univers: frozenset) -> set:
    return {nom for nom in univers if re.search(rf"\b{re.escape(nom)}\b", texte)}


UNIVERS = _univers_noms_outils()


class TestGuideOutilsCoherentAvecInventaire:

    def test_configuration_reelle(self):
        """Sans aucun patch : reflète l'environnement réel de l'utilisateur
        (UAM_DB_TYPE=sqlite à la date de ce test)."""
        texte = prompts.build_tool_system_prompt()
        exposes = {t.name for t in tools.get_tools()}
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        absents_mais_mentionnes = mentionnes - exposes
        assert not absents_mais_mentionnes, (
            f"Le guide nomme {absents_mais_mentionnes}, absent(s) de "
            "get_tools() dans la configuration réelle."
        )

    def test_sqlite_sans_actualites_ni_horaires(self):
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", False), \
             patch.object(tools, "_db_backend_supporte_horaires", False):
            texte = prompts.build_tool_system_prompt()
            exposes = {t.name for t in tools.get_tools()}
        assert "search_latest_news" not in texte
        assert "get_schedules_from_db" not in texte
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        assert mentionnes <= exposes

    def test_actualites_supportees_horaires_absentes(self):
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", True), \
             patch.object(tools, "_db_backend_supporte_horaires", False):
            texte = prompts.build_tool_system_prompt()
            exposes = {t.name for t in tools.get_tools()}
        assert "search_latest_news" in texte
        assert "get_schedules_from_db" not in texte
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        assert mentionnes <= exposes

    def test_horaires_supportees_actualites_absentes(self):
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", False), \
             patch.object(tools, "_db_backend_supporte_horaires", True):
            texte = prompts.build_tool_system_prompt()
            exposes = {t.name for t in tools.get_tools()}
        assert "get_schedules_from_db" in texte
        assert "search_latest_news" not in texte
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        assert mentionnes <= exposes

    def test_backend_documentaire_complet(self):
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", True), \
             patch.object(tools, "_db_backend_supporte_horaires", True):
            texte = prompts.build_tool_system_prompt()
            exposes = {t.name for t in tools.get_tools()}
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        assert mentionnes <= exposes
        assert "search_latest_news" in mentionnes
        assert "get_schedules_from_db" in mentionnes

    def test_installation_neuve_sans_base(self):
        """Cas nominal de toute installation neuve : database/scolarite_uam.db
        n'est pas versionnée (*.db dans .gitignore), donc _db_available=False
        au premier lancement sur toute machine autre que celle où la base a
        été semée localement — un clone du dépôt, un jury, un enseignant, ou
        l'utilisateur lui-même sur une autre machine. Le guide ne doit alors
        nommer aucun des quatre outils conditionnés à la base."""
        with patch.object(tools, "_db_available", False):
            texte = prompts.build_tool_system_prompt()
            exposes = {t.name for t in tools.get_tools()}
        for nom in ("search_latest_news", "get_schedules_from_db",
                    "search_student_record", "search_statistics_uam"):
            assert nom not in texte, f"{nom} mentionné alors que _db_available=False"
        # Le guide ne mentionne pas forcément tous les outils inconditionnels
        # par leur nom (ex : check_question_relevance, save_user_preference,
        # get_user_preferences n'y figurent pas) : la garantie générale porte
        # sur la solidité de ce qui est mentionné (mentionnes <= exposes),
        # pas sur l'exhaustivité du guide.
        mentionnes = _noms_mentionnes(texte, UNIVERS)
        assert mentionnes <= exposes

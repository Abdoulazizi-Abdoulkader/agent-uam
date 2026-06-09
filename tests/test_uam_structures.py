"""
Tests unitaires pour uam_structures.py
Couvre detect_structure_in_text et get_structure_info — fonctions critiques du routage.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from uam_structures import detect_structure_in_text, get_structure_info, UAM_STRUCTURES


# ── detect_structure_in_text ────────────────────────────────────────────────

class TestDetectStructureInText:

    def test_abreviation_connue(self):
        results = detect_structure_in_text("Quelles sont les formations à la FAST ?")
        abrevs = [r["abreviation"] for r in results]
        assert "FAST" in abrevs

    def test_plusieurs_structures(self):
        results = detect_structure_in_text("FAST et FLSH sont deux facultés de l'UAM.")
        abrevs = {r["abreviation"] for r in results}
        assert "FAST" in abrevs
        assert "FLSH" in abrevs

    def test_texte_sans_structure(self):
        results = detect_structure_in_text("Quel est le prix du pain aujourd'hui ?")
        assert results == []

    def test_texte_vide(self):
        results = detect_structure_in_text("")
        assert results == []

    def test_retour_contient_nom_complet(self):
        results = detect_structure_in_text("Je veux entrer à la FAST.")
        assert len(results) >= 1
        assert "nom_complet" in results[0]
        assert results[0]["nom_complet"] != ""

    def test_pas_de_doublon(self):
        results = detect_structure_in_text("FAST FAST FAST")
        abrevs = [r["abreviation"] for r in results]
        assert len(abrevs) == len(set(abrevs))


# ── get_structure_info ───────────────────────────────────────────────────────

class TestGetStructureInfo:

    def test_abreviation_exacte(self):
        info = get_structure_info("FAST")
        assert info is not None
        assert info["abreviation"] == "FAST"
        assert "nom_complet" in info

    def test_abreviation_minuscule(self):
        info = get_structure_info("fast")
        assert info is not None
        assert info["abreviation"] == "FAST"

    def test_structure_inconnue(self):
        info = get_structure_info("XXXXINCONNU")
        assert info is None

    def test_variante_exacte(self):
        """Une variante connue doit trouver la bonne structure."""
        # Récupérer la première variante réelle de la première faculté
        first_abbrev = next(iter(UAM_STRUCTURES["facultes"]))
        first_info = UAM_STRUCTURES["facultes"][first_abbrev]
        variantes = first_info.get("variantes", [])
        if variantes:
            result = get_structure_info(variantes[0])
            assert result is not None
            assert result["abreviation"] == first_abbrev

    def test_variante_sous_chaine_ne_match_pas(self):
        """Une variante ne doit PAS matcher si elle est sous-chaîne d'un autre texte."""
        # "ENS" ne doit pas matcher "enseignement" (substring)
        info = get_structure_info("enseignement supérieur en général")
        assert info is None

    def test_structure_retourne_type(self):
        info = get_structure_info("FAST")
        assert "type" in info
        assert info["type"] in ("faculte", "institut", "ecole")

    def test_toutes_abreviations_trouvables(self):
        """Chaque abréviation de UAM_STRUCTURES doit être retrouvable."""
        for category in ("facultes", "instituts", "ecoles"):
            for abbrev in UAM_STRUCTURES[category]:
                result = get_structure_info(abbrev)
                assert result is not None, f"Abréviation '{abbrev}' non trouvée"
                assert result["abreviation"] == abbrev

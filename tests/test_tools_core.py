"""
Tests unitaires pour les fonctions core de tools.py
Utilise unittest.mock pour isoler le vectorstore FAISS.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_doc(content: str):
    """Crée un faux Document LangChain."""
    doc = MagicMock()
    doc.page_content = content
    return doc


# ── _rag_response ─────────────────────────────────────────────────────────────

class TestRagResponse:

    def setup_method(self):
        import tools
        self.tools = tools

    def test_vectorstore_absent(self):
        with patch.object(self.tools._vectorstore, '_vectorstore', None):
            result = self.tools._rag_response("une requête")
        assert "non initialisée" in result.lower() or "erreur" in result.lower()

    def test_aucun_resultat(self):
        fake_vs = MagicMock()
        fake_vs.similarity_search.return_value = []
        with patch.object(self.tools._vectorstore, '_vectorstore', fake_vs):
            result = self.tools._rag_response("requête sans résultat", "Rien trouvé.")
        assert result == "Rien trouvé."

    def test_resultat_unique(self):
        fake_vs = MagicMock()
        fake_vs.similarity_search.return_value = [_make_doc("Contenu du document A")]
        with patch.object(self.tools._vectorstore, '_vectorstore', fake_vs):
            result = self.tools._rag_response("requête", "Rien.")
        assert "Contenu du document A" in result

    def test_plusieurs_resultats_separes_par_separateur(self):
        fake_vs = MagicMock()
        fake_vs.similarity_search.return_value = [
            _make_doc("Doc A"),
            _make_doc("Doc B"),
        ]
        with patch.object(self.tools._vectorstore, '_vectorstore', fake_vs):
            result = self.tools._rag_response("requête")
        assert "Doc A" in result
        assert "Doc B" in result
        assert "---" in result

    def test_troncature_800_chars(self):
        long_content = "X" * 2000
        fake_vs = MagicMock()
        fake_vs.similarity_search.return_value = [_make_doc(long_content)]
        with patch.object(self.tools._vectorstore, '_vectorstore', fake_vs):
            result = self.tools._rag_response("requête")
        assert len(result) <= 800

    def test_message_not_found_par_defaut(self):
        fake_vs = MagicMock()
        fake_vs.similarity_search.return_value = []
        with patch.object(self.tools._vectorstore, '_vectorstore', fake_vs):
            result = self.tools._rag_response("requête")
        assert result == "Aucune information trouvée."


# ── sanitize_input via tools ──────────────────────────────────────────────────

class TestSanitizeInTools:

    def test_input_trop_long_tronque(self):
        from utils import sanitize_input
        long_text = "a" * 3000
        result = sanitize_input(long_text, max_length=500)
        assert len(result) == 500

    def test_caracteres_controle_supprimes(self):
        from utils import sanitize_input
        text = "Bonjour\x00monde"
        result = sanitize_input(text)
        assert "\x00" not in result
        assert "Bonjourmonde" == result

    def test_entree_vide_leve_erreur(self):
        from utils import sanitize_input
        with pytest.raises(ValueError):
            sanitize_input("   ")


# ── validate_question ─────────────────────────────────────────────────────────

class TestValidateQuestion:

    def test_question_valide(self):
        from utils import validate_question
        ok, err = validate_question("Quelles filières à la FAST ?")
        assert ok is True
        assert err is None

    def test_question_trop_courte(self):
        from utils import validate_question
        ok, err = validate_question("A")
        assert ok is False
        assert "courte" in err

    def test_que_caracteres_speciaux(self):
        from utils import validate_question
        ok, err = validate_question("!!! ???")
        assert ok is False

    def test_question_vide(self):
        from utils import validate_question
        ok, err = validate_question("")
        assert ok is False

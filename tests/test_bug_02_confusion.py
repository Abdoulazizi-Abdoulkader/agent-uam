# tests/test_bug_02_confusion.py
"""BUG-02 : "Je ne comprends rien" n'est pas détecté comme CONFUSION.

`confusion_patterns` (tools/conversation.py) reconnaît « je ne comprends pas »
et « je n'y comprends rien », mais pas « je ne comprends rien » (sans le
« y »), une formulation quasi identique et tout aussi courante. Le message
part alors comme une question normale vers l'agent au lieu de déclencher la
réponse empathique de `handle_special_case`.

Manifestation consignée dans docs/superpowers/audit/2026-08-16-audit.md,
section 5 (table) et « Reproductions détaillées ».
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestFormulationsSansY:
    """Les formulations « je ne comprends rien » (sans « y ») doivent être
    détectées comme CONFUSION, au même titre que « je ne comprends pas » et
    « je n'y comprends rien », déjà correctement reconnues."""

    @pytest.mark.parametrize("message", [
        "Je ne comprends rien",
        "Je ne comprends rien du tout",
    ])
    def test_sont_detectees_comme_confusion(self, message):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message=message) == "CONFUSION"


class TestPasDeRegression:
    """Les formulations déjà reconnues avant la correction le restent."""

    @pytest.mark.parametrize("message,attendu", [
        ("Je ne comprends pas", "CONFUSION"),
        ("Je n'y comprends rien", "CONFUSION"),
        ("Ça ne marche pas", "FRUSTRATION"),
        ("J'ai déjà demandé ça", "REPETITION"),
    ])
    def test_formulations_deja_reconnues_restent_correctes(self, message, attendu):
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message=message) == attendu

    @pytest.mark.parametrize("message", [
        "Quels sont les frais d'inscription ?",
        "Je ne fais rien de spécial aujourd'hui",
        "Il ne reste plus rien à manger",
    ])
    def test_phrases_neutres_avec_rien_restent_normales(self, message):
        """« rien » seul, sans « je ne comprends », ne doit pas déclencher
        CONFUSION — le motif ajouté doit rester ancré sur « comprends »."""
        from tools import detect_frustration_or_confusion
        assert detect_frustration_or_confusion.func(message=message) == "NORMAL"


class TestRoutageDeBoutEnBout:
    """Le routage est ce que l'utilisateur subit réellement."""

    def test_je_ne_comprends_rien_atteint_handle_special_case(self):
        from langchain_core.messages import HumanMessage
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content="Je ne comprends rien")]})
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "CONFUSION"

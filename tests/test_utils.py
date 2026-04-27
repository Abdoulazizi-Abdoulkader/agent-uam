import unittest
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules du projet
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import (
    sanitize_input, validate_question, extract_entities,
    format_error_message, safe_get, truncate_text, retry_on_failure
)

class TestUtils(unittest.TestCase):

    def test_sanitize_input(self):
        # Cas normaux
        self.assertEqual(sanitize_input(" Bonjour "), "Bonjour")
        self.assertEqual(sanitize_input("A" * 3000, max_length=2000), "A" * 2000)
        
        # Cas d'erreurs
        with self.assertRaises(ValueError):
            sanitize_input(None)
        with self.assertRaises(ValueError):
            sanitize_input("   ")
            
        # Caractères de contrôle
        self.assertEqual(sanitize_input("Texte\x00avec\x08contrôle"), "Texteaveccontrôle")

    def test_validate_question(self):
        # Valide
        is_valid, error = validate_question("Quelles sont les filières de l'UAM ?")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Invalide - trop court
        is_valid, error = validate_question("A")
        self.assertFalse(is_valid)
        self.assertEqual(error, "La question est trop courte")
        
        # Invalide - que des caractères spéciaux
        is_valid, error = validate_question("??? !!!")
        self.assertFalse(is_valid)
        self.assertEqual(error, "La question doit contenir au moins un caractère alphanumérique")

    def test_extract_entities(self):
        text = "Je veux m'inscrire en licence à la FSS pour obtenir mon diplôme."
        entities = extract_entities(text)
        
        self.assertIn("FSS", entities["structures"])
        self.assertIn("licence", [e.lower() for e in entities["niveaux"]])
        self.assertTrue(any(k.lower() in ["inscrire", "inscription", "diplôme"] for k in entities["keywords"]))

    def test_format_error_message(self):
        err = ValueError("Invalid data")
        msg = format_error_message(err, context="Test context")
        self.assertIn("Une erreur de validation s'est produite", msg)
        self.assertIn("Test context", msg)
        self.assertIn("Invalid data", msg)
        
        err2 = Exception("Unknown error")
        msg2 = format_error_message(err2)
        self.assertIn("Une erreur s'est produite", msg2)
        self.assertIn("Unknown error", msg2)

    def test_safe_get(self):
        data = {"a": {"b": {"c": 42}}}
        self.assertEqual(safe_get(data, "a", "b", "c"), 42)
        self.assertIsNone(safe_get(data, "a", "x", "c"))
        self.assertEqual(safe_get(data, "a", "x", "c", default=10), 10)

    def test_truncate_text(self):
        text = "Bonjour le monde"
        self.assertEqual(truncate_text(text, max_length=100), text)
        self.assertEqual(truncate_text(text, max_length=10), "Bonjour...")

    def test_retry_on_failure(self):
        self.attempts = 0
        
        @retry_on_failure(max_retries=3, delay=0.1, backoff=1)
        def failing_func():
            self.attempts += 1
            if self.attempts < 3:
                raise ValueError("Fail")
            return "Success"
            
        result = failing_func()
        self.assertEqual(result, "Success")
        self.assertEqual(self.attempts, 3)
        
        self.attempts = 0
        @retry_on_failure(max_retries=2, delay=0.1, backoff=1)
        def always_failing():
            self.attempts += 1
            raise ValueError("Always fail")
            
        with self.assertRaises(ValueError):
            always_failing()
        self.assertEqual(self.attempts, 2)

if __name__ == '__main__':
    unittest.main()

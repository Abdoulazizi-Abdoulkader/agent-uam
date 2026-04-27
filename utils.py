"""
Utilitaires généraux pour l'agent UAM
Fonctions helper pour validation, sanitization, etc.
"""
import re
import functools
from typing import Optional, Dict, Any, Tuple
from logger_config import get_logger

logger = get_logger(__name__)


def sanitize_input(text: str, max_length: int = 2000) -> str:
    """
    Nettoie et valide l'entrée utilisateur
    
    Args:
        text: Texte à nettoyer
        max_length: Longueur maximale autorisée
        
    Returns:
        Texte nettoyé
        
    Raises:
        ValueError: Si le texte est invalide
    """
    if not isinstance(text, str):
        raise ValueError("L'entrée doit être une chaîne de caractères")
    
    # Supprimer les espaces en début/fin
    text = text.strip()
    
    # Vérifier la longueur
    if len(text) == 0:
        raise ValueError("L'entrée ne peut pas être vide")
    
    if len(text) > max_length:
        logger.warning(f"Entrée tronquée de {len(text)} à {max_length} caractères")
        text = text[:max_length]
    
    # Supprimer les caractères de contrôle (sauf les retours à la ligne et tabulations)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    return text


def validate_question(question: str) -> Tuple[bool, Optional[str]]:
    """
    Valide une question utilisateur
    
    Args:
        question: Question à valider
        
    Returns:
        Tuple (is_valid, error_message)
    """
    try:
        sanitized = sanitize_input(question, max_length=2000)
        
        # Vérifier qu'il y a au moins quelques caractères significatifs
        if len(sanitized) < 2:
            return False, "La question est trop courte"
        
        # Vérifier qu'il n'y a pas que des caractères spéciaux
        if not re.search(r'[a-zA-Z0-9À-ÿ]', sanitized):
            return False, "La question doit contenir au moins un caractère alphanumérique"
        
        return True, None
        
    except ValueError as e:
        return False, str(e)



def format_error_message(error: Exception, context: Optional[str] = None) -> str:
    """
    Formate un message d'erreur de manière conviviale
    
    Args:
        error: Exception à formater
        context: Contexte supplémentaire
        
    Returns:
        Message d'erreur formaté
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    # Messages d'erreur conviviaux pour l'utilisateur
    friendly_messages = {
        "ValueError": "Une erreur de validation s'est produite",
        "KeyError": "Une information est manquante",
        "ConnectionError": "Problème de connexion",
        "TimeoutError": "La requête a pris trop de temps",
        "FileNotFoundError": "Un fichier requis est introuvable"
    }
    
    base_message = friendly_messages.get(error_type, "Une erreur s'est produite")
    
    if context:
        return f"{base_message} ({context}). Détails: {error_message}"
    
    return f"{base_message}. Détails: {error_message}"


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Décorateur pour réessayer une fonction en cas d'échec

    Args:
        max_retries: Nombre maximum de tentatives (>= 1)
        delay: Délai initial entre les tentatives (secondes)
        backoff: Facteur de multiplication du délai
        exceptions: Types d'exceptions à capturer
    """
    import time as _time

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception: Optional[Exception] = None

            for attempt in range(max(max_retries, 1)):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Tentative {attempt + 1}/{max_retries} échouée pour "
                            f"{func.__name__}: {e}. "
                            f"Nouvelle tentative dans {current_delay:.1f}s..."
                        )
                        _time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Toutes les tentatives ont échoué pour {func.__name__}: {e}"
                        )

            # last_exception est toujours une Exception ici (au moins 1 tentative)
            raise last_exception  # type: ignore[misc]

        return wrapper
    return decorator


def safe_get(dictionary: Dict[str, Any], *keys, default: Any = None) -> Any:
    """
    Récupère une valeur d'un dictionnaire de manière sécurisée
    
    Args:
        dictionary: Dictionnaire à interroger
        keys: Clés à suivre (peut être imbriquées)
        default: Valeur par défaut si la clé n'existe pas
        
    Returns:
        Valeur trouvée ou valeur par défaut
    """
    try:
        result = dictionary
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError, IndexError):
        return default


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Tronque un texte à une longueur maximale
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        suffix: Suffixe à ajouter si tronqué
        
    Returns:
        Texte tronqué
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


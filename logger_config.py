"""
Configuration du système de logging pour l'agent UAM
Fournit un logger structuré avec différents niveaux et formats
"""
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Créer le dossier logs s'il n'existe pas
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Format de log structuré
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Format détaillé pour les fichiers
DETAILED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s"


def setup_logger(
    name: str = "agent_uam",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Configure et retourne un logger avec handlers pour console et fichier
    
    Args:
        name: Nom du logger
        level: Niveau de logging (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Si True, écrit les logs dans un fichier
        log_to_console: Si True, affiche les logs dans la console
        
    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Éviter les doublons de handlers
    if logger.handlers:
        return logger
    
    # Formatter pour les logs
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    detailed_formatter = logging.Formatter(DETAILED_LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Handler pour la console
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler pour le fichier
    if log_to_file:
        # Fichier de log avec date
        log_file = LOG_DIR / f"agent_uam_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Toujours logger tout dans le fichier
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Fichier d'erreurs séparé
        error_log_file = LOG_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Récupère un logger existant ou en crée un nouveau
    
    Args:
        name: Nom du logger (optionnel, utilise le nom du module appelant si non fourni)
        
    Returns:
        Logger configuré
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'agent_uam')
    
    logger = logging.getLogger(name)
    
    # Si le logger n'a pas de handlers, le configurer
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


# Logger par défaut pour le module
default_logger = setup_logger("agent_uam")


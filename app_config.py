"""
Configuration centralisée pour l'agent UAM
Gère toutes les configurations de l'application
"""
import os
import threading
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from logger_config import get_logger

logger = get_logger(__name__)


class LLMProvider(Enum):
    """Provider LLM supporté. Seul OPENROUTER est actuellement actif dans llm_utils.py."""
    OPENROUTER   = "openrouter"    # défaut — seul provider actif
    OPENAI       = "openai"
    CLAUDE       = "claude"
    LLAMA_GROQ   = "llama_groq"
    LLAMA_OLLAMA = "llama_ollama"


@dataclass
class DatabaseConfig:
    """Configuration de la base de données"""
    db_type: Optional[str] = None
    db_host: str = "localhost"
    db_port: str = "5432"
    db_name: str = "uam_db"
    db_user: str = "postgres"
    db_password: str = ""
    db_path: str = "./database/scolarite_uam.db"
    connection_string: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Charge la configuration depuis les variables d'environnement"""
        return cls(
            db_type=os.getenv("UAM_DB_TYPE"),
            db_host=os.getenv("UAM_DB_HOST", "localhost"),
            db_port=os.getenv("UAM_DB_PORT", "5432"),
            db_name=os.getenv("UAM_DB_NAME", "uam_db"),
            db_user=os.getenv("UAM_DB_USER", "postgres"),
            db_password=os.getenv("UAM_DB_PASSWORD", ""),
            db_path=os.getenv("UAM_DB_PATH", "./database/scolarite_uam.db"),
            connection_string=os.getenv("UAM_DB_CONNECTION_STRING")
        )


@dataclass
class LLMConfig:
    """Configuration du LLM"""
    provider: str = "openrouter"
    model_name: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = None
    timeout: int = 60
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Charge la configuration depuis les variables d'environnement"""
        return cls(
            provider=os.getenv("UAM_LLM_PROVIDER", "openrouter"),
            model_name=os.getenv("UAM_LLM_MODEL"),
            temperature=float(os.getenv("UAM_LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("UAM_LLM_MAX_TOKENS", "0")) or None,
            timeout=int(os.getenv("UAM_LLM_TIMEOUT", "60"))
        )


@dataclass
class VectorStoreConfig:
    """Configuration du vector store"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    similarity_search_k: int = 4
    persist_directory: Optional[str] = "./vectorstore"
    
    @classmethod
    def from_env(cls) -> "VectorStoreConfig":
        """Charge la configuration depuis les variables d'environnement"""
        return cls(
            chunk_size=int(os.getenv("UAM_CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("UAM_CHUNK_OVERLAP", "200")),
            similarity_search_k=int(os.getenv("UAM_SIMILARITY_K", "4")),
            persist_directory=os.getenv("UAM_VECTORSTORE_DIR", "./vectorstore")
        )


@dataclass
class AppConfig:
    """Configuration principale de l'application"""
    # Chemins
    documents_directory: str = "./documents_uam"
    exports_directory: str = "./exports"
    logs_directory: str = "./logs"
    memory_file: str = "./user_memory.json"
    memory_db_path: str = "./user_memory.db"
    metrics_db_path: str = "./metrics.db"
    
    # Base de données
    database: DatabaseConfig = field(default_factory=DatabaseConfig.from_env)
    
    # LLM
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    
    # Vector Store
    vectorstore: VectorStoreConfig = field(default_factory=VectorStoreConfig.from_env)
    
    # Sécurité
    max_input_length: int = 2000
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    max_tool_iterations: int = 5
    
    # Interface
    streamlit_port: int = 8501
    streamlit_host: str = "localhost"
    
    def __post_init__(self):
        logger.info(f"Configuration chargée - Documents: {self.documents_directory}")

    def setup(self) -> None:
        """Crée les dossiers nécessaires. À appeler au démarrage de l'application, pas à l'import."""
        Path(self.documents_directory).mkdir(parents=True, exist_ok=True)
        Path(self.exports_directory).mkdir(parents=True, exist_ok=True)
        Path(self.logs_directory).mkdir(parents=True, exist_ok=True)
        Path(self.memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.metrics_db_path).parent.mkdir(parents=True, exist_ok=True)
        if self.vectorstore.persist_directory:
            Path(self.vectorstore.persist_directory).mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """Valide la configuration et journalise les problèmes."""
        issues = []

        provider = (self.llm.provider or "").strip().lower()
        required_api_keys = {
            "openrouter": "OPENROUTER_API_KEY",
        }
        required_key = required_api_keys.get(provider)
        if required_key and not os.getenv(required_key):
            issues.append(
                f"Clé API manquante pour le provider '{provider}': {required_key}"
            )

        if self.max_input_length <= 0:
            issues.append("UAM_MAX_INPUT_LENGTH doit être > 0")
        if self.max_retries < 0:
            issues.append("UAM_MAX_RETRIES doit être >= 0")
        if self.rate_limit_per_minute <= 0:
            issues.append("UAM_RATE_LIMIT doit être > 0")
        if self.max_tool_iterations <= 0:
            issues.append("UAM_MAX_TOOL_ITERATIONS doit être > 0")
        if self.vectorstore.chunk_size <= 0:
            issues.append("UAM_CHUNK_SIZE doit être > 0")
        if self.vectorstore.chunk_overlap < 0:
            issues.append("UAM_CHUNK_OVERLAP doit être >= 0")
        if self.vectorstore.chunk_overlap >= self.vectorstore.chunk_size:
            issues.append("UAM_CHUNK_OVERLAP doit être < UAM_CHUNK_SIZE")
        if self.vectorstore.similarity_search_k <= 0:
            issues.append("UAM_SIMILARITY_K doit être > 0")

        for issue in issues:
            logger.warning(f"Configuration invalide ou incomplète: {issue}")
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Charge la configuration depuis les variables d'environnement"""
        return cls(
            documents_directory=os.getenv("UAM_DOCUMENTS_DIR", "./documents_uam"),
            exports_directory=os.getenv("UAM_EXPORTS_DIR", "./exports"),
            logs_directory=os.getenv("UAM_LOGS_DIR", "./logs"),
            memory_file=os.getenv("UAM_MEMORY_FILE", "./user_memory.json"),
            memory_db_path=os.getenv("UAM_MEMORY_DB", "./user_memory.db"),
            metrics_db_path=os.getenv("UAM_METRICS_DB", "./metrics.db"),
            database=DatabaseConfig.from_env(),
            llm=LLMConfig.from_env(),
            vectorstore=VectorStoreConfig.from_env(),
            max_input_length=int(os.getenv("UAM_MAX_INPUT_LENGTH", "2000")),
            max_retries=int(os.getenv("UAM_MAX_RETRIES", "3")),
            rate_limit_per_minute=int(os.getenv("UAM_RATE_LIMIT", "60")),
            max_tool_iterations=int(os.getenv("UAM_MAX_TOOL_ITERATIONS", "5")),
            streamlit_port=int(os.getenv("UAM_STREAMLIT_PORT", "8501")),
            streamlit_host=os.getenv("UAM_STREAMLIT_HOST", "localhost")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire"""
        return {
            "documents_directory": self.documents_directory,
            "exports_directory": self.exports_directory,
            "logs_directory": self.logs_directory,
            "memory_file": self.memory_file,
            "memory_db_path": self.memory_db_path,
            "metrics_db_path": self.metrics_db_path,
            "database": {
                "db_type": self.database.db_type,
                "db_host": self.database.db_host,
                "db_port": self.database.db_port,
                "db_name": self.database.db_name,
                "db_user": self.database.db_user,
                "db_password": "***" if self.database.db_password else "",
            },
            "llm": {
                "provider": self.llm.provider,
                "model_name": self.llm.model_name,
                "temperature": self.llm.temperature
            },
            "vectorstore": {
                "chunk_size": self.vectorstore.chunk_size,
                "chunk_overlap": self.vectorstore.chunk_overlap,
                "similarity_search_k": self.vectorstore.similarity_search_k,
                "persist_directory": self.vectorstore.persist_directory
            },
            "max_input_length": self.max_input_length,
            "max_retries": self.max_retries,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "max_tool_iterations": self.max_tool_iterations
        }


# Instance globale de configuration (singleton thread-safe)
_config: Optional[AppConfig] = None
_config_lock = threading.Lock()


def get_config() -> AppConfig:
    """Récupère l'instance globale de configuration (thread-safe, double-checked locking)."""
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                instance = AppConfig.from_env()
                instance.setup()
                instance.validate()
                _config = instance
    return _config

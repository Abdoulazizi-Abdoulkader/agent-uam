"""
Initialisation du LLM et des embeddings — provider OpenRouter uniquement
"""
import os
from typing import Optional

from langsmith import traceable
from app_config import LLMProvider
from app_config import get_config
from logger_config import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "openai/gpt-4o-mini"


@traceable
def initialize_llm(
    provider: LLMProvider = LLMProvider.OPENROUTER,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """
    Initialise le LLM OpenRouter.

    Args:
        provider: ignoré (gardé pour compatibilité des signatures), seul OPENROUTER est supporté
        model_name: identifiant OpenRouter du modèle (ex: ``meta-llama/llama-3.3-70b-instruct``)
        temperature: température de génération (défaut: config)

    Returns:
        Instance ChatOpenAI pointant vers openrouter.ai
    """
    from langchain_openai import ChatOpenAI

    if provider != LLMProvider.OPENROUTER:
        logger.warning(
            f"Provider '{provider.value}' ignoré : seul OPENROUTER est supporté. "
            "Utilisation d'OpenRouter."
        )

    config = get_config()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY non définie. "
            "Ajoutez OPENROUTER_API_KEY=sk-or-v1-... dans votre fichier .env"
        )

    final_model = model_name or config.llm.model_name or DEFAULT_MODEL
    final_temperature = temperature if temperature is not None else config.llm.temperature

    llm_kwargs = {
        "model": final_model,
        "temperature": final_temperature,
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1",
        "timeout": config.llm.timeout,
        "default_headers": {
            "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://github.com/agent-uam"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "Agent UAM"),
        },
    }
    if config.llm.max_tokens:
        llm_kwargs["max_tokens"] = config.llm.max_tokens

    # api_key est passé directement au constructeur — pas besoin de toucher os.environ
    llm = ChatOpenAI(**llm_kwargs)

    logger.info(f"LLM OpenRouter initialisé : {final_model} (timeout={config.llm.timeout}s)")
    return llm


@traceable
def initialize_embeddings(provider: LLMProvider = LLMProvider.OPENROUTER):
    """
    Initialise les embeddings HuggingFace multilingues.
    OpenRouter ne fournit pas d'API embeddings — on utilise sentence-transformers localement.

    Args:
        provider: ignoré (gardé pour compatibilité des signatures)

    Returns:
        Instance HuggingFaceEmbeddings
    """
    model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info(f"Embeddings HuggingFace : {model}")
        return HuggingFaceEmbeddings(model_name=model)
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        logger.info(f"Embeddings HuggingFace (community) : {model}")
        return HuggingFaceEmbeddings(model_name=model)

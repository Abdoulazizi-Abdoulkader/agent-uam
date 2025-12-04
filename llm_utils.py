"""
Utilitaires pour l'initialisation des LLM et embeddings
"""
import os
from typing import Optional
from config import LLMProvider


def initialize_llm(provider: LLMProvider, model_name: Optional[str] = None, temperature: float = 0.3):
    """
    Initialise le LLM selon le provider choisi

    Args:
        provider: Provider LLM (OPENAI, CLAUDE, LLAMA_OLLAMA, LLAMA_GROQ, OPENROUTER)
        model_name: Nom du modèle (optionnel, utilise les valeurs par défaut)
        temperature: Température pour la génération (0 = déterministe, 1 = créatif)

    Returns:
        Instance du LLM configuré
    """
    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            temperature=temperature
        )

    elif provider == LLMProvider.CLAUDE:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name or "claude-sonnet-4-20250514",
            temperature=temperature,
        )

    elif provider == LLMProvider.LLAMA_OLLAMA:
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=model_name or "llama3.2",
            temperature=temperature
        )

    elif provider == LLMProvider.LLAMA_GROQ:
        from langchain_groq import ChatGroq
        # Vérifier que la clé API est disponible
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY non définie. "
                "Définissez-la dans le fichier .env ou comme variable d'environnement.\n"
                "Exemple: export GROQ_API_KEY='votre_cle' ou créez un fichier .env avec GROQ_API_KEY=votre_cle"
            )
        return ChatGroq(
            model=model_name or "llama-3.3-70b-versatile",
            temperature=temperature,
            api_key=api_key  # Passer explicitement la clé API
        )

    elif provider == LLMProvider.OPENROUTER:
        from langchain_openai import ChatOpenAI
        # Vérifier que la clé API est disponible
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY non définie. "
                "Définissez-la dans le fichier .env ou comme variable d'environnement.\n"
                "Exemple: export OPENROUTER_API_KEY='votre_cle' ou créez un fichier .env avec OPENROUTER_API_KEY=votre_cle\n"
                "Obtenez votre clé sur https://openrouter.ai/"
            )
        # OpenRouter utilise une API compatible OpenAI avec une URL de base différente
        # ChatOpenAI nécessite que api_key soit passé explicitement ET que OPENAI_API_KEY soit définie
        # On définit temporairement OPENAI_API_KEY pour éviter les erreurs de validation
        original_openai_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = api_key

        try:
            llm = ChatOpenAI(
                model=model_name or "openai/gpt-4o",
                temperature=temperature,
                api_key=api_key,  # Passer explicitement
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://github.com/your-repo"),  # Optionnel mais recommandé
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "Agent UAM"),  # Optionnel mais recommandé
                }
            )
            return llm
        finally:
            # Restaurer la valeur originale
            if original_openai_key is not None:
                os.environ["OPENAI_API_KEY"] = original_openai_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)

    else:
        raise ValueError(f"Provider non supporté: {provider}")


def initialize_embeddings(provider: LLMProvider):
    """
    Initialise les embeddings selon le provider

    Args:
        provider: Provider LLM

    Returns:
        Instance des embeddings
    """
    if provider == LLMProvider.OPENAI:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings()

    elif provider == LLMProvider.CLAUDE:
        # Claude n'a pas d'API embeddings, utiliser alternatives
        from langchain_openai import OpenAIEmbeddings
        print("  Claude n'a pas d'embeddings natifs, utilisation d'OpenAI Embeddings")
        return OpenAIEmbeddings()

    elif provider == LLMProvider.LLAMA_OLLAMA:
        from langchain_community.embeddings import OllamaEmbeddings
        return OllamaEmbeddings(model="llama3.2")

    elif provider == LLMProvider.LLAMA_GROQ:
        # Groq n'a pas d'API embeddings, utiliser HuggingFace
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            print("  Groq n'a pas d'embeddings natifs, utilisation de HuggingFace")
            return HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
        except ImportError:
            # Fallback vers l'ancienne version si langchain-huggingface n'est pas installé
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                print("  Groq n'a pas d'embeddings natifs, utilisation de HuggingFace (version community)")
                return HuggingFaceEmbeddings(
                    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
            except ImportError:
                # Dernier recours : utiliser OpenAI embeddings
                from langchain_openai import OpenAIEmbeddings
                print("  HuggingFace non disponible, utilisation d'OpenAI Embeddings")
                return OpenAIEmbeddings()

    elif provider == LLMProvider.OPENROUTER:
        # OpenRouter n'a pas d'API embeddings dédiée, utiliser OpenAI embeddings ou HuggingFace
        # Option 1: Utiliser OpenAI embeddings via OpenRouter (si disponible)
        try:
            from langchain_openai import OpenAIEmbeddings
            api_key = os.getenv("OPENROUTER_API_KEY")
            if api_key:
                print("  OpenRouter: utilisation d'OpenAI Embeddings via OpenRouter")
                return OpenAIEmbeddings(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
        except Exception:
            pass

        # Option 2: Fallback vers HuggingFace (gratuit et multilingue)
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            print("  OpenRouter n'a pas d'embeddings natifs, utilisation de HuggingFace")
            return HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
        except ImportError:
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                print("  OpenRouter n'a pas d'embeddings natifs, utilisation de HuggingFace (version community)")
                return HuggingFaceEmbeddings(
                    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
            except ImportError:
                # Dernier recours : utiliser OpenAI embeddings standard
                from langchain_openai import OpenAIEmbeddings
                print("  HuggingFace non disponible, utilisation d'OpenAI Embeddings")
                return OpenAIEmbeddings()

    else:
        raise ValueError(f"Provider non supporté: {provider}")


import os
import uuid
import json
from typing import Annotated, TypedDict, Literal, List, Sequence, Optional, Dict, Any
from enum import Enum
from pathlib import Path
from operator import add
from datetime import datetime

# Charger les variables d'environnement dès le début
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv n'est pas installé, utiliser les variables d'environnement système

# Imports LangChain modernes
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

# Import ToolNode avec fallback si non disponible
try:
    from langgraph.prebuilt import ToolNode
except ImportError:
    # Créer une implémentation alternative de ToolNode
    from langchain_core.messages import ToolMessage
    
    class ToolNode:
        """Implémentation alternative de ToolNode pour exécuter les outils"""
        def __init__(self, tools):
            # Créer un dictionnaire des outils par nom
            self.tools = {}
            for tool in tools:
                if hasattr(tool, 'name'):
                    self.tools[tool.name] = tool
                elif hasattr(tool, '__name__'):
                    self.tools[tool.__name__] = tool
        
        def invoke(self, state):
            """Exécute les appels d'outils depuis les messages"""
            messages = state.get("messages", [])
            if not messages:
                return {"messages": []}
            
            last_message = messages[-1]
            tool_messages = []
            
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    # Gérer différents formats de tool_call
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        tool_call_id = tool_call.get("id", "")
                    else:
                        # Format objet
                        tool_name = getattr(tool_call, "name", "")
                        tool_args = getattr(tool_call, "args", {})
                        tool_call_id = getattr(tool_call, "id", "")
                    
                    if tool_name in self.tools:
                        try:
                            result = self.tools[tool_name].invoke(tool_args)
                            tool_messages.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call_id
                                )
                            )
                        except Exception as e:
                            tool_messages.append(
                                ToolMessage(
                                    content=f"Erreur lors de l'exécution de {tool_name}: {e}",
                                    tool_call_id=tool_call_id
                                )
                            )
            
            return {"messages": tool_messages}
        
        def __call__(self, state):
            """Permet d'utiliser ToolNode comme une fonction"""
            return self.invoke(state)


# ==================== CONFIGURATION ====================
class LLMProvider(Enum):
    """Providers LLM supportés"""
    OPENAI = "openai"
    CLAUDE = "claude"
    LLAMA_OLLAMA = "llama_ollama"
    LLAMA_GROQ = "llama_groq"
    OPENROUTER = "openrouter"


# ==================== BASE DE CONNAISSANCES UAM ====================
# Dictionnaire des facultés, écoles et instituts avec leurs abréviations
UAM_STRUCTURES = {
    "facultes": {
        "FAST": {
            "nom_complet": "Faculté des Sciences et Techniques",
            "variantes": ["Faculté des sciences & techniques", "Faculté des Sciences et Techniques", 
                         "FAST", "sciences et techniques", "sciences techniques"]
        },
        "FLSH": {
            "nom_complet": "Faculté des Lettres et Sciences Humaines",
            "variantes": ["Faculté des lettres et sciences humaines", "Faculté des Lettres et Sciences Humaines",
                         "FLSH", "lettres et sciences humaines", "lettres sciences humaines"]
        },
        "FA": {
            "nom_complet": "Faculté d'Agronomie",
            "variantes": ["Faculté d'agronomie", "Faculté d'Agronomie", "FA", "agronomie"]
        },
        "FSEG": {
            "nom_complet": "Faculté des Sciences Économiques et de Gestion",
            "variantes": ["Faculté des sciences économiques et de gestion", 
                         "Faculté des Sciences Économiques et de Gestion", "FSEG",
                         "sciences économiques et de gestion", "sciences économiques gestion"]
        },
        "FSJP": {
            "nom_complet": "Faculté des Sciences Juridiques et Politiques",
            "variantes": ["Faculté des sciences juridiques et politiques",
                         "Faculté des Sciences Juridiques et Politiques", "FSJP",
                         "sciences juridiques et politiques", "droit", "juridique"]
        },
        "FSS": {
            "nom_complet": "Faculté des Sciences de la Santé",
            "variantes": ["Faculté des sciences de la santé", "Faculté des Sciences de la Santé",
                         "FSS", "sciences de la santé", "santé", "médecine"]
        }
    },
    "instituts": {
        "IRSH": {
            "nom_complet": "Institut de Recherche en Sciences Humaines",
            "variantes": ["Institut de recherche en sciences humaines", 
                         "Institut de Recherche en Sciences Humaines", "IRSH"]
        },
        "IREM": {
            "nom_complet": "Institut de Recherches pour l'Enseignement des Mathématiques",
            "variantes": ["Institut de recherches pour l'enseignement des mathématiques",
                         "Institut de Recherches pour l'Enseignement des Mathématiques", "IREM"]
        },
        "IRI": {
            "nom_complet": "Institut des Radio-isotopes",
            "variantes": ["Institut des radio-isotopes", "Institut des Radio-isotopes", "IRI"]
        }
    },
    "ecoles": {
        "ENS": {
            "nom_complet": "École Normale Supérieure",
            "variantes": ["École normale supérieure", "École Normale Supérieure", "ENS"]
        },
        "ED-SVT": {
            "nom_complet": "École Doctorale des Sciences de la Vie et de la Terre",
            "variantes": ["École doctorale des Sciences de la Vie et de la Terre",
                         "École Doctorale des Sciences de la Vie et de la Terre",
                         "ED-SVT", "École doctorale SVT"]
        },
        "ED-LASHS": {
            "nom_complet": "École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société",
            "variantes": ["École doctorale des Lettres, Arts, Sciences de l'Homme et de la Société",
                         "École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société",
                         "ED-LASHS", "École doctorale LASHS"]
        },
        "ED-SET": {
            "nom_complet": "École Doctorale des Sciences Exactes et Techniques",
            "variantes": ["École doctorale des Sciences Exactes et Techniques",
                         "École Doctorale des Sciences Exactes et Techniques",
                         "ED-SET", "École doctorale SET"]
        }
    }
}


def get_structure_info(structure_name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche une structure (faculté, école, institut) par son nom ou abréviation
    
    Args:
        structure_name: Nom ou abréviation de la structure
        
    Returns:
        Dictionnaire avec les informations de la structure ou None si non trouvé
    """
    structure_name_lower = structure_name.lower().strip()
    
    # Rechercher dans toutes les catégories
    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            # Vérifier l'abréviation
            if abbrev.lower() == structure_name_lower:
                return {
                    "type": category[:-1],  # Enlever le 's' final
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"],
                    "variantes": info["variantes"]
                }
            # Vérifier les variantes
            for variant in info["variantes"]:
                if variant.lower() == structure_name_lower or variant.lower() in structure_name_lower:
                    return {
                        "type": category[:-1],
                        "abreviation": abbrev,
                        "nom_complet": info["nom_complet"],
                        "variantes": info["variantes"]
                    }
    
    return None


def detect_structure_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Détecte toutes les structures mentionnées dans un texte
    
    Args:
        text: Texte à analyser
        
    Returns:
        Liste des structures détectées
    """
    text_lower = text.lower()
    detected = []
    
    for category in ["facultes", "instituts", "ecoles"]:
        for abbrev, info in UAM_STRUCTURES[category].items():
            # Vérifier si l'abréviation ou une variante est dans le texte
            if abbrev.lower() in text_lower:
                detected.append({
                    "type": category[:-1],
                    "abreviation": abbrev,
                    "nom_complet": info["nom_complet"]
                })
            else:
                for variant in info["variantes"]:
                    if variant.lower() in text_lower:
                        detected.append({
                            "type": category[:-1],
                            "abreviation": abbrev,
                            "nom_complet": info["nom_complet"]
                        })
                        break
    
    return detected


class AgentState(TypedDict):
    """État de l'agent conversationnel avec gestion moderne des messages"""
    # Utilisation d'Annotated pour la réduction automatique des messages
    messages: Annotated[Sequence[BaseMessage], add]
    question: str
    is_relevant: bool
    context: str
    response: str
    need_clarification: bool
    user_id: str  # ID utilisateur pour la mémoire à long terme
    user_preferences: Dict[str, Any]  # Préférences utilisateur


# ==================== INITIALISATION LLM ====================
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


# ==================== CHARGEMENT DES DOCUMENTS ====================
def load_and_index_documents(pdf_directory: str, provider: LLMProvider) -> FAISS:
    """
    Charge les documents (PDF, TXT, DOCX, MD) et crée un index vectoriel
    
    Args:
        pdf_directory: Chemin vers le dossier contenant les documents
        provider: Provider LLM pour les embeddings
    
    Returns:
        Index FAISS pour la recherche sémantique
    """
    print(" Chargement des documents...")
    
    # Normaliser le chemin
    pdf_directory = os.path.abspath(pdf_directory)
    if not os.path.exists(pdf_directory):
        raise ValueError(f" Le dossier '{pdf_directory}' n'existe pas.")
    
    print(f"  Dossier: {pdf_directory}")
    
    all_documents = []
    
    # 1. Charger les PDFs
    try:
        pdf_files = list(Path(pdf_directory).glob("**/*.pdf"))
        print(f"   {len(pdf_files)} fichier(s) PDF trouvé(s)")
        
        if pdf_files:
            pdf_loader = DirectoryLoader(
                pdf_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader,
                show_progress=False,
                silent_errors=False
            )
            pdf_docs = pdf_loader.load()
            all_documents.extend(pdf_docs)
            print(f"  ✓ {len(pdf_docs)} PDF(s) chargé(s) avec succès")
        else:
            print(f"    Aucun fichier PDF trouvé dans {pdf_directory}")
    except Exception as e:
        print(f"    Erreur chargement PDF: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Charger les fichiers TXT
    try:
        txt_files = list(Path(pdf_directory).glob("**/*.txt"))
        print(f"  🔍 {len(txt_files)} fichier(s) TXT trouvé(s)")
        
        if txt_files:
            txt_loader = DirectoryLoader(
                pdf_directory,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
                show_progress=False,
                silent_errors=False
            )
            txt_docs = txt_loader.load()
            all_documents.extend(txt_docs)
            print(f"  ✓ {len(txt_docs)} fichier(s) TXT chargé(s) avec succès")
        else:
            print(f"    Aucun fichier TXT trouvé dans {pdf_directory}")
    except Exception as e:
        print(f"    Erreur chargement TXT: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Charger les fichiers Markdown (optionnel)
    try:
        from langchain_community.document_loaders import UnstructuredMarkdownLoader
        md_loader = DirectoryLoader(
            pdf_directory,
            glob="**/*.md",
            loader_cls=UnstructuredMarkdownLoader,
            show_progress=False
        )
        md_docs = md_loader.load()
        all_documents.extend(md_docs)
        print(f"  ✓ {len(md_docs)} fichier(s) Markdown chargé(s)")
    except Exception as e:
        if "No module named" not in str(e):
            print(f"    Erreur chargement Markdown: {e}")
    
    # 4. Charger les fichiers DOCX (optionnel)
    try:
        from langchain_community.document_loaders import Docx2txtLoader
        docx_loader = DirectoryLoader(
            pdf_directory,
            glob="**/*.docx",
            loader_cls=Docx2txtLoader,
            show_progress=False
        )
        docx_docs = docx_loader.load()
        all_documents.extend(docx_docs)
        print(f"  ✓ {len(docx_docs)} fichier(s) DOCX chargé(s)")
    except Exception as e:
        if "No module named" not in str(e):
            print(f"    Erreur chargement DOCX: {e}")
    
    if len(all_documents) == 0:
        raise ValueError(
            f" Aucun document trouvé dans {pdf_directory}\n"
            f" Vérifiez que le dossier contient des fichiers PDF (.pdf) ou TXT (.txt)"
        )
    
    print(f"  Total: {len(all_documents)} document(s) chargé(s)")
    
    # Découper les documents en chunks
    print("  🔪 Découpage des documents en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    splits = text_splitter.split_documents(all_documents)
    
    print(f" {len(all_documents)} document(s) total chargé(s) et divisé(s) en {len(splits)} chunks")
    
    # Créer l'index vectoriel avec les embeddings appropriés
    embeddings = initialize_embeddings(provider)
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    return vectorstore


# ==================== OUTILS (TOOLS) ====================

# Variables globales
_vectorstore = None
_user_memory_file = "user_memory.json"

# Import du module de connexion à la base de données
try:
    from database_connector import (
        is_database_available,
        search_formations_db,
        search_students_db,
        search_schedules_db,
        search_fees_db,
        search_news_announcements_db,
        query_database
    )
    _db_available = is_database_available()
except ImportError:
    _db_available = False
    print("⚠️ Module database_connector non disponible")
except Exception as e:
    _db_available = False
    print(f"⚠️ Erreur lors de l'initialisation de la base de données : {e}")

def set_vectorstore(vectorstore: FAISS):
    """Définit le vectorstore global pour les outils"""
    global _vectorstore
    _vectorstore = vectorstore


# ==================== MÉMOIRE À LONG TERME ====================
class UserMemory:
    """Gestion de la mémoire à long terme pour les préférences utilisateur"""
    
    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict[str, Any]:
        """Charge la mémoire depuis le fichier JSON"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f" Erreur lors du chargement de la mémoire: {e}")
                return {}
        return {}
    
    def _save_memory(self):
        """Sauvegarde la mémoire dans le fichier JSON"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f" Erreur lors de la sauvegarde de la mémoire: {e}")
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Récupère les préférences d'un utilisateur"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        return self.memory[user_id].get("preferences", {})
    
    def save_user_preference(self, user_id: str, key: str, value: Any):
        """Sauvegarde une préférence utilisateur"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        
        self.memory[user_id]["preferences"][key] = value
        self.memory[user_id]["last_updated"] = datetime.now().isoformat()
        self._save_memory()
    
    def add_conversation(self, user_id: str, question: str, response: str):
        """Ajoute une conversation à l'historique"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        
        self.memory[user_id]["conversation_history"].append({
            "question": question,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        self.memory[user_id]["last_updated"] = datetime.now().isoformat()
        self._save_memory()
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Récupère l'historique des conversations"""
        if user_id not in self.memory:
            return []
        return self.memory[user_id].get("conversation_history", [])[-limit:]


# Instance globale de la mémoire
_user_memory = UserMemory()


@tool
def search_uam_knowledge(query: str) -> str:
    """
    Recherche des informations dans la base de connaissances de l'UAM.
    Comprend automatiquement les abréviations (ex: FAST, FLSH, ENS, etc.).
    
    Args:
        query: La question ou le terme à rechercher dans les documents UAM.
               Peut contenir des abréviations comme FAST, FLSH, ENS, etc.
        
    Returns:
        Le contexte pertinent trouvé dans les documents
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Détecter et remplacer les abréviations par leurs noms complets pour améliorer la recherche
    query_expanded = query
    detected_structures = detect_structure_in_text(query)
    
    if detected_structures:
        # Ajouter les noms complets des structures détectées à la requête
        structure_names = [s["nom_complet"] for s in detected_structures]
        query_expanded = f"{query} {' '.join(structure_names)}"
    
    # Recherche sémantique avec la requête enrichie
    docs = _vectorstore.similarity_search(query_expanded, k=4)
    
    # Combiner les documents
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    return context if context else "Aucune information trouvée pour cette requête."


@tool
def detect_greeting(message: str) -> str:
    """
    Détecte si le message de l'utilisateur est une salutation ou une formule de politesse.
    
    Args:
        message: Le message de l'utilisateur
        
    Returns:
        "GREETING" si c'est une salutation, "QUESTION" si c'est une question, "BOTH" si les deux
    """
    message_lower = message.lower().strip()
    
    # Salutations courantes
    greetings = [
        "bonjour", "bonsoir", "salut", "bonne journée", "bonne soirée",
        "bonne nuit", "coucou", "hey", "hi", "hello", "bon matin",
        "bon après-midi", "à bientôt", "au revoir", "adieu",
        "merci", "merci beaucoup", "merci bien", "je vous remercie",
        "s'il vous plaît", "s'il te plaît", "svp", "stp",
        "excusez-moi", "excuse-moi", "pardon", "désolé", "désolée"
    ]
    
    # Vérifier si le message contient une salutation
    is_greeting = any(greeting in message_lower for greeting in greetings)
    
    # Vérifier si c'est une question (contient des mots-clés de question)
    question_keywords = ["?", "quoi", "comment", "pourquoi", "quand", "où", "qui", "quel", "quelle", "quels", "quelles"]
    is_question = any(keyword in message_lower for keyword in question_keywords) or "?" in message
    
    # Vérifier si le message contient des mots-clés UAM (pour savoir si c'est une vraie question)
    uam_keywords = ["uam", "université", "faculté", "école", "institut", "formation", "inscription", 
                     "admission", "diplôme", "fast", "flsh", "fseg", "fsjp", "fa", "fss", "ens"]
    has_uam_content = any(keyword in message_lower for keyword in uam_keywords)
    
    if is_greeting and (is_question or has_uam_content):
        return "BOTH"
    elif is_greeting:
        return "GREETING"
    elif is_question or has_uam_content:
        return "QUESTION"
    else:
        return "QUESTION"  # Par défaut, traiter comme une question


@tool
def check_question_relevance(question: str) -> str:
    """
    Vérifie si une question concerne l'Université Abdou Moumouni de Niamey.
    
    Args:
        question: La question de l'utilisateur
        
    Returns:
        "PERTINENT" si la question concerne l'UAM, "HORS_SUJET" sinon
    """
    keywords_uam = [
        "uam", "université", "abdou moumouni", "niamey", "niger",
        "faculté", "école", "institut", "formation", "filière",
        "inscription", "admission", "diplôme", "attestation", "relevé",
        "scolarité", "étudiant", "licence", "master", "doctorat",
        "cours", "horaire", "service", "recteur", "doyen"
    ]
    
    question_lower = question.lower()
    
    # Vérifier si la question contient des mots-clés UAM
    for keyword in keywords_uam:
        if keyword in question_lower:
            return "PERTINENT"
    
    # Questions générales sur l'éducation peuvent être pertinentes
    education_keywords = ["comment s'inscrire", "quelles formations", "quel diplôme"]
    for keyword in education_keywords:
        if keyword in question_lower:
            return "PERTINENT"
    
    return "HORS_SUJET"


@tool
def calculate_fees(level: str, faculty: str = "") -> str:
    """
    Calcule les frais de scolarité selon le niveau et la faculté.
    Utilise la base de données si disponible pour obtenir les tarifs à jour.
    
    Args:
        level: Niveau d'étude (licence, master, doctorat)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les frais de scolarité (à jour si BD disponible)
    """
    results_parts = []
    
    # 1. Recherche dans la base de données (si disponible)
    if _db_available:
        try:
            # Détecter l'abréviation de la faculté si nécessaire
            faculty_abbrev = None
            if faculty:
                structure_info = get_structure_info(faculty)
                if structure_info:
                    faculty_abbrev = structure_info["abreviation"]
                else:
                    faculty_abbrev = faculty.upper()
            
            # Obtenir l'année académique actuelle
            current_year = datetime.now().year
            
            db_results = search_fees_db(level=level, faculty=faculty_abbrev, year=current_year)
            
            if db_results:
                results_parts.append("💰 FRAIS DE SCOLARITÉ À JOUR (BASE DE DONNÉES) :")
                results_parts.append("")
                for fee in db_results[:5]:  # Limiter à 5 résultats
                    fee_info = []
                    if "level" in fee:
                        fee_info.append(f"Niveau : {fee['level'].capitalize()}")
                    if "faculty" in fee:
                        fee_info.append(f"Faculté : {fee['faculty']}")
                    if "amount" in fee:
                        fee_info.append(f"Montant : {fee['amount']:,} FCFA")
                    if "academic_year" in fee:
                        fee_info.append(f"Année académique : {fee['academic_year']}")
                    if "description" in fee:
                        fee_info.append(f"Description : {fee['description']}")
                    
                    results_parts.append("\n".join(fee_info))
                    results_parts.append("---")
                    results_parts.append("")
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche dans la base de données : {e}")
    
    # 2. Tarifs de base (fallback si pas de BD ou pas de résultats)
    if not results_parts:
        fees_base = {
            "licence": {
                "base": 50000,  # FCFA
                "description": "Frais de scolarité pour la Licence"
            },
            "master": {
                "base": 75000,  # FCFA
                "description": "Frais de scolarité pour le Master"
            },
            "doctorat": {
                "base": 100000,  # FCFA
                "description": "Frais de scolarité pour le Doctorat"
            }
        }
        
        level_lower = level.lower()
        
        if level_lower in fees_base:
            info = fees_base[level_lower]
            results_parts.append(f"💰 {info['description']}: {info['base']:,} FCFA par an")
            if faculty:
                results_parts.append(f"Faculté: {faculty}")
            results_parts.append("\n⚠️ Note: Ces tarifs sont indicatifs. Veuillez contacter le service de scolarité pour les tarifs exacts.")
        else:
            return f"Niveau '{level}' non reconnu. Niveaux disponibles: licence, master, doctorat"
    
    return "\n".join(results_parts)


@tool
def search_formations(faculty: str = "", level: str = "") -> str:
    """
    Recherche les formations disponibles selon la faculté et le niveau.
    Combine les résultats de la base de données (si disponible) et des documents.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        level: Niveau d'étude (licence, master, doctorat) - optionnel
        
    Returns:
        Liste des formations disponibles avec informations à jour
    """
    results_parts = []
    
    # 1. Recherche dans la base de données (si disponible)
    if _db_available:
        try:
            # Détecter l'abréviation de la faculté si nécessaire
            faculty_abbrev = None
            if faculty:
                structure_info = get_structure_info(faculty)
                if structure_info:
                    faculty_abbrev = structure_info["abreviation"]
                else:
                    faculty_abbrev = faculty.upper()
            
            db_results = search_formations_db(faculty=faculty_abbrev, level=level)
            
            if db_results:
                results_parts.append("📊 INFORMATIONS À JOUR DEPUIS LA BASE DE DONNÉES :")
                results_parts.append("")
                for formation in db_results[:10]:  # Limiter à 10 résultats
                    formation_info = []
                    if "name" in formation:
                        formation_info.append(f"• {formation['name']}")
                    if "faculty" in formation:
                        formation_info.append(f"  Faculté : {formation['faculty']}")
                    if "level" in formation:
                        formation_info.append(f"  Niveau : {formation['level']}")
                    if "description" in formation:
                        formation_info.append(f"  Description : {formation['description']}")
                    if "duration_years" in formation:
                        formation_info.append(f"  Durée : {formation['duration_years']} ans")
                    
                    results_parts.append("\n".join(formation_info))
                    results_parts.append("")
                
                results_parts.append("---")
                results_parts.append("")
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche dans la base de données : {e}")
    
    # 2. Recherche dans les documents (base de connaissances)
    if _vectorstore is None:
        if not results_parts:
            return "Erreur: Base de connaissances non initialisée"
    else:
        # Construire la requête de recherche
        query_parts = []
        if faculty:
            query_parts.append(f"faculté {faculty}")
        if level:
            query_parts.append(f"formation {level}")
        
        query = " ".join(query_parts) if query_parts else "formations disponibles"
        
        # Recherche dans la base de connaissances
        docs = _vectorstore.similarity_search(query, k=5)
        
        if docs:
            if results_parts:
                results_parts.append("📄 INFORMATIONS COMPLÉMENTAIRES DES DOCUMENTS :")
            else:
                results_parts.append("📄 FORMATIONS DISPONIBLES :")
            results_parts.append("")
            
            for doc in docs:
                results_parts.append(doc.page_content[:500])  # Limiter la longueur
                results_parts.append("---")
    
    if not results_parts:
        return f"Aucune formation trouvée pour {faculty if faculty else 'toutes les facultés'}"
    
    return "\n\n".join(results_parts)


@tool
def get_faculty_info(faculty_name: str) -> str:
    """
    Obtient des informations détaillées sur une faculté, école ou institut spécifique.
    Recherche automatiquement la définition et la mission de la structure.
    
    Args:
        faculty_name: Nom ou abréviation de la structure (ex: "FA", "FAST", "Faculté d'Agronomie", "ENS")
        
    Returns:
        Informations complètes sur la structure incluant : nom complet, type, définition et mission
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Vérifier d'abord dans la base de connaissances structurée
    structure_info = get_structure_info(faculty_name)
    
    result_parts = []
    
    if structure_info:
        result_parts.append(f"📋 {structure_info['nom_complet']} ({structure_info['abreviation']})")
        result_parts.append(f"Type: {structure_info['type'].capitalize()}")
        result_parts.append("")
        
        # Recherche spécifique pour la définition et la mission
        nom_complet = structure_info['nom_complet']
        
        # Recherche 1 : Définition
        query_definition = f"{nom_complet} définition présentation description"
        docs_definition = _vectorstore.similarity_search(query_definition, k=2)
        
        # Recherche 2 : Mission
        query_mission = f"{nom_complet} mission objectifs rôles fonctions"
        docs_mission = _vectorstore.similarity_search(query_mission, k=2)
        
        # Recherche 3 : Informations générales
        query_general = f"{nom_complet} informations générales"
        docs_general = _vectorstore.similarity_search(query_general, k=3)
        
        # Combiner tous les résultats uniques
        all_docs = {}
        for doc in docs_definition + docs_mission + docs_general:
            # Utiliser le contenu comme clé pour éviter les doublons
            content_key = doc.page_content[:200]  # Premiers 200 caractères comme clé
            if content_key not in all_docs:
                all_docs[content_key] = doc.page_content
        
        if all_docs:
            result_parts.append("📖 DÉFINITION ET MISSION :")
            result_parts.append("")
            for i, content in enumerate(all_docs.values(), 1):
                result_parts.append(content[:1000])  # Limiter à 1000 caractères par document
                if i < len(all_docs):
                    result_parts.append("---")
        else:
            # Si pas de résultats spécifiques, faire une recherche générale
            search_query = nom_complet
            docs = _vectorstore.similarity_search(search_query, k=3)
            
            if docs:
                result_parts.append("📖 INFORMATIONS :")
                result_parts.append("")
                for doc in docs:
                    result_parts.append(doc.page_content[:800])
                    result_parts.append("---")
    else:
        # Si la structure n'est pas trouvée dans la base structurée, faire une recherche générale
        search_query = f"{faculty_name} faculté école institut"
        docs = _vectorstore.similarity_search(search_query, k=3)
        
        if docs:
            result_parts.append(f"Informations sur '{faculty_name}' :")
            result_parts.append("")
            for doc in docs:
                result_parts.append(doc.page_content[:800])
                result_parts.append("---")
        else:
            return f"Aucune information trouvée sur '{faculty_name}'. Vérifiez l'orthographe ou utilisez l'abréviation."
    
    return "\n\n".join(result_parts)


@tool
def get_structure_by_abbreviation(abbreviation: str) -> str:
    """
    Obtient le nom complet d'une structure à partir de son abréviation.
    
    Args:
        abbreviation: Abréviation de la structure (ex: "FAST", "FLSH", "ENS")
        
    Returns:
        Nom complet et informations sur la structure
    """
    structure_info = get_structure_info(abbreviation)
    
    if structure_info:
        return f"{structure_info['nom_complet']} ({structure_info['abreviation']})\nType: {structure_info['type'].capitalize()}"
    else:
        # Liste toutes les structures disponibles
        all_structures = []
        for category in ["facultes", "instituts", "ecoles"]:
            category_name = category.capitalize()[:-1]  # Enlever le 's'
            structures = [f"{info['nom_complet']} ({abbrev})" 
                         for abbrev, info in UAM_STRUCTURES[category].items()]
            all_structures.append(f"{category_name}:\n" + "\n".join(f"  - {s}" for s in structures))
        
        return f"Abréviation '{abbreviation}' non trouvée.\n\nStructures disponibles:\n\n" + "\n\n".join(all_structures)


def _list_all_structures_internal() -> str:
    """
    Fonction interne pour lister toutes les structures (utilisée par l'outil)
    """
    result = []
    
    result.append(" STRUCTURES DE L'UNIVERSITÉ ABDOU MOUMOUNI DE NIAMEY\n")
    result.append("=" * 60)
    
    # Facultés
    result.append("\n FACULTÉS:")
    for abbrev, info in UAM_STRUCTURES["facultes"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    # Instituts
    result.append("\n INSTITUTS DE RECHERCHE:")
    for abbrev, info in UAM_STRUCTURES["instituts"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    # Écoles
    result.append("\n ÉCOLES:")
    for abbrev, info in UAM_STRUCTURES["ecoles"].items():
        result.append(f"  • {info['nom_complet']} ({abbrev})")
    
    return "\n".join(result)


@tool
def list_all_structures() -> str:
    """
    Liste toutes les facultés, écoles et instituts de l'UAM avec leurs abréviations.
    
    Returns:
        Liste complète des structures de l'UAM
    """
    return _list_all_structures_internal()


@tool
def save_user_preference(user_id: str, preference_key: str, preference_value: str) -> str:
    """
    Sauvegarde une préférence utilisateur pour la mémoire à long terme.
    
    Args:
        user_id: Identifiant de l'utilisateur
        preference_key: Clé de la préférence (ex: 'faculte_interesse', 'niveau_etude')
        preference_value: Valeur de la préférence
        
    Returns:
        Confirmation de sauvegarde
    """
    _user_memory.save_user_preference(user_id, preference_key, preference_value)
    return f"Préférence '{preference_key}' sauvegardée avec succès: {preference_value}"


@tool
def get_user_preferences(user_id: str) -> str:
    """
    Récupère les préférences sauvegardées d'un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        
    Returns:
        Préférences de l'utilisateur au format JSON
    """
    preferences = _user_memory.get_user_preferences(user_id)
    if not preferences:
        return "Aucune préférence sauvegardée pour cet utilisateur."
    return json.dumps(preferences, ensure_ascii=False, indent=2)


@tool
def search_prerequisites(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les prérequis (pré-requis) nécessaires pour une filière ou une faculté.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel, ex: "FAST", "Faculté des Sciences")
        
    Returns:
        Informations sur les prérequis
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"prérequis pré-requis conditions admission {filiere}")
    if faculty:
        # Détecter la structure pour obtenir le nom complet
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} prérequis pré-requis conditions admission")
        else:
            query_parts.append(f"{faculty} prérequis pré-requis conditions admission")
    
    query = " ".join(query_parts) if query_parts else "prérequis pré-requis conditions admission filière"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les prérequis trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    # Combiner les résultats
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_competences_requises(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les connaissances et compétences requises pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les connaissances et compétences requises
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"compétences connaissances requises {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} compétences connaissances requises")
        else:
            query_parts.append(f"{faculty} compétences connaissances requises")
    
    query = " ".join(query_parts) if query_parts else "compétences connaissances requises filière"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les compétences requises trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_cycles_et_duree(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les cycles disponibles et la durée d'études pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les cycles (licence, master, doctorat) et leurs durées
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"cycles durée études licence master doctorat {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} cycles durée études licence master doctorat")
        else:
            query_parts.append(f"{faculty} cycles durée études licence master doctorat")
    
    query = " ".join(query_parts) if query_parts else "cycles durée études licence master doctorat"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les cycles et durées trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_chronogramme(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche le chronogramme annuel d'études (modules, heures de cours) pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur le chronogramme, les modules et les heures de cours
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"chronogramme modules heures cours emploi temps programme {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} chronogramme modules heures cours emploi temps programme")
        else:
            query_parts.append(f"{faculty} chronogramme modules heures cours emploi temps programme")
    
    query = " ".join(query_parts) if query_parts else "chronogramme modules heures cours emploi temps programme"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur le chronogramme trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_coefficients(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les coefficients des différents modules pour une filière.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les coefficients des modules
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"coefficients modules {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} coefficients modules")
        else:
            query_parts.append(f"{faculty} coefficients modules")
    
    query = " ".join(query_parts) if query_parts else "coefficients modules"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les coefficients trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_professeurs(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les professeurs assignés aux différents modules et leurs qualifications.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les professeurs et leurs qualifications
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"professeurs enseignants corps professoral qualifications {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} professeurs enseignants corps professoral qualifications")
        else:
            query_parts.append(f"{faculty} professeurs enseignants corps professoral qualifications")
    
    query = " ".join(query_parts) if query_parts else "professeurs enseignants corps professoral qualifications"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les professeurs trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_debouches(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les débouchés professionnels et les possibilités d'embauche après les études.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les débouchés professionnels et les possibilités d'embauche
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"débouchés professionnels embauche emploi carrière métiers {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} débouchés professionnels embauche emploi carrière métiers")
        else:
            query_parts.append(f"{faculty} débouchés professionnels embauche emploi carrière métiers")
    
    query = " ".join(query_parts) if query_parts else "débouchés professionnels embauche emploi carrière métiers"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les débouchés trouvée pour {filiere if filiere else faculty if faculty else 'les filières'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_reglement_interieur(faculty: str = "") -> str:
    """
    Recherche le règlement intérieur d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel, si vide recherche le règlement général)
        
    Returns:
        Informations sur le règlement intérieur
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} règlement intérieur règles discipline"
        else:
            query = f"{faculty} règlement intérieur règles discipline"
    else:
        query = "règlement intérieur UAM université règles discipline"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur le règlement intérieur trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_organisation_corps_professoral(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps professoral d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur l'organisation du corps professoral
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} organisation corps professoral structure enseignants"
        else:
            query = f"{faculty} organisation corps professoral structure enseignants"
    else:
        query = "organisation corps professoral UAM structure enseignants"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur l'organisation du corps professoral trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_organisation_corps_estudiantin(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps estudiantin (associations étudiantes, clubs, etc.) d'une faculté ou de l'université.
    
    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur l'organisation du corps estudiantin
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query = f"{structure_info['nom_complet']} organisation corps estudiantin associations étudiantes clubs étudiants"
        else:
            query = f"{faculty} organisation corps estudiantin associations étudiantes clubs étudiants"
    else:
        query = "organisation corps estudiantin UAM associations étudiantes clubs étudiants"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur l'organisation du corps estudiantin trouvée pour {faculty if faculty else 'l\'UAM'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_reclamations() -> str:
    """
    Recherche les différents types de réclamations possibles et comment les faire.
    
    Returns:
        Informations sur les réclamations et les procédures pour les faire
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    query = "réclamations réclamation procédure comment faire démarche"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return "Aucune information sur les réclamations trouvée dans la base de connaissances."
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_avantages_universite(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les avantages de suivre une filière à l'université plutôt que dans d'autres écoles et instituts.
    
    Args:
        filiere: Nom de la filière (optionnel)
        faculty: Nom ou abréviation de la faculté (optionnel)
        
    Returns:
        Informations sur les avantages de l'université
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if filiere:
        query_parts.append(f"avantages université UAM {filiere} écoles instituts")
    if faculty:
        structure_info = get_structure_info(faculty)
        if structure_info:
            query_parts.append(f"{structure_info['nom_complet']} avantages université écoles instituts")
        else:
            query_parts.append(f"{faculty} avantages université écoles instituts")
    
    query = " ".join(query_parts) if query_parts else "avantages université UAM écoles instituts"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune information sur les avantages trouvée pour {filiere if filiere else faculty if faculty else 'l\'université'}"
    
    results = []
    for doc in docs:
        results.append(doc.page_content[:800])
    
    return "\n\n---\n\n".join(results)


@tool
def search_latest_news(limit: int = 5, category: str = "") -> str:
    """
    Recherche les dernières actualités et annonces de l'UAM depuis la base de données.
    
    Args:
        limit: Nombre maximum d'actualités à retourner (défaut: 5)
        category: Catégorie d'annonce (optionnel, ex: "admission", "examen", "formation")
        
    Returns:
        Liste des dernières actualités et annonces
    """
    if not _db_available:
        return "⚠️ Base de données non disponible. Les actualités ne peuvent pas être récupérées."
    
    try:
        announcements = search_news_announcements_db(limit=limit, category=category)
        
        if not announcements:
            return "Aucune actualité trouvée."
        
        results_parts = []
        results_parts.append("📢 DERNIÈRES ACTUALITÉS ET ANNONCES UAM :")
        results_parts.append("")
        
        for i, announcement in enumerate(announcements, 1):
            ann_info = []
            ann_info.append(f"{i}. {announcement.get('title', 'Sans titre')}")
            
            if "published_date" in announcement:
                ann_info.append(f"   Date : {announcement['published_date']}")
            
            if "category" in announcement:
                ann_info.append(f"   Catégorie : {announcement['category']}")
            
            if "content" in announcement:
                content = announcement['content'][:300]  # Limiter à 300 caractères
                ann_info.append(f"   {content}...")
            
            if "link" in announcement:
                ann_info.append(f"   Lien : {announcement['link']}")
            
            results_parts.append("\n".join(ann_info))
            results_parts.append("")
        
        return "\n".join(results_parts)
        
    except Exception as e:
        return f"Erreur lors de la récupération des actualités : {e}"


@tool
def get_schedules_from_db(faculty: str = "", filiere: str = "", level: str = "") -> str:
    """
    Recherche les horaires/emplois du temps depuis la base de données.
    
    Args:
        faculty: Abréviation de la faculté (optionnel)
        filiere: Nom de la filière (optionnel)
        level: Niveau d'étude (optionnel)
        
    Returns:
        Informations sur les horaires et emplois du temps
    """
    if not _db_available:
        return "⚠️ Base de données non disponible. Les horaires ne peuvent pas être récupérés depuis la BD."
    
    try:
        # Détecter l'abréviation de la faculté si nécessaire
        faculty_abbrev = None
        if faculty:
            structure_info = get_structure_info(faculty)
            if structure_info:
                faculty_abbrev = structure_info["abreviation"]
            else:
                faculty_abbrev = faculty.upper()
        
        # Utiliser la fonction importée depuis database_connector
        # Utiliser la fonction importée depuis database_connector (au niveau global)
        # Note: search_schedules_db est importée au niveau global si disponible
        try:
            schedules = search_schedules_db(faculty=faculty_abbrev, filiere=filiere, level=level)
        except NameError:
            # Si la fonction n'est pas disponible, retourner un message
            return "⚠️ Fonction de recherche dans la base de données non disponible."
        
        if not schedules:
            return f"Aucun horaire trouvé pour {faculty if faculty else 'les structures'}."
        
        results_parts = []
        results_parts.append("📅 HORAIRES ET EMPLOIS DU TEMPS (BASE DE DONNÉES) :")
        results_parts.append("")
        
        for schedule in schedules[:20]:  # Limiter à 20 résultats
            sched_info = []
            if "filiere_name" in schedule:
                sched_info.append(f"Filière : {schedule['filiere_name']}")
            if "day_of_week" in schedule:
                sched_info.append(f"Jour : {schedule['day_of_week']}")
            if "start_time" in schedule and "end_time" in schedule:
                sched_info.append(f"Heure : {schedule['start_time']} - {schedule['end_time']}")
            if "module_name" in schedule:
                sched_info.append(f"Module : {schedule['module_name']}")
            if "room" in schedule:
                sched_info.append(f"Salle : {schedule['room']}")
            if "professor" in schedule:
                sched_info.append(f"Professeur : {schedule['professor']}")
            
            results_parts.append("\n".join(sched_info))
            results_parts.append("---")
            results_parts.append("")
        
        return "\n".join(results_parts)
        
    except Exception as e:
        return f"Erreur lors de la récupération des horaires : {e}"


def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    tools = [
        detect_greeting,
        search_uam_knowledge,
        check_question_relevance,
        calculate_fees,
        search_formations,
        get_faculty_info,
        get_structure_by_abbreviation,
        list_all_structures,
        save_user_preference,
        get_user_preferences,
        # Nouveaux outils pour répondre aux questions des étudiants
        search_prerequisites,
        search_competences_requises,
        search_cycles_et_duree,
        search_chronogramme,
        search_coefficients,
        search_professeurs,
        search_debouches,
        search_reglement_interieur,
        search_organisation_corps_professoral,
        search_organisation_corps_estudiantin,
        search_reclamations,
        search_avantages_universite
    ]
    
    # Ajouter les outils de base de données si disponible
    if _db_available:
        tools.extend([
            search_latest_news,
            get_schedules_from_db
        ])
    
    return tools


# ==================== NŒUDS DU GRAPHE ====================

def route_question(state: AgentState) -> Literal["agent", "reject_query"]:
    """
    Route la question selon sa pertinence.
    Version améliorée : pour les questions pertinentes, utilise le pattern agent avec outils automatiques.
    Gère aussi les salutations pour être accueillant.
    Détecte les abréviations simples pour fournir automatiquement les informations de base.
    """
    # Utiliser le dernier message
    if not state["messages"]:
        return "reject_query"
    
    last_message = state["messages"][-1]
    question = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # S'assurer que question est une chaîne de caractères
    if not isinstance(question, str):
        question = str(question)
    
    question_stripped = question.strip().upper()
    
    # Détecter si c'est juste une abréviation simple (ex: "FA", "FAST", "ENS")
    # Liste de toutes les abréviations possibles
    all_abbreviations = []
    for category in ["facultes", "instituts", "ecoles"]:
        all_abbreviations.extend(UAM_STRUCTURES[category].keys())
    
    # Vérifier si la question est exactement une abréviation (avec ou sans espaces)
    is_simple_abbreviation = question_stripped in all_abbreviations
    
    # Détecter les salutations
    greeting_type = detect_greeting.invoke({"message": question})
    
    # Si c'est juste une salutation sans question UAM, toujours accepter pour être accueillant
    if greeting_type == "GREETING" and not is_simple_abbreviation:
        return "agent"  # L'agent répondra poliment à la salutation
    
    # Si c'est une simple abréviation, toujours accepter pour fournir les infos de base
    if is_simple_abbreviation:
        return "agent"  # L'agent utilisera get_faculty_info automatiquement
    
    # Vérifier la pertinence avec l'outil
    relevance = check_question_relevance.invoke({"question": question})
    
    if "PERTINENT" in relevance or greeting_type == "BOTH":
        # Utiliser le pattern agent amélioré avec appel automatique d'outils
        return "agent"
    return "reject_query"


def search_knowledge(state: AgentState) -> AgentState:
    """Recherche le contexte dans la base de connaissances"""
    if not state["messages"]:
        return state
    
    last_message = state["messages"][-1]
    question = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # Utiliser l'outil de recherche
    context = search_uam_knowledge.invoke({"query": question})
    
    # Mettre à jour l'état avec le contexte trouvé
    return {
        **state,
        "context": context,
        "question": question,
        "is_relevant": True
    }


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Détermine si l'agent doit appeler des outils ou terminer la conversation.
    Utilise le pattern recommandé de LangGraph 1.0.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # Si le dernier message contient des appels d'outils, exécuter les outils
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    # Sinon, terminer
    return "end"


def call_model(state: AgentState, llm_with_tools) -> AgentState:
    """
    Appelle le LLM avec les outils bindés pour générer une réponse ou appeler des outils.
    Pattern amélioré selon LangGraph 1.0 avec prompt système pour guider l'utilisation des outils.
    """
    messages = state["messages"]
    
    # Détecter les salutations et structures dans le dernier message
    last_message = messages[-1] if messages else None
    question = last_message.content if (last_message and hasattr(last_message, 'content')) else ""
    
    # S'assurer que question est une chaîne de caractères
    if not isinstance(question, str):
        question = str(question)
    
    # Détecter les structures mentionnées pour enrichir le contexte
    detected_structures = detect_structure_in_text(question)
    structures_context = ""
    if detected_structures:
        structures_info = []
        for struct in detected_structures:
            structures_info.append(f"- {struct['nom_complet']} ({struct['abreviation']}) - {struct['type'].capitalize()}")
        structures_context = f"\n\nSTRUCTURES DÉTECTÉES DANS LA QUESTION :\n" + "\n".join(structures_info)
    
    # Créer un prompt système pour guider le LLM
    system_prompt = """Tu es l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

TON RÔLE :
Tu es un assistant virtuel professionnel, accueillant et respectueux, spécialisé dans l'accompagnement des étudiants, 
candidats et visiteurs de l'UAM. Tu représentes l'université avec courtoisie et professionnalisme.

CONSIGNES DE COMMUNICATION :
- SOIS TOUJOURS ACCUEILLANT : Commence par saluer poliment l'utilisateur (Bonjour, Bonsoir, etc.)
- SOIS POLI ET RESPECTUEUX : Utilise "vous" pour vous adresser à l'utilisateur, sauf indication contraire
- SOIS PROFESSIONNEL : Maintiens un ton formel mais chaleureux, adapté au contexte universitaire
- SOIS CLAR ET PRÉCIS : Structure tes réponses avec des paragraphes courts et des listes à puces quand c'est pertinent
- SOIS EMPATHIQUE : Montre de la compréhension et de l'empathie face aux préoccupations des utilisateurs

GESTION DES SALUTATIONS :
- Si l'utilisateur te salue, réponds poliment avec une salutation appropriée
- Si c'est une simple salutation sans question, réponds chaleureusement et propose ton aide
- Si la salutation accompagne une question, salue d'abord puis réponds à la question

COMPRÉHENSION DES ABRÉVIATIONS :
- Tu comprends automatiquement les abréviations des structures UAM :
  * FAST = Faculté des Sciences et Techniques
  * FLSH = Faculté des Lettres et Sciences Humaines
  * FA = Faculté d'Agronomie
  * FSEG = Faculté des Sciences Économiques et de Gestion
  * FSJP = Faculté des Sciences Juridiques et Politiques
  * FSS = Faculté des Sciences de la Santé
  * ENS = École Normale Supérieure
  * ED-SVT = École Doctorale des Sciences de la Vie et de la Terre
  * ED-LASHS = École Doctorale des Lettres, Arts, Sciences de l'Homme et de la Société
  * ED-SET = École Doctorale des Sciences Exactes et Techniques
  * IRSH = Institut de Recherche en Sciences Humaines
  * IREM = Institut de Recherches pour l'Enseignement des Mathématiques
  * IRI = Institut des Radio-isotopes

GESTION DES ABRÉVIATIONS SIMPLES :
- Si l'utilisateur tape juste une abréviation (ex: "FA", "FAST", "ENS"), utilise IMMÉDIATEMENT l'outil get_faculty_info
- L'outil get_faculty_info fournit automatiquement : le nom complet, la définition et la mission de la structure
- Présente les informations de manière structurée : nom complet, type, définition, mission
- Mentionne toujours le nom complet de la structure dans ta réponse

UTILISATION DES OUTILS - GUIDE COMPLET :

OUTILS GÉNÉRAUX :
- search_uam_knowledge : Recherche générale dans la base de connaissances (utilise-le en premier pour la plupart des questions)
- detect_greeting : Identifie les salutations pour adapter ta réponse
- get_faculty_info : Obtient des informations détaillées sur une faculté/école/institut (nom complet, définition, mission)
  * À UTILISER EN PRIORITÉ quand l'utilisateur tape juste une abréviation (ex: "FA", "FAST", "ENS")
  * Fournit automatiquement la définition et la mission de la structure
- get_structure_by_abbreviation : Convertit une abréviation en nom complet (ex: FAST → Faculté des Sciences et Techniques)
- list_all_structures : Liste toutes les structures de l'UAM

OUTILS BASE DE DONNÉES (INFORMATIONS À JOUR) :
- search_latest_news : Récupère les dernières actualités et annonces depuis la base de données
- get_schedules_from_db : Récupère les horaires/emplois du temps depuis la base de données
- search_formations : Combine automatiquement les résultats de la BD (à jour) et des documents
- calculate_fees : Utilise la base de données pour obtenir les tarifs les plus récents

OUTILS SPÉCIALISÉS POUR LES QUESTIONS DES ÉTUDIANTS :

1. QUESTIONS SUR LES FILIÈRES :
   - search_formations : Recherche les filières disponibles (par faculté et/ou niveau)
   - search_prerequisites : Recherche les prérequis/pré-requis pour une filière
   - search_competences_requises : Recherche les connaissances et compétences requises
   - search_cycles_et_duree : Recherche les cycles (licence, master, doctorat) et leurs durées
   - search_avantages_universite : Recherche les avantages de l'université vs autres écoles

2. QUESTIONS SUR LE PROGRAMME D'ÉTUDES :
   - search_chronogramme : Recherche le chronogramme annuel (modules, heures de cours, emploi du temps)
   - search_coefficients : Recherche les coefficients des différents modules

3. QUESTIONS SUR LES ENSEIGNANTS :
   - search_professeurs : Recherche les professeurs assignés aux modules et leurs qualifications
   - search_organisation_corps_professoral : Recherche l'organisation du corps professoral

4. QUESTIONS SUR LES DÉBOUCHÉS :
   - search_debouches : Recherche les débouchés professionnels et possibilités d'embauche

5. QUESTIONS SUR LA VIE ÉTUDIANTE :
   - search_organisation_corps_estudiantin : Recherche l'organisation du corps estudiantin (associations, clubs)
   - search_reglement_interieur : Recherche le règlement intérieur
   - search_reclamations : Recherche les types de réclamations et comment les faire

6. AUTRES OUTILS :
   - calculate_fees : Calcule les frais de scolarité
   - save_user_preference / get_user_preferences : Gère les préférences utilisateur

STRATÉGIE D'UTILISATION :
- **PRIORITÉ 1** : Si l'utilisateur tape juste une abréviation (ex: "FA", "FAST", "ENS"), utilise IMMÉDIATEMENT get_faculty_info
- **INFORMATIONS À JOUR** : Les outils search_formations et calculate_fees combinent automatiquement les données de la base de données (à jour) et des documents
- Pour les questions sur les filières : Utilise search_formations (combine BD + documents automatiquement)
- Pour les questions sur les frais : Utilise calculate_fees (utilise la BD pour les tarifs à jour)
- Pour les actualités/annonces : Utilise search_latest_news pour les dernières informations
- Pour les horaires : Utilise get_schedules_from_db pour les emplois du temps à jour
- Pour les questions sur les prérequis : Utilise search_prerequisites
- Pour les questions sur les compétences : Utilise search_competences_requises
- Pour les questions sur les cycles/durées : Utilise search_cycles_et_duree
- Pour les questions sur le programme : Utilise search_chronogramme et/ou search_coefficients
- Pour les questions sur les professeurs : Utilise search_professeurs
- Pour les questions sur les débouchés : Utilise search_debouches
- Pour les questions sur le règlement : Utilise search_reglement_interieur
- Pour les questions sur les réclamations : Utilise search_reclamations
- Pour les questions générales : Utilise search_uam_knowledge en premier

IMPORTANT :
- Base-toi UNIQUEMENT sur les informations trouvées dans la base de connaissances
- Si l'information n'est pas disponible, indique-le poliment et propose d'orienter vers le service approprié
- Utilise plusieurs outils si nécessaire pour donner une réponse complète

STRUCTURE DES RÉPONSES :
1. Salutation appropriée (si première interaction ou si l'utilisateur a salué)
2. Réponse à la question avec informations précises
3. Mention des sources pertinentes (faculté, institut concerné)
4. Proposition d'aide supplémentaire si pertinent
5. Formule de politesse de clôture si approprié

EXEMPLES DE RÉPONSES ACCUEILLANTES :
- "Bonjour ! Je suis ravi de vous aider concernant [sujet]. [Réponse à la question]..."
- "Bonsoir ! Concernant votre question sur [sujet], voici les informations que je peux vous fournir..."
- "Merci pour votre question. Je vais vous fournir les informations sur [sujet]..."

IMPORTANT : 
- Ne sors JAMAIS du cadre universitaire - tu ne réponds qu'aux questions sur l'UAM
- Reste professionnel et respectueux en toutes circonstances
- Utilise toujours les outils pour obtenir des informations précises avant de répondre""" + structures_context
    
    # Ajouter le prompt système au début des messages s'il n'y en a pas déjà
    if not messages or not isinstance(messages[0], SystemMessage):
        messages_with_system = [SystemMessage(content=system_prompt)] + list(messages)
    else:
        messages_with_system = messages
    
    # Appeler le LLM avec les outils bindés
    response = llm_with_tools.invoke(messages_with_system)
    
    return {
        **state,
        "messages": [response]
    }


def generate_response(state: AgentState, llm) -> AgentState:
    """
    Génère une réponse basée sur le contexte.
    Version améliorée qui utilise le contexte déjà récupéré.
    """
    # Récupérer le contexte depuis l'état
    context = state.get("context", "")
    messages = state["messages"]
    
    # Détecter les structures dans les messages pour enrichir le contexte
    question_text = ""
    for msg in reversed(messages):
        if hasattr(msg, 'content'):
            question_text = msg.content
            break
    
    # S'assurer que question_text est une chaîne de caractères
    if not isinstance(question_text, str):
        question_text = str(question_text)
    
    detected_structures = detect_structure_in_text(question_text)
    structures_info = ""
    if detected_structures:
        structures_list = [f"{s['nom_complet']} ({s['abreviation']})" for s in detected_structures]
        structures_info = f"\n\nStructures mentionnées : {', '.join(structures_list)}"
    
    # Créer le prompt avec le contexte
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Tu es l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

TON RÔLE :
Tu es un assistant virtuel professionnel, accueillant et respectueux, spécialisé dans l'accompagnement des étudiants, 
candidats et visiteurs de l'UAM.

CONSIGNES DE COMMUNICATION :
- SOIS TOUJOURS ACCUEILLANT : Commence par saluer poliment l'utilisateur si c'est approprié
- SOIS POLI ET RESPECTUEUX : Utilise "vous" pour vous adresser à l'utilisateur
- SOIS PROFESSIONNEL : Maintiens un ton formel mais chaleureux, adapté au contexte universitaire
- SOIS CLAR ET PRÉCIS : Structure tes réponses avec des paragraphes courts et des listes à puces

COMPRÉHENSION DES ABRÉVIATIONS :
- Tu comprends automatiquement les abréviations : FAST, FLSH, FA, FSEG, FSJP, FSS, ENS, ED-SVT, ED-LASHS, ED-SET, IRSH, IREM, IRI
- Mentionne toujours le nom complet de la structure dans ta réponse

CONTEXTE DISPONIBLE :
{context}{structures_info}

Si le contexte ne contient pas l'information demandée, réponds poliment :
"Je n'ai pas trouvé cette information spécifique dans ma base de connaissances. Je vous recommande de contacter [service approprié] pour obtenir une réponse précise. N'hésitez pas à me poser d'autres questions sur l'UAM !"
"""),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Générer la réponse avec le contexte
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "context": context,
        "structures_info": structures_info,
        "messages": messages
    })
    
    # Retourner l'état mis à jour - Annotated[Sequence[BaseMessage], add] fusionne automatiquement
    return {
        **state,
        "response": response,
        "messages": [AIMessage(content=response)]  # Sera automatiquement ajouté à la liste existante
    }


def reject_query(state: AgentState) -> AgentState:
    """Rejette poliment les questions hors sujet avec une réponse accueillante"""
    # Vérifier si c'est une salutation
    last_message = state["messages"][-1] if state["messages"] else None
    question = last_message.content if (last_message and hasattr(last_message, 'content')) else ""
    greeting_type = detect_greeting.invoke({"message": question})
    
    if greeting_type == "GREETING":
        # Répondre poliment à la salutation même si hors sujet
        response = """Bonjour ! Je suis l'assistant virtuel de l'Université Abdou Moumouni de Niamey (UAM).

Je suis là pour vous aider avec toutes vos questions concernant l'UAM :
- 📋 Informations sur les facultés, écoles et instituts
- 🎓 Formations et filières disponibles
- 📝 Conditions d'admission et pièces d'inscription
- 🏢 Démarches administratives (diplômes, attestations, relevés, etc.)
- ⏰ Horaires et services
- 📞 Contacts des différents services

Comment puis-je vous aider aujourd'hui ?"""
    else:
        response = """Bonjour ! Je suis désolé, mais je suis spécialisé uniquement dans les questions concernant l'Université Abdou Moumouni de Niamey (UAM).

Je peux vous aider avec :
- 📋 Informations sur les facultés, écoles et instituts
- 🎓 Formations et filières disponibles
- 📝 Conditions d'admission et pièces d'inscription
- 🏢 Démarches administratives (diplômes, attestations, relevés, etc.)
- ⏰ Horaires et services
- 📞 Contacts des différents services

Avez-vous une question concernant l'UAM ? Je serai ravi de vous aider !"""
    
    # Retourner l'état mis à jour - Annotated[Sequence[BaseMessage], add] fusionne automatiquement
    return {
        **state,
        "response": response,
        "is_relevant": False,
        "messages": [AIMessage(content=response)]  # Sera automatiquement ajouté à la liste existante
    }


# ==================== CONSTRUCTION DU GRAPHE ====================
def create_agent_graph(vectorstore: FAISS, llm):
    """
    Crée le graphe LangGraph pour l'agent conversationnel avec les dernières fonctionnalités.
    Utilise le pattern recommandé de LangGraph 1.0 avec ToolNode et appel automatique des outils.
    
    Args:
        vectorstore: Index FAISS pour la recherche
        llm: LLM principal pour les réponses
    
    Returns:
        Application LangGraph compilée avec MemorySaver
    """
    # Initialiser le vectorstore global pour les outils
    set_vectorstore(vectorstore)
    
    # Obtenir les outils disponibles
    tools = get_tools()
    
    # Bind les outils au LLM pour permettre l'appel automatique
    # Le LLM décidera quand utiliser les outils
    llm_with_tools = llm.bind_tools(tools)
    
    # Créer le ToolNode pour exécuter automatiquement les appels d'outils
    tool_node = ToolNode(tools)
    
    # Créer le graphe avec StateGraph
    workflow = StateGraph(AgentState)
    
    # Ajouter les nœuds
    workflow.add_node("agent", lambda s: call_model(s, llm_with_tools))
    workflow.add_node("tools", tool_node)
    workflow.add_node("search_knowledge", search_knowledge)
    workflow.add_node("generate_response", lambda s: generate_response(s, llm))
    workflow.add_node("reject_query", reject_query)
    
    # Définir le point d'entrée avec routage conditionnel
    workflow.set_conditional_entry_point(
        route_question,
        {
            "agent": "agent",  # Utiliser le pattern agent amélioré
            "reject_query": "reject_query"
        }
    )
    
    # Routage conditionnel après l'agent : outils ou fin
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # Après l'exécution des outils, retourner à l'agent pour générer la réponse finale
    workflow.add_edge("tools", "agent")
    
    # Définir les transitions
    workflow.add_edge("reject_query", END)
    
    # Garder les nœuds de recherche pour compatibilité (peuvent être utilisés dans d'autres flux)
    # workflow.add_edge("search_knowledge", "generate_response")
    # workflow.add_edge("generate_response", END)
    
    # Compiler avec MemorySaver pour la persistance de l'état
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


# ==================== INTERFACE UTILISATEUR ====================
def run_chatbot(pdf_directory: str, provider: LLMProvider, model_name: Optional[str] = None):
    """
    Lance le chatbot interactif
    
    Args:
        pdf_directory: Dossier contenant les documents
        provider: Provider LLM à utiliser
        model_name: Nom du modèle (optionnel)
    """
    print(f" Initialisation de l'agent conversationnel UAM avec {provider.value}...")
    print()
    
    # Initialiser le LLM
    llm = initialize_llm(provider, model_name, temperature=0.3)
    
    # Charger et indexer les documents
    vectorstore = load_and_index_documents(pdf_directory, provider)
    
    # Créer le graphe
    agent = create_agent_graph(vectorstore, llm)
    
    print()
    print(f" Agent prêt avec {provider.value} ! Posez vos questions sur l'UAM")
    print("  (Tapez 'quit', 'exit' ou 'bye' pour quitter)")
    print("=" * 60)
    print()
    
    # Générer un thread_id unique avec uuid pour chaque session
    thread_id = str(uuid.uuid4())
    print(f" Session ID: {thread_id}")
    print()
    
    # Configuration de session avec thread_id unique
    config = {"configurable": {"thread_id": thread_id}}
    
    # Message système initial accueillant
    system_message = SystemMessage(
        content="""Bonjour et bienvenue ! 👋

Je suis l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM). 

Je suis là pour vous accompagner et répondre à toutes vos questions concernant :
- 📋 Les facultés, écoles et instituts de l'UAM
- 🎓 Les formations et filières disponibles
- 📝 Les conditions d'admission et les pièces d'inscription
- 🏢 Les démarches administratives (diplômes, attestations, relevés, etc.)
- ⏰ Les horaires et services
- 📞 Les contacts des différents services

N'hésitez pas à me poser vos questions ! Je comprends aussi les abréviations comme FAST, FLSH, ENS, etc.

Comment puis-je vous aider aujourd'hui ?"""
    )
    
    # Initialiser l'état avec le message système
    initial_state = {
        "messages": [system_message],
        "question": "",
        "is_relevant": False,
        "context": "",
        "response": "",
        "need_clarification": False
    }
    
    # Mettre à jour l'état initial dans le graphe
    agent.invoke(initial_state, config)
    
    print("🤖 Assistant: Bonjour et bienvenue ! 👋")
    print("              Je suis l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).")
    print()
    print("              Je peux vous aider avec :")
    print("              📋 Informations sur les facultés, écoles et instituts")
    print("              🎓 Formations et filières disponibles")
    print("              📝 Conditions d'admission et pièces d'inscription")
    print("              🏢 Démarches administratives")
    print("              ⏰ Horaires et services")
    print()
    print("              💡 Astuce : Je comprends les abréviations comme FAST, FLSH, ENS, etc.")
    print()
    print("              Comment puis-je vous aider aujourd'hui ?")
    print()
    
    while True:
        try:
            user_input = input("👤 Vous: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', 'au revoir', 'quitter', 'à bientôt']:
                print()
                print("🤖 Assistant: Au revoir et merci de votre visite ! 🙏")
                print("              N'hésitez pas à revenir si vous avez d'autres questions sur l'UAM.")
                print("              Bonne continuation dans vos démarches universitaires !")
                print()
                break
            
            if not user_input:
                continue
            
            # Créer le message utilisateur
            user_message = HumanMessage(content=user_input)
            
            # Mettre à jour l'état avec le nouveau message utilisateur
            # LangGraph gère automatiquement l'ajout des messages grâce à Annotated[Sequence[BaseMessage], add]
            current_state = {
                "messages": [user_message],
                "question": user_input,
                "is_relevant": False,
                "context": "",
                "response": "",
                "need_clarification": False
            }
            
            # Exécuter le graphe - MemorySaver conserve automatiquement l'historique
            result = agent.invoke(current_state, config)
            
            # Afficher la réponse
            print()
            if result.get("response"):
                print(f" Assistant: {result['response']}")
            else:
                # Si pas de réponse directe, chercher dans les messages
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, AIMessage):
                        print(f" Assistant: {msg.content}")
                        break
            print()
            
        except KeyboardInterrupt:
            print()
            print()
            print("🤖 Assistant: Au revoir et merci de votre visite ! 🙏")
            print("              Bonne continuation dans vos démarches universitaires !")
            print()
            break
        except Exception as e:
            print()
            print(f" Erreur: {e}")
            print("Veuillez réessayer.")
            print()


# ==================== POINT D'ENTRÉE ====================
if __name__ == "__main__":
    """
    CONFIGURATION DES CLÉS API
    
    Créez un fichier .env avec votre clé :
        GROQ_API_KEY=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
    
    Ou exportez la variable :
        export GROQ_API_KEY="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"
    """
    
    # Charger les variables d'environnement depuis .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(" Variables d'environnement chargées depuis .env")
    except ImportError:
        print("  python-dotenv non installé. Utilisez: pip install python-dotenv")
        print("   Ou définissez GROQ_API_KEY manuellement")
    
    print()
    
    # CONFIGURATION
    PDF_DIRECTORY = "./documents_uam"
    
    # Configuration pour Groq (Llama) - RECOMMANDÉ
    PROVIDER = LLMProvider.LLAMA_GROQ
    MODEL_NAME = "llama-3.3-70b-versatile"
    
    # Autres options disponibles :
    # PROVIDER = LLMProvider.CLAUDE
    # MODEL_NAME = "claude-sonnet-4-20250514"
    
    # PROVIDER = LLMProvider.OPENAI
    # MODEL_NAME = "gpt-4o"
    
    # PROVIDER = LLMProvider.LLAMA_OLLAMA
    # MODEL_NAME = "llama3.2"
    
    # PROVIDER = LLMProvider.OPENROUTER
    # MODEL_NAME = "openai/gpt-4o"  # ou "anthropic/claude-3.7-sonnet", "google/gemini-pro", etc.
    # Voir https://openrouter.ai/models pour la liste complète des modèles disponibles
    
    # Vérifier que le dossier existe
    if not os.path.exists(PDF_DIRECTORY):
        print(f" Erreur: Le dossier '{PDF_DIRECTORY}' n'existe pas.")
        print()
        print("Solutions :")
        print(f"  1. Créez le dossier : mkdir {PDF_DIRECTORY}")
        print(f"  2. Créez des documents d'exemple : python create_sample_docs.py")
        print(f"  3. Ajoutez vos propres documents PDF/TXT dans {PDF_DIRECTORY}/")
        print()
    else:
        # Vérifier s'il y a des documents
        docs_path = Path(PDF_DIRECTORY)
        doc_count = len(list(docs_path.glob("**/*.pdf"))) + len(list(docs_path.glob("**/*.txt")))
        
        if doc_count == 0:
            print(f"  Le dossier '{PDF_DIRECTORY}' est vide.")
            print()
            print("Pour créer des documents d'exemple :")
            print("  python create_sample_docs.py")
            print()
        else:
            run_chatbot(PDF_DIRECTORY, PROVIDER, MODEL_NAME)
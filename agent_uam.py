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
        provider: Provider LLM (OPENAI, CLAUDE, LLAMA_OLLAMA, LLAMA_GROQ)
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
    
    Args:
        query: La question ou le terme à rechercher dans les documents UAM
        
    Returns:
        Le contexte pertinent trouvé dans les documents
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Recherche sémantique
    docs = _vectorstore.similarity_search(query, k=4)
    
    # Combiner les documents
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    return context if context else "Aucune information trouvée pour cette requête."


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
    
    Args:
        level: Niveau d'étude (licence, master, doctorat)
        faculty: Nom de la faculté (optionnel)
        
    Returns:
        Informations sur les frais de scolarité
    """
    # Tarifs de base (à adapter selon les documents réels)
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
        result = f"{info['description']}: {info['base']:,} FCFA par an"
        if faculty:
            result += f"\nFaculté: {faculty}"
        result += "\n\nNote: Ces tarifs sont indicatifs. Veuillez contacter le service de scolarité pour les tarifs exacts."
        return result
    
    return f"Niveau '{level}' non reconnu. Niveaux disponibles: licence, master, doctorat"


@tool
def search_formations(faculty: str = "", level: str = "") -> str:
    """
    Recherche les formations disponibles selon la faculté et le niveau.
    
    Args:
        faculty: Nom de la faculté (optionnel)
        level: Niveau d'étude (licence, master, doctorat) - optionnel
        
    Returns:
        Liste des formations disponibles
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Construire la requête de recherche
    query_parts = []
    if faculty:
        query_parts.append(f"faculté {faculty}")
    if level:
        query_parts.append(f"formation {level}")
    
    query = " ".join(query_parts) if query_parts else "formations disponibles"
    
    # Recherche dans la base de connaissances
    docs = _vectorstore.similarity_search(query, k=5)
    
    if not docs:
        return f"Aucune formation trouvée pour {faculty if faculty else 'toutes les facultés'}"
    
    # Combiner les résultats
    results = []
    for doc in docs:
        results.append(doc.page_content[:500])  # Limiter la longueur
    
    return "\n\n---\n\n".join(results)


@tool
def get_faculty_info(faculty_name: str) -> str:
    """
    Obtient des informations détaillées sur une faculté spécifique.
    
    Args:
        faculty_name: Nom ou abréviation de la faculté (ex: "FAST", "Faculté des Sciences")
        
    Returns:
        Informations sur la faculté avec son nom complet et abréviation
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    
    # Vérifier d'abord dans la base de connaissances structurée
    structure_info = get_structure_info(faculty_name)
    
    result_parts = []
    
    if structure_info:
        result_parts.append(f" {structure_info['nom_complet']} ({structure_info['abreviation']})")
        result_parts.append(f"Type: {structure_info['type'].capitalize()}")
        result_parts.append("")
    
    # Recherche dans la base de connaissances vectorielle
    search_query = structure_info['nom_complet'] if structure_info else f"faculté {faculty_name}"
    docs = _vectorstore.similarity_search(search_query, k=3)
    
    if docs:
        result_parts.append("Informations détaillées:")
        for doc in docs:
            result_parts.append(doc.page_content[:800])
            result_parts.append("---")
    elif not structure_info:
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


def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    return [
        search_uam_knowledge,
        check_question_relevance,
        calculate_fees,
        search_formations,
        get_faculty_info,
        get_structure_by_abbreviation,
        list_all_structures,
        save_user_preference,
        get_user_preferences
    ]


# ==================== NŒUDS DU GRAPHE ====================

def route_question(state: AgentState) -> Literal["agent", "reject_query"]:
    """
    Route la question selon sa pertinence.
    Version améliorée : pour les questions pertinentes, utilise le pattern agent avec outils automatiques.
    """
    # Utiliser le dernier message
    if not state["messages"]:
        return "reject_query"
    
    last_message = state["messages"][-1]
    question = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # Vérifier la pertinence avec l'outil
    relevance = check_question_relevance.invoke({"question": question})
    
    if "PERTINENT" in relevance:
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
    
    # Créer un prompt système pour guider le LLM
    system_prompt = """Tu es l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

CONSIGNES :
- Réponds de manière claire, précise et professionnelle
- Utilise l'outil search_uam_knowledge pour rechercher des informations dans la base de connaissances UAM
- Base-toi UNIQUEMENT sur les informations trouvées dans la base de connaissances
- Si l'information n'est pas disponible, indique-le poliment et propose d'orienter vers le service approprié
- Structure ta réponse de manière lisible avec des paragraphes courts
- Utilise un ton accueillant et respectueux
- Mentionne les sources pertinentes (faculté, institut concerné) quand c'est disponible
- Pour les démarches administratives, sois très précis sur les étapes et documents requis

IMPORTANT : Utilise toujours l'outil search_uam_knowledge avant de répondre aux questions sur l'UAM pour obtenir les informations les plus récentes et précises."""
    
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
    
    # Créer le prompt avec le contexte
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Tu es l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

CONSIGNES :
- Réponds de manière claire, précise et professionnelle
- Base-toi UNIQUEMENT sur le contexte fourni ci-dessous
- Si l'information n'est pas dans le contexte, indique-le poliment et propose d'orienter vers le service approprié
- Structure ta réponse de manière lisible avec des paragraphes courts
- Utilise un ton accueillant et respectueux
- Mentionne les sources pertinentes (faculté, institut concerné) quand c'est disponible
- Pour les démarches administratives, sois très précis sur les étapes et documents requis

CONTEXTE DISPONIBLE :
{context}

Si le contexte ne contient pas l'information demandée, réponds quelque chose comme :
"Je n'ai pas trouvé cette information spécifique dans ma base de connaissances. Je vous recommande de contacter [service approprié] pour obtenir une réponse précise."
"""),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Générer la réponse avec le contexte
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "context": context,
        "messages": messages
    })
    
    # Retourner l'état mis à jour - Annotated[Sequence[BaseMessage], add] fusionne automatiquement
    return {
        **state,
        "response": response,
        "messages": [AIMessage(content=response)]  # Sera automatiquement ajouté à la liste existante
    }


def reject_query(state: AgentState) -> AgentState:
    """Rejette poliment les questions hors sujet"""
    response = """Je suis désolé, mais je suis spécialisé uniquement dans les questions concernant l'Université Abdou Moumouni de Niamey (UAM).

Je peux vous aider avec :
- 📋 Informations sur les facultés, écoles et instituts
- 🎓 Formations et filières disponibles
- 📝 Conditions d'admission et pièces d'inscription
- 🏢 Démarches administratives (diplômes, attestations, relevés, etc.)
- ⏰ Horaires et services
- 📞 Contacts des différents services

Avez-vous une question concernant l'UAM ?"""
    
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
    
    # Message système initial
    system_message = SystemMessage(
        content="Bonjour ! Je suis l'assistant virtuel de l'Université Abdou Moumouni de Niamey. Comment puis-je vous aider ?"
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
    
    print("🤖 Assistant: Bonjour ! Je suis l'assistant virtuel de l'Université Abdou Moumouni de Niamey.")
    print("              Comment puis-je vous aider ?")
    print()
    
    while True:
        try:
            user_input = input("👤 Vous: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', 'au revoir', 'quitter']:
                print()
                print("🤖 Assistant: Au revoir ! N'hésitez pas à revenir si vous avez d'autres questions sur l'UAM.")
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
            print(" Assistant: Au revoir ! À bientôt.")
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
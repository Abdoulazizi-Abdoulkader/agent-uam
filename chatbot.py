"""
Interface utilisateur pour le chatbot UAM
"""
import uuid
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config import LLMProvider
from llm_utils import initialize_llm
from document_loader import load_and_index_documents
from agent_graph import create_agent_graph
from typing import Optional

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



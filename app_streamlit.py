"""
Interface Streamlit moderne pour l'Agent Conversationnel UAM
Avec chat UI élégant et fonctionnalités avancées
"""

import streamlit as st
import uuid
import json
import os
from datetime import datetime
from pathlib import Path
import sys

# Charger les variables d'environnement avant les imports
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ajouter le répertoire parent au path pour importer agent_uam
sys.path.append(str(Path(__file__).parent))

from agent_uam import (
    initialize_llm, 
    LLMProvider, 
    load_and_index_documents,
    create_agent_graph,
    _user_memory,
    UserMemory
)
from multi_agents import create_multi_agent_graph
from export_utils import export_to_json, export_to_pdf

# Configuration de la page
st.set_page_config(
    page_title="Agent Conversationnel UAM",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour une interface moderne
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 20%;
    }
    .message-content {
        flex: 1;
    }
    .message-timestamp {
        font-size: 0.75rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation de la session
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.agent_initialized = False
    st.session_state.conversation_history = []

# Sidebar pour la configuration
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # Mode d'agent
    agent_mode = st.radio(
        "Mode d'agent",
        ["Agent Simple", "Multi-Agents (Spécialisés par faculté)"],
        index=0,
        help="Multi-Agents: Utilise des agents spécialisés pour chaque faculté"
    )
    
    # Sélection du provider LLM
    provider_options = {
        "OpenRouter (Multi-modèles)": LLMProvider.OPENROUTER,
        "Groq (Llama)": LLMProvider.LLAMA_GROQ,
        "OpenAI (GPT-4o)": LLMProvider.OPENAI,
        "Claude (Anthropic)": LLMProvider.CLAUDE,
        "Ollama (Local)": LLMProvider.LLAMA_OLLAMA
    }
    
    selected_provider_name = st.selectbox(
        "Choisir le provider LLM",
        options=list(provider_options.keys()),
        index=0  # OpenRouter est maintenant le premier (par défaut)
    )
    selected_provider = provider_options[selected_provider_name]
    
    # Sélection du modèle selon le provider
    model_name = ""
    
    if selected_provider == LLMProvider.OPENROUTER:
        st.markdown("#### 🤖 Modèles OpenRouter disponibles")
        
        # Sélecteur de modèles prédéfinis pour OpenRouter
        openrouter_models = {
            "GPT-4o (OpenAI)": {
                "id": "openai/gpt-4o",
                "description": "Modèle le plus performant d'OpenAI, excellent pour tous les cas d'usage"
            },
            "Claude Sonnet 3.7 (Anthropic)": {
                "id": "anthropic/claude-3.7-sonnet",
                "description": "Modèle avancé d'Anthropic, excellent pour le raisonnement complexe"
            },
            "Gemini Pro (Google)": {
                "id": "google/gemini-pro",
                "description": "Modèle performant de Google, bon rapport qualité/prix"
            },
            "Llama 3.1 70B (Meta)": {
                "id": "meta-llama/llama-3.1-70b-instruct",
                "description": "Modèle open-source performant de Meta, très rapide"
            }
        }
        
        # Afficher les modèles avec leurs descriptions
        model_options = list(openrouter_models.keys())
        selected_model_name = st.selectbox(
            "Choisir le modèle OpenRouter",
            options=model_options,
            index=0,
            help="Sélectionnez un modèle parmi les options disponibles. Voir https://openrouter.ai/models pour plus de modèles."
        )
        
        # Afficher la description du modèle sélectionné
        if selected_model_name in openrouter_models:
            st.info(f"ℹ️ {openrouter_models[selected_model_name]['description']}")
        
        model_name = openrouter_models[selected_model_name]["id"]
        
        # Option pour entrer un modèle personnalisé
        st.caption("💡 Vous pouvez aussi entrer un modèle personnalisé ci-dessous")
        custom_model = st.text_input(
            "Modèle personnalisé (optionnel)",
            value="",
            help="Format: 'provider/model-name' (ex: 'mistralai/mistral-large'). Laissez vide pour utiliser le modèle sélectionné ci-dessus."
        )
        
        # Utiliser le modèle personnalisé s'il est fourni, sinon utiliser le modèle sélectionné
        if custom_model.strip():
            model_name = custom_model.strip()
    else:
        # Pour les autres providers, utiliser un champ texte
        default_model = ""
        if selected_provider == LLMProvider.LLAMA_GROQ:
            default_model = "llama-3.3-70b-versatile"
        elif selected_provider == LLMProvider.OPENAI:
            default_model = "gpt-4o"
        elif selected_provider == LLMProvider.CLAUDE:
            default_model = "claude-sonnet-4-20250514"
        elif selected_provider == LLMProvider.LLAMA_OLLAMA:
            default_model = "llama3.2"
        
        model_name = st.text_input(
            "Nom du modèle (optionnel)",
            value=default_model,
            help="Laissez vide pour utiliser le modèle par défaut du provider."
        )
    
    # Bouton d'initialisation
    if st.button("🚀 Initialiser l'Agent", type="primary"):
        with st.spinner("Initialisation de l'agent..."):
            try:
                # Charger les documents
                pdf_directory = "./documents_uam"
                vectorstore = load_and_index_documents(pdf_directory, selected_provider)
                
                # Initialiser le LLM
                # Pour OpenRouter, on doit toujours avoir un modèle
                final_model_name = model_name if model_name else None
                if selected_provider == LLMProvider.OPENROUTER and not final_model_name:
                    final_model_name = "openai/gpt-4o"  # Modèle par défaut pour OpenRouter
                
                llm = initialize_llm(selected_provider, final_model_name)
                
                # Créer le graphe selon le mode
                if agent_mode == "Multi-Agents (Spécialisés par faculté)":
                    agent = create_multi_agent_graph(vectorstore, llm)
                    st.session_state.agent_mode = "multi"
                else:
                    agent = create_agent_graph(vectorstore, llm)
                    st.session_state.agent_mode = "simple"
                
                st.session_state.agent = agent
                st.session_state.agent_initialized = True
                st.session_state.vectorstore = vectorstore
                st.session_state.llm = llm
                
                st.success("✅ Agent initialisé avec succès!")
            except Exception as e:
                st.error(f"❌ Erreur lors de l'initialisation: {e}")
    
    st.divider()
    
    # Section préférences utilisateur
    st.subheader("👤 Préférences")
    user_prefs = _user_memory.get_user_preferences(st.session_state.user_id)
    
    if user_prefs:
        st.json(user_prefs)
    else:
        st.info("Aucune préférence sauvegardée")
    
    st.divider()
    
    # Section export
    st.subheader("📄 Export")
    
    if st.button("📥 Exporter en JSON"):
        export_data = {
            "user_id": st.session_state.user_id,
            "export_date": datetime.now().isoformat(),
            "conversations": st.session_state.conversation_history,
            "preferences": user_prefs
        }
        st.download_button(
            label="Télécharger JSON",
            data=json.dumps(export_data, ensure_ascii=False, indent=2),
            file_name=f"uam_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    if st.button("📄 Exporter en PDF"):
        try:
            if st.session_state.conversation_history:
                pdf_path = export_to_pdf(
                    st.session_state.conversation_history,
                    st.session_state.user_id,
                    user_prefs
                )
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="Télécharger PDF",
                        data=pdf_file.read(),
                        file_name=f"uam_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("Aucune conversation à exporter")
        except Exception as e:
            st.error(f"Erreur lors de l'export PDF: {e}")
            st.info("Assurez-vous que reportlab est installé: pip install reportlab")

# Header principal
st.markdown('<div class="main-header">🎓 Agent Conversationnel UAM</div>', unsafe_allow_html=True)
st.markdown("### Université Abdou Moumouni de Niamey")

# Zone de chat
chat_container = st.container()

# Afficher l'historique des messages
with chat_container:
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")
        
        if role == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <div class="message-content">
                    <strong>👤 Vous:</strong><br>
                    {content}
                    <div class="message-timestamp">{timestamp}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <div class="message-content">
                    <strong>🤖 Assistant:</strong><br>
                    {content}
                    <div class="message-timestamp">{timestamp}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# Zone de saisie
if not st.session_state.agent_initialized:
    st.warning("⚠️ Veuillez initialiser l'agent dans la sidebar avant de commencer la conversation.")
else:
    # Formulaire de saisie
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Posez votre question sur l'UAM:",
            placeholder="Ex: Quelles sont les filières disponibles à la Faculté des Sciences ?",
            key="user_input"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            submit_button = st.form_submit_button("Envoyer 📤", type="primary")
        
        with col2:
            clear_button = st.form_submit_button("Effacer l'historique 🗑️")
    
    if clear_button:
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.rerun()
    
    if submit_button and user_input:
        # Ajouter le message utilisateur
        user_message = {
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages.append(user_message)
        st.session_state.conversation_history.append({
            "question": user_input,
            "response": "",
            "timestamp": datetime.now().isoformat()
        })
        
        # Générer la réponse
        with st.spinner("🤔 L'agent réfléchit..."):
            try:
                config = {"configurable": {"thread_id": st.session_state.user_id}}
                
                # Créer l'état initial
                from langchain_core.messages import HumanMessage
                current_state = {
                    "messages": [HumanMessage(content=user_input)],
                    "question": user_input,
                    "is_relevant": False,
                    "context": "",
                    "response": "",
                    "need_clarification": False,
                    "user_id": st.session_state.user_id,
                    "user_preferences": user_prefs
                }
                
                # Exécuter l'agent selon le mode
                if st.session_state.get("agent_mode") == "multi":
                    # Pour multi-agents, utiliser MultiAgentState
                    from multi_agents import MultiAgentState
                    from langchain_core.messages import HumanMessage
                    multi_state = {
                        "messages": [HumanMessage(content=user_input)],
                        "question": user_input,
                        "faculty": "",
                        "context": "",
                        "response": "",
                        "agent_used": ""
                    }
                    result = st.session_state.agent.invoke(multi_state, config)
                else:
                    # Agent simple
                    result = st.session_state.agent.invoke(current_state, config)
                
                # Extraire la réponse
                response_text = ""
                if result.get("response"):
                    response_text = result["response"]
                else:
                    # Chercher dans les messages
                    for msg in reversed(result.get("messages", [])):
                        if hasattr(msg, 'content') and msg.content:
                            response_text = msg.content
                            break
                
                # Ajouter la réponse
                assistant_message = {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.messages.append(assistant_message)
                
                # Mettre à jour l'historique
                if st.session_state.conversation_history:
                    st.session_state.conversation_history[-1]["response"] = response_text
                
                # Sauvegarder dans la mémoire
                _user_memory.add_conversation(
                    st.session_state.user_id,
                    user_input,
                    response_text
                )
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erreur: {e}")
                error_message = {
                    "role": "assistant",
                    "content": f"Désolé, une erreur s'est produite: {e}",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.messages.append(error_message)
                st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Agent Conversationnel UAM - Basé sur LangChain v1.0+ et LangGraph v1.0+ (2025)"
    "</div>",
    unsafe_allow_html=True
)


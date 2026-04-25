"""
Nœuds du graphe LangGraph pour l'agent conversationnel UAM
"""
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Literal
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable
from uam_structures import UAM_STRUCTURES, detect_structure_in_text
from tools import (
    detect_greeting,
    check_question_relevance,
    search_uam_knowledge,
    detect_user_profile,
    detect_frustration_or_confusion,
)
from agent_state import AgentState
from logger_config import get_logger
from utils import validate_question, format_error_message
from app_config import get_config
from prompts import build_tool_system_prompt, build_context_system_prompt

# Logger pour ce module
logger = get_logger(__name__)

# ==================== NŒUDS DU GRAPHE ====================

@traceable
def route_and_store(state: AgentState) -> AgentState:
    """
    Nœud de routage : analyse le message, stocke la destination dans routing_hint
    et le sous-type dans routing_context pour éviter toute re-détection en aval.
    """
    def _result(hint: str, context: str = "") -> AgentState:
        return {**state, "routing_hint": hint, "routing_context": context}

    try:
        if not state["messages"]:
            logger.warning("Aucun message dans l'état pour le routage")
            return _result("reject_query")

        last_message = state["messages"][-1]
        question = last_message.content if hasattr(last_message, "content") else str(last_message)
        if not isinstance(question, str):
            question = str(question)

        # Validation avec effet réel : rejeter si question vide / invalide
        is_valid, error_msg = validate_question(question)
        if not is_valid:
            logger.warning(f"Question invalide rejetée: {error_msg}")
            return _result("reject_query")

        question_stripped = question.strip().upper()
        logger.debug(f"Routage de la question: {question[:100]}...")

        # ── 1. Abréviations de structures (ex: "FA", "FAST", "ENS") ──────────
        all_abbreviations = []
        for category in ["facultes", "instituts", "ecoles"]:
            all_abbreviations.extend(UAM_STRUCTURES[category].keys())
        if question_stripped in all_abbreviations:
            logger.debug("Abréviation de structure → agent")
            return _result("agent")

        # ── 2. Nature conversationnelle ────────────────────────────────────────
        greeting_type = detect_greeting.invoke({"message": question})

        if greeting_type == "FAREWELL":
            logger.debug("Fin de conversation → handle_special_case")
            return _result("handle_special_case", "FAREWELL")

        if greeting_type == "THANKS":
            logger.debug("Remerciement → handle_special_case")
            return _result("handle_special_case", "THANKS")

        if greeting_type == "GREETING":
            logger.debug("Salutation simple → agent")
            return _result("agent")

        # ── 3. Frustration / confusion ─────────────────────────────────────────
        sentiment = detect_frustration_or_confusion.invoke({"message": question})
        if sentiment in ("FRUSTRATION", "CONFUSION", "REPETITION"):
            logger.debug(f"Sentiment ({sentiment}) → handle_special_case")
            return _result("handle_special_case", sentiment)

        # ── 4. Profil utilisateur spécial ──────────────────────────────────────
        profile = detect_user_profile.invoke({"message": question})
        if profile in ("CANDIDAT_MASTER", "CANDIDAT_DOCTORAT", "ETUDIANT_ETRANGER"):
            logger.debug(f"Profil spécial ({profile}) → agent")
            return _result("agent")

        # ── 5. Pertinence UAM ───────────────────────────────────────────────────
        relevance = check_question_relevance.invoke({"question": question})
        if relevance == "PERTINENT" or greeting_type == "BOTH":
            logger.debug("Question pertinente → agent")
            return _result("agent")

        logger.debug("Question hors sujet → reject_query")
        return _result("reject_query")

    except Exception as e:
        logger.error(f"Erreur lors du routage: {e}", exc_info=True)
        return _result("agent")


@traceable
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


@traceable
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Détermine si l'agent doit appeler des outils ou terminer la conversation.
    Utilise le pattern recommandé de LangGraph 1.0.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    config = get_config()
    tool_iterations = state.get("tool_iterations", 0)
    if tool_iterations >= config.max_tool_iterations:
        logger.warning("Limite d'appels d'outils atteinte, arrêt du cycle.")
        return "end"

    # Si le dernier message contient des appels d'outils, exécuter les outils
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    # Sinon, terminer
    return "end"


@traceable(run_type="llm")
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
        structures_info = [
            f"- {s['nom_complet']} ({s['abreviation']}) - {s['type'].capitalize()}"
            for s in detected_structures
        ]
        structures_context = "\n\nSTRUCTURES DÉTECTÉES DANS LA QUESTION :\n" + "\n".join(structures_info)

    # Détecter le profil utilisateur pour adapter le prompt
    profile = detect_user_profile.invoke({"message": question})
    profile_context = ""
    profile_hints = {
        "CANDIDAT_MASTER": (
            "\n\nPROFIL DÉTECTÉ : Candidat souhaitant intégrer un Master à l'UAM (venant d'un autre établissement).\n"
            "→ Utilise search_external_student_master pour les conditions d'admission spécifiques.\n"
            "→ Utilise search_required_documents pour le dossier à fournir.\n"
            "→ Utilise search_international_equivalence si le candidat vient de l'étranger."
        ),
        "CANDIDAT_DOCTORAT": (
            "\n\nPROFIL DÉTECTÉ : Candidat souhaitant faire une thèse / doctorat à l'UAM.\n"
            "→ Utilise search_phd_admission pour les conditions d'admission en doctorat.\n"
            "→ Utilise search_master_thesis_supervision pour trouver un directeur de thèse.\n"
            "→ Mentionne les trois écoles doctorales (ED-SVT, ED-LASHS, ED-SET)."
        ),
        "ETUDIANT_ETRANGER": (
            "\n\nPROFIL DÉTECTÉ : Étudiant étranger (hors Niger) souhaitant étudier à l'UAM.\n"
            "→ Utilise search_foreign_student_procedures pour les démarches spécifiques.\n"
            "→ Utilise search_international_equivalence pour la reconnaissance du diplôme.\n"
            "→ Utilise search_housing_and_services pour le logement."
        ),
        "ETUDIANT_EXTERNE": (
            "\n\nPROFIL DÉTECTÉ : Étudiant venant d'une autre université nigérienne.\n"
            "→ Utilise search_transfer_equivalence pour le transfert/équivalence de crédits.\n"
            "→ Utilise search_admission_requirements pour les conditions d'accès."
        ),
        "BACHELIER": (
            "\n\nPROFIL DÉTECTÉ : Nouveau bachelier souhaitant s'inscrire à l'UAM.\n"
            "→ Utilise search_formations pour les filières disponibles.\n"
            "→ Utilise search_required_documents pour les pièces d'inscription.\n"
            "→ Utilise generate_registration_checklist avec profile='nouveau'."
        ),
        "PROFESSIONNEL": (
            "\n\nPROFIL DÉTECTÉ : Professionnel souhaitant reprendre des études (VAE/VAP).\n"
            "→ Utilise search_recognition_prior_learning pour la validation des acquis.\n"
            "→ Adapte la réponse à la formation continue."
        ),
        "PARENT": (
            "\n\nPROFIL DÉTECTÉ : Parent s'informant pour son enfant.\n"
            "→ Fournis des informations claires et rassurantes.\n"
            "→ Oriente vers les contacts officiels pour les démarches formelles."
        ),
    }
    profile_context = profile_hints.get(profile, "")

    system_prompt = build_tool_system_prompt(structures_context + profile_context)
    
    # Ajouter le prompt système au début des messages s'il n'y en a pas déjà
    if not messages or not isinstance(messages[0], SystemMessage):
        messages_with_system = [SystemMessage(content=system_prompt)] + list(messages)
    else:
        messages_with_system = messages
    
    # Appeler le LLM avec les outils bindés
    response = llm_with_tools.invoke(messages_with_system)
    
    return {
        **state,
        "is_relevant": True,
        "messages": [response]
    }


@traceable(run_type="llm")
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
        ("system", build_context_system_prompt(context, structures_info)),
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


@traceable
def handle_special_case(state: AgentState) -> AgentState:
    """
    Gère les cas conversationnels exceptionnels sans LLM.
    Lit routing_context (stocké par route_and_store) pour éviter tout appel d'outil redondant.
    """
    routing_context = state.get("routing_context", "")

    if routing_context == "FAREWELL":
        response = (
            "Merci pour votre visite ! C'était un plaisir de vous accompagner.\n\n"
            "N'hésitez pas à revenir si vous avez d'autres questions sur l'UAM. "
            "Bonne continuation et à bientôt !"
        )

    elif routing_context == "THANKS":
        response = (
            "Avec plaisir ! Je suis toujours disponible pour vous aider.\n\n"
            "Si vous avez d'autres questions sur l'UAM — formations, inscription, "
            "procédures ou services — n'hésitez pas à me les poser."
        )

    elif routing_context == "FRUSTRATION":
        response = (
            "Je suis sincèrement désolé si mes réponses ne vous ont pas satisfait. "
            "Je comprends votre frustration et je vais faire de mon mieux pour mieux vous aider.\n\n"
            "Pourriez-vous reformuler votre question de façon plus précise ? "
            "Par exemple, en précisant :\n"
            "• La faculté ou la filière concernée\n"
            "• Votre situation (nouvel étudiant, réinscription, étudiant externe…)\n"
            "• Ce que vous cherchez exactement\n\n"
            "Si le problème persiste, je vous recommande de contacter directement "
            "le service de scolarité de la faculté concernée pour une réponse officielle."
        )

    elif routing_context == "CONFUSION":
        response = (
            "Je comprends, permettez-moi de clarifier les choses.\n\n"
            "Je suis l'assistant virtuel de l'UAM, spécialisé dans :\n"
            "• Les informations sur les formations et filières\n"
            "• Les procédures d'inscription et d'admission\n"
            "• Les démarches administratives\n"
            "• Les services aux étudiants\n\n"
            "Pourriez-vous me poser votre question de manière plus précise ? "
            "Je ferai de mon mieux pour vous apporter une réponse claire."
        )

    elif routing_context == "REPETITION":
        response = (
            "Je vois que vous avez déjà posé cette question. Laissez-moi essayer "
            "de vous apporter une réponse plus complète ou sous un angle différent.\n\n"
            "Pourriez-vous préciser ce qui n'était pas clair dans ma précédente réponse ? "
            "Cela m'aidera à mieux cibler l'information dont vous avez besoin."
        )

    else:
        # Ne devrait pas arriver en flux normal — fallback sans appel LLM
        logger.warning(f"handle_special_case: routing_context inattendu '{routing_context}'")
        response = (
            "Je suis là pour vous aider. Pouvez-vous préciser votre demande "
            "concernant l'Université Abdou Moumouni de Niamey ?"
        )

    return {
        **state,
        "response": response,
        "is_relevant": True,
        "messages": [AIMessage(content=response)],
    }


@traceable
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



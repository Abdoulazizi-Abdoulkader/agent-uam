"""
Nœuds du graphe LangGraph pour l'agent conversationnel UAM
"""
from typing import Literal
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from uam_structures import UAM_STRUCTURES, detect_structure_in_text
from tools import detect_greeting, check_question_relevance, search_uam_knowledge
from agent_state import AgentState

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



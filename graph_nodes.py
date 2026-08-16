"""
Nœuds du graphe LangGraph pour l'agent conversationnel UAM
"""
import logging
from langchain_core.messages import AIMessage, SystemMessage
from typing import Literal
from langsmith import traceable
from uam_structures import UAM_STRUCTURES, detect_structure_in_text
from tools import (
    detect_greeting,
    check_question_relevance,
    detect_user_profile,
    detect_frustration_or_confusion,
)
from agent_state import AgentState
from logger_config import get_logger
from utils import validate_question
from app_config import get_config
from prompts import build_tool_system_prompt

# Logger pour ce module
logger = get_logger(__name__)

# ── Données statiques profils (hors call_model pour lisibilité et testabilité) ─

_PROFILE_HINTS: dict[str, str] = {
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

_LENGTH_HINTS: dict[str, str] = {
    "BACHELIER":         "\n\nLONGUEUR CIBLE : 80-120 mots. Utilise des listes à puces pour les étapes.",
    "PARENT":            "\n\nLONGUEUR CIBLE : 60-90 mots. Sois rassurant et concis.",
    "ETUDIANT_UAM":      "\n\nLONGUEUR CIBLE : 60-100 mots. Va droit au but.",
    "CANDIDAT_MASTER":   "\n\nLONGUEUR CIBLE : 100-150 mots. Liste les conditions et pièces requises.",
    "CANDIDAT_DOCTORAT": "\n\nLONGUEUR CIBLE : 100-150 mots. Mentionne les 3 écoles doctorales si pertinent.",
    "ETUDIANT_ETRANGER": "\n\nLONGUEUR CIBLE : 100-150 mots. Inclus les étapes administratives clés.",
    "PROFESSIONNEL":     "\n\nLONGUEUR CIBLE : 80-120 mots. Précise la procédure VAE/VAP applicable.",
}

# 12 messages ≈ 6 échanges question/réponse : assez pour les questions de suivi
# (« et pour le Master ? ») une fois les résultats d'outils purgés par _compress_history.
_MAX_HISTORY = 12


# ── Fonctions privées de construction du contexte ─────────────────────────────

def _build_structures_context(question: str) -> str:
    """Détecte les structures UAM dans la question et retourne un bloc de contexte."""
    detected = detect_structure_in_text(question)
    if not detected:
        return ""
    lines = [f"- {s['nom_complet']} ({s['abreviation']}) - {s['type'].capitalize()}"
             for s in detected]
    return "\n\nSTRUCTURES DÉTECTÉES DANS LA QUESTION :\n" + "\n".join(lines)


def _build_profile_context(profile: str) -> str:
    """Retourne le bloc de contexte profil + hint de longueur pour le prompt système."""
    return _PROFILE_HINTS.get(profile, "") + _LENGTH_HINTS.get(profile, "")


def _compress_history(messages: list, max_size: int = _MAX_HISTORY) -> list:
    """Allège l'historique envoyé au LLM avant de le tronquer.

    Les résultats d'outils ne servent qu'au tour qui les a produits : une fois la
    réponse rédigée, l'information utile s'y trouve déjà. Les conserver ferait payer
    le même contexte à chaque question — un seul résultat de recherche documentaire
    pèse ~1 500 tokens, et l'état LangGraph les accumule indéfiniment.

    On ne purge donc que les **tours passés** : tout ce qui suit le dernier message
    utilisateur est laissé intact, car pendant la boucle ReAct le LLM doit voir les
    résultats des outils qu'il vient d'appeler.

    Les ToolMessage et les AIMessage porteurs de tool_calls sont retirés **ensemble** :
    l'API attend qu'un message d'assistant annonçant des appels d'outils soit suivi de
    leurs résultats, retirer les uns sans les autres provoquerait une erreur 400.
    """
    from langchain_core.messages import HumanMessage, ToolMessage

    # Début du tour courant = dernier message utilisateur
    debut_tour = 0
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            debut_tour = i
            break

    passe, tour_courant = messages[:debut_tour], messages[debut_tour:]

    allege = [
        m for m in passe
        if not isinstance(m, ToolMessage) and not getattr(m, "tool_calls", None)
    ]
    retires = len(passe) - len(allege)
    if retires:
        logger.debug(f"Historique allégé : {retires} messages d'outils retirés des tours passés")

    historique = allege + tour_courant

    if len(historique) > max_size:
        logger.info(f"Troncature de l'historique : {len(historique)} → {max_size} messages")
        # On tronque par la gauche sans jamais entamer le tour courant
        garde = max(max_size - len(tour_courant), 0)
        historique = allege[-garde:] + tour_courant if garde else tour_courant

    return historique


# Conservé pour compatibilité : evaluate.py et les tests importent encore ce nom.
def _truncate_history(messages: list, max_size: int = _MAX_HISTORY) -> list:
    """Alias historique de `_compress_history`."""
    return _compress_history(messages, max_size)


# ==================== NŒUDS DU GRAPHE ====================

@traceable
def route_and_store(state: AgentState) -> AgentState:
    """
    Nœud de routage : analyse le message, stocke la destination dans routing_hint
    et le sous-type dans routing_context pour éviter toute re-détection en aval.
    """
    def _result(hint: str, context: str = "", profile: str = "") -> AgentState:
        # Ne renvoyer QUE les champs modifiés. Réexpédier `messages` (via {**state})
        # le ferait repasser dans le réducteur `add` d'AgentState, qui concatène :
        # l'historique doublerait à chaque question (1 → 2 → 4 → … → 83 608 messages
        # observés en session réelle). LangGraph fusionne le reste de l'état seul.
        return {"routing_hint": hint, "routing_context": context, "user_profile": profile}

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
            logger.debug("Abréviation de structure → réponse directe (sans LLM)")
            return _result("handle_special_case", f"DIRECT_STRUCTURE:{question_stripped}")

        # ── 2. Nature conversationnelle ────────────────────────────────────────
        # NB : on appelle .func (la fonction regex pure sous-jacente) plutôt que
        # .invoke() pour éviter ~2 ms de surcoût LangChain (validation Pydantic +
        # span LangSmith) par appel — non négligeable sur ce chemin de routage
        # exécuté à chaque message. Ces détecteurs restent exposés au LLM via get_tools().
        greeting_type = detect_greeting.func(message=question)

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
        sentiment = detect_frustration_or_confusion.func(message=question)
        if sentiment in ("FRUSTRATION", "CONFUSION", "REPETITION"):
            logger.debug(f"Sentiment ({sentiment}) → handle_special_case")
            return _result("handle_special_case", sentiment)

        # ── 4. Profil utilisateur spécial ──────────────────────────────────────
        profile = detect_user_profile.func(message=question)
        if profile in ("CANDIDAT_MASTER", "CANDIDAT_DOCTORAT", "ETUDIANT_ETRANGER"):
            relevance = check_question_relevance.func(question=question)
            if relevance == "HORS_SUJET":
                logger.debug(f"Profil ({profile}) mais question hors UAM → reject_query")
                return _result("reject_query", profile=profile)
            logger.debug(f"Profil spécial ({profile}) + pertinence UAM confirmée → agent")
            return _result("agent", profile=profile)

        # ── 5. Pertinence UAM ───────────────────────────────────────────────────
        relevance = check_question_relevance.func(question=question)
        if relevance == "PERTINENT" or greeting_type == "BOTH":
            logger.debug("Question pertinente → agent")
            return _result("agent", profile=profile)

        logger.debug("Question hors sujet → reject_query")
        return _result("reject_query", profile=profile)

    except Exception as e:
        logger.error(f"Erreur lors du routage: {e}", exc_info=True)
        return _result("reject_query")




@traceable
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Détermine si l'agent doit appeler des outils ou terminer la conversation.

    Court-circuits :
    - Limite globale max_tool_iterations
    - Profils simples (BACHELIER, PARENT) : seuil réduit à 2 itérations
    - Saturation de contexte : ≥ 2 itérations ET ≥ 2500 chars d'outils
    """
    from langchain_core.messages import ToolMessage

    messages = state["messages"]
    last_message = messages[-1]

    config = get_config()
    tool_iterations = state.get("tool_iterations", 0)
    if tool_iterations >= config.max_tool_iterations:
        logger.warning("Limite d'appels d'outils atteinte, arrêt du cycle.")
        return "end"

    # Profils ne nécessitant jamais plus de 2 appels d'outils
    _SIMPLE_PROFILES = {"BACHELIER", "PARENT", "ETUDIANT_UAM"}
    profile = state.get("user_profile", "")
    max_iter_for_profile = 2 if profile in _SIMPLE_PROFILES else config.max_tool_iterations
    if tool_iterations >= max_iter_for_profile:
        logger.info(f"Court-circuit profil {profile} : {tool_iterations} itérations → end")
        return "end"

    # Court-circuit sur saturation de contexte (≥ 2 itérations + ≥ 2500 chars)
    if tool_iterations >= 2:
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        total_chars = sum(len(getattr(m, "content", "") or "") for m in tool_messages)
        if total_chars >= 2500:
            logger.info(
                f"Court-circuit ReAct : {tool_iterations} itérations, "
                f"{total_chars} car. de contexte → end"
            )
            return "end"

    # Si le dernier message contient des appels d'outils, exécuter les outils
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


@traceable(run_type="llm")
def call_model(state: AgentState, llm_with_tools) -> AgentState:
    """Appelle le LLM avec les outils bindés pour générer une réponse ou appeler des outils."""
    from langchain_core.messages import AIMessage as _AIMessage
    messages = state["messages"]

    last_message = messages[-1] if messages else None
    question = last_message.content if (last_message and hasattr(last_message, "content")) else ""
    if not isinstance(question, str):
        question = str(question)

    profile = state.get("user_profile", "INCONNU")
    structures_context = _build_structures_context(question)
    profile_context    = _build_profile_context(profile)
    system_prompt      = build_tool_system_prompt(structures_context + profile_context)

    # Détection de structures déjà effectuée par _build_structures_context ci-dessus :
    # on ne la relance que si le niveau DEBUG est réellement actif.
    if logger.isEnabledFor(logging.DEBUG):
        detected = detect_structure_in_text(question)
        logger.debug(
            f"call_model — profil: {profile} "
            f"| structures: {[s['abreviation'] for s in detected]} "
            f"| prompt système: {len(system_prompt)} chars"
        )

    history = _compress_history(list(messages))
    messages_with_system = [SystemMessage(content=system_prompt)] + history

    try:
        config = get_config()
        response = llm_with_tools.invoke(
            messages_with_system,
            config={"timeout": config.llm.timeout},
        )
    except Exception as e:
        logger.error(f"call_model — erreur LLM ({type(e).__name__}): {e}", exc_info=True)
        fallback = (
            "Je rencontre une difficulté technique momentanée. "
            "Veuillez réessayer dans quelques instants. "
            "Si le problème persiste, contactez le service de scolarité de l'UAM directement."
        )
        response = _AIMessage(content=fallback)

    # Champs modifiés uniquement — voir la note dans route_and_store._result
    return {"is_relevant": True, "messages": [response]}




@traceable
def handle_special_case(state: AgentState) -> AgentState:
    """
    Gère les cas conversationnels exceptionnels sans LLM.
    Lit routing_context (stocké par route_and_store) pour éviter tout appel d'outil redondant.
    """
    routing_context = state.get("routing_context", "")

    if routing_context.startswith("DIRECT_STRUCTURE:"):
        abbrev = routing_context.split(":", 1)[1]
        # Recherche directe par clé pour éviter le bug de sous-chaîne de get_structure_info
        raw = None
        struct_type = None
        for cat in ("facultes", "instituts", "ecoles"):
            if abbrev in UAM_STRUCTURES[cat]:
                raw = UAM_STRUCTURES[cat][abbrev]
                struct_type = cat[:-1]
                break
        info = {**raw, "abreviation": abbrev, "type": struct_type} if raw else None
        if info:
            type_label = {"faculte": "Faculté", "institut": "Institut", "ecole": "École"}.get(
                info.get("type", ""), "Structure"
            )
            lines = [
                f"Bonjour ! Voici les informations sur **{info['nom_complet']}** ({info['abreviation']}) :\n",
                f"**Type :** {type_label}",
            ]
            if info.get("missions"):
                lines.append(f"\n**Mission :** {info['missions']}")
            if info.get("localisation"):
                lines.append(f"\n**Localisation :** {info['localisation']}")
            if info.get("historique"):
                lines.append(f"\n**Historique :** {info['historique']}")
            lines.append("\nN'hésitez pas à me poser d'autres questions sur l'UAM !")
            response = "\n".join(lines)
        else:
            response = (
                f"Désolé, je n'ai pas trouvé d'informations sur la structure « {abbrev} ».\n"
                "Veuillez vérifier l'abréviation ou contacter la scolarité de l'UAM."
            )
        return {"response": response, "is_relevant": True, "messages": [AIMessage(content=response)]}

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
        "response": response,
        "is_relevant": True,
        "messages": [AIMessage(content=response)],
    }


@traceable
def reject_query(state: AgentState) -> AgentState:
    """Rejette poliment les questions hors sujet.

    Les messages de type GREETING sont routés vers 'agent' par route_and_store,
    donc cette fonction ne reçoit que des questions non pertinentes pour l'UAM.
    """
    response = (
        "Je suis désolé, mais je suis spécialisé uniquement dans les questions "
        "concernant l'Université Abdou Moumouni de Niamey (UAM).\n\n"
        "Je peux vous aider avec :\n"
        "- 📋 Informations sur les facultés, écoles et instituts\n"
        "- 🎓 Formations et filières disponibles\n"
        "- 📝 Conditions d'admission et pièces d'inscription\n"
        "- 🏢 Démarches administratives (diplômes, attestations, relevés, etc.)\n"
        "- ⏰ Horaires et services\n"
        "- 📞 Contacts des différents services\n\n"
        "Avez-vous une question concernant l'UAM ? Je serai ravi de vous aider !"
    )
    return {
        "response": response,
        "is_relevant": False,
        "messages": [AIMessage(content=response)],
    }



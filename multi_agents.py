from typing import Annotated, TypedDict, Sequence
from operator import add
from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent_uam import (
    search_uam_knowledge,
    set_vectorstore,
    UAM_STRUCTURES,
    detect_structure_in_text
)


# Facultés disponibles (utilise maintenant la base de connaissances structurée)
def get_faculties_dict():
    """Retourne un dictionnaire des facultés depuis UAM_STRUCTURES"""
    return {
        abbrev: info["nom_complet"]
        for abbrev, info in UAM_STRUCTURES["facultes"].items()
    }


def get_all_structures_dict():
    """Retourne un dictionnaire de toutes les structures (facultés, écoles, instituts)"""
    all_structures = {}

    # Ajouter les facultés
    for abbrev, info in UAM_STRUCTURES["facultes"].items():
        all_structures[abbrev] = info["nom_complet"]

    # Ajouter les écoles
    for abbrev, info in UAM_STRUCTURES["ecoles"].items():
        all_structures[abbrev] = info["nom_complet"]

    # Ajouter les instituts
    for abbrev, info in UAM_STRUCTURES["instituts"].items():
        all_structures[abbrev] = info["nom_complet"]

    return all_structures


def get_agent_name(abbreviation: str) -> str:
    """Convertit une abréviation en nom d'agent (ex: 'FAST' -> 'fast_agent', 'ED-SVT' -> 'ed_svt_agent')"""
    return f"{abbreviation.lower().replace('-', '_')}_agent"


def get_structure_code_from_agent_name(agent_name: str) -> str:
    """Convertit un nom d'agent en code de structure (ex: 'ed_svt_agent' -> 'ED-SVT', 'ens_agent' -> 'ENS')"""
    # Enlever le suffixe "_agent"
    code = agent_name.replace("_agent", "").upper()

    # Restaurer les tirets pour les codes qui en ont (ED-SVT, ED-LASHS, ED-SET)
    if code.startswith("ED_"):
        code = code.replace("_", "-")

    return code


FACULTIES = get_faculties_dict()
ALL_STRUCTURES = get_all_structures_dict()


class MultiAgentState(TypedDict):
    """État pour le système multi-agents"""
    messages: Annotated[Sequence[BaseMessage], add]
    question: str
    faculty: str  # Faculté concernée
    context: str
    response: str
    agent_used: str  # Agent qui a traité la question


def route_to_faculty_agent(state: MultiAgentState) -> str:
    """
    Route la question vers l'agent spécialisé de la structure appropriée.
    Utilise la base de connaissances structurée pour détecter les structures (facultés, écoles, instituts).
    """
    question = state["question"]
    question_lower = question.lower()

    # Détecter les structures mentionnées dans la question
    detected_structures = detect_structure_in_text(question)

    if detected_structures:
        # Utiliser la première structure détectée
        structure = detected_structures[0]
        abbrev = structure["abreviation"]

        # Générer le nom d'agent dynamiquement
        agent_name = get_agent_name(abbrev)
        state["faculty"] = abbrev
        return agent_name

    # Détection par mots-clés (fallback)
    faculty_keywords = {
        "fast_agent": ["sciences", "techniques", "mathématiques", "physique", "chimie", "biologie", "géologie", "informatique"],
        "fa_agent": ["agronomie", "agriculture", "agronome", "rural", "agroalimentaire"],
        "flsh_agent": ["lettres", "sciences humaines", "littérature", "histoire", "géographie", "philosophie"],
        "fss_agent": ["santé", "médecine", "pharmacie", "infirmier", "santé publique"],
        "fseg_agent": ["économiques", "juridiques", "économie", "gestion", "commerce"],
        "fsjp_agent": ["juridiques", "politiques", "droit", "juridique", "science politique"],
        "ens_agent": ["normale supérieure", "enseignement", "pédagogie", "formation des enseignants"],
        "ed_svt_agent": ["école doctorale svt", "sciences de la vie", "sciences de la terre", "doctorat svt"],
        "ed_lashs_agent": ["école doctorale lashs", "lettres arts sciences humaines", "doctorat lashs"],
        "ed_set_agent": ["école doctorale set", "sciences exactes techniques", "doctorat set"],
        "irsh_agent": ["institut recherche sciences humaines", "irsh"],
        "irem_agent": ["institut recherche enseignement mathématiques", "irem", "enseignement mathématiques"],
        "iri_agent": ["institut radio-isotopes", "iri", "radio-isotopes"]
    }

    for agent_name, keywords in faculty_keywords.items():
        for keyword in keywords:
            if keyword in question_lower:
                # Convertir le nom d'agent en code de structure
                structure_code = get_structure_code_from_agent_name(agent_name)
                state["faculty"] = structure_code
                return agent_name

    # Si aucune structure spécifique détectée, utiliser l'agent général
    return "general_agent"


def create_faculty_agent(structure_code: str, structure_full_name: str, llm):
    """
    Crée un agent spécialisé pour une structure (faculté, école ou institut)

    Args:
        structure_code: Code de la structure (ex: "FAST", "ENS", "IRSH")
        structure_full_name: Nom complet de la structure
        llm: LLM à utiliser
    """
    def structure_agent_node(state: MultiAgentState) -> MultiAgentState:
        """Nœud de l'agent spécialisé"""
        question = state["question"]

        # Recherche spécifique pour cette structure
        query = f"{structure_full_name} {question}"
        context = search_uam_knowledge.invoke({"query": query})

        # Créer un prompt spécialisé
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        # Déterminer le type de structure pour adapter le prompt
        structure_type = "structure"
        if structure_code in UAM_STRUCTURES["facultes"]:
            structure_type = "faculté"
        elif structure_code in UAM_STRUCTURES["ecoles"]:
            structure_type = "école"
        elif structure_code in UAM_STRUCTURES["instituts"]:
            structure_type = "institut"

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Tu es un assistant spécialisé de la {structure_full_name} ({structure_type}) de l'Université Abdou Moumouni de Niamey.

Tu es un expert dans tous les domaines liés à cette {structure_type} :
- Formations et filières (si applicable)
- Conditions d'admission (si applicable)
- Programmes d'études (si applicable)
- Activités de recherche (si applicable)
- Débouchés professionnels (si applicable)
- Informations administratives spécifiques

Réponds de manière précise et détaillée en te basant sur le contexte fourni.
Si l'information n'est pas disponible, oriente l'utilisateur vers le service approprié.

CONTEXTE DISPONIBLE :
{{context}}"""),
            MessagesPlaceholder(variable_name="messages"),
        ])

        # Générer la réponse
        from langchain_core.output_parsers import StrOutputParser
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "context": context,
            "messages": state["messages"]
        })

        return {
            **state,
            "context": context,
            "response": response,
            "agent_used": structure_code,
            "messages": [AIMessage(content=response)]
        }

    return structure_agent_node


def create_general_agent(llm):
    """Crée l'agent général pour les questions non spécifiques à une faculté"""
    def general_agent_node(state: MultiAgentState) -> MultiAgentState:
        """Nœud de l'agent général"""
        question = state["question"]

        # Recherche générale
        context = search_uam_knowledge.invoke({"query": question})

        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_core.output_parsers import StrOutputParser

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

Tu peux répondre à des questions générales sur l'université :
- Informations générales sur l'UAM
- Toutes les facultés et leurs formations
- Procédures d'inscription générales
- Services de l'université

Réponds de manière claire et précise en te basant sur le contexte fourni.

CONTEXTE DISPONIBLE :
{context}"""),
            MessagesPlaceholder(variable_name="messages"),
        ])

        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "context": context,
            "messages": state["messages"]
        })

        return {
            **state,
            "context": context,
            "response": response,
            "agent_used": "GENERAL",
            "messages": [AIMessage(content=response)]
        }

    return general_agent_node


def create_multi_agent_graph(vectorstore, llm):
    """
    Crée le graphe multi-agents avec agents spécialisés par structure
    (facultés, écoles, instituts)

    Args:
        vectorstore: Index FAISS pour la recherche
        llm: LLM principal

    Returns:
        Application LangGraph compilée
    """
    # Initialiser le vectorstore
    set_vectorstore(vectorstore)

    # Créer le graphe
    workflow = StateGraph(MultiAgentState)

    # Créer les agents spécialisés pour toutes les structures
    agent_mapping = {}  # Pour stocker le mapping agent_name -> agent_name

    # Créer les agents pour les facultés
    for faculty_code, faculty_name in UAM_STRUCTURES["facultes"].items():
        agent_name = get_agent_name(faculty_code)
        agent_node = create_faculty_agent(faculty_code, faculty_name["nom_complet"], llm)
        workflow.add_node(agent_name, agent_node)
        agent_mapping[agent_name] = agent_name

    # Créer les agents pour les écoles
    for ecole_code, ecole_info in UAM_STRUCTURES["ecoles"].items():
        agent_name = get_agent_name(ecole_code)
        agent_node = create_faculty_agent(ecole_code, ecole_info["nom_complet"], llm)
        workflow.add_node(agent_name, agent_node)
        agent_mapping[agent_name] = agent_name

    # Créer les agents pour les instituts
    for institut_code, institut_info in UAM_STRUCTURES["instituts"].items():
        agent_name = get_agent_name(institut_code)
        agent_node = create_faculty_agent(institut_code, institut_info["nom_complet"], llm)
        workflow.add_node(agent_name, agent_node)
        agent_mapping[agent_name] = agent_name

    # Créer l'agent général
    general_agent_node = create_general_agent(llm)
    workflow.add_node("general_agent", general_agent_node)
    agent_mapping["general_agent"] = "general_agent"

    # Définir le point d'entrée avec routage
    workflow.set_conditional_entry_point(
        route_to_faculty_agent,
        agent_mapping
    )

    # Tous les agents terminent à END
    for agent_name in agent_mapping.keys():
        workflow.add_edge(agent_name, END)

    # Compiler avec mémoire
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


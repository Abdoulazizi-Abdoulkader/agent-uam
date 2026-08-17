"""
Outils (Tools) pour l'agent conversationnel UAM
Tous les outils disponibles pour la recherche et l'interaction
"""
import contextvars
import json
import re
import threading
import unicodedata
from datetime import datetime
from functools import lru_cache
from langchain_core.tools import tool
from langchain_community.vectorstores import FAISS
from langsmith import traceable
from app_config import get_config
from context_tracker import push_context, push_text
try:
    import grounding_capture as _gc
    _GROUNDING_AVAILABLE = True
except ImportError:
    _GROUNDING_AVAILABLE = False
from uam_structures import (
    get_structure_info,
    detect_structure_in_text,
    UAM_STRUCTURES,
    list_all_structures_internal
)
from memory import _user_memory
from logger_config import get_logger
from utils import sanitize_input, retry_on_failure

# Logger pour ce module
logger = get_logger(__name__)

# Patterns hors-sujet compilés une seule fois au chargement du module
_OFF_TOPIC_RE = [re.compile(p) for p in [
    r"\b(m[eé]t[eé]o|temp[eé]rature|clima[t]?|pluie|vent|soleil|nuage|pr[eé]vision)\b",
    r"quel temps fait[-\s]?il",
    r"\b(po[eè]me?|chanson|musique|film|cin[eé]ma|roman|litt[eé]rature)\b",
    r"\b(pirater?|hack|mot de passe|compte facebook|instagram|r[eé]seau social)\b",
    r"\b(recette|cuisine|plat|ingr[eé]dient)\b",
    r"\b(sport|football|basket|championnat|score|r[eé]sultat sportif)\b",
    r"\b(bourse[s]? (de|du|des) valeur|action|crypto|bitcoin|investissement financier)\b",
    # Politique et gouvernance — sans rapport avec l'UAM
    r"\b([eé]lection|gouvernement|premier ministre|s[eé]nat|assembl[eé]e nationale)\b",
    r"\bpr[eé]sident.{0,30}(du\s+niger|de la r[eé]publique)\b",
    # Hébergement commercial / restauration non universitaire
    r"\b(h[ôo]tel|auberge|pension).{0,40}(niamey|niger)\b",
    # Prix du marché
    r"\bprix.{0,20}(du\s+)?(mil|riz|sucre|kilogramme|kg).{0,20}march[eé]\b",
    r"\bkilogramme.{0,20}(mil|riz|sucre)\b",
    # Université explicitement étrangère (hors Niger)
    r"universit[eé].{0,40}(fran[cç]aise?|[eé]trang[eè]re?|europ[eé]enne?|canadienne?|am[eé]ricaine?)\b",
    r"universit[eé]\s+(de\s+)?(tillab[eé]ri|maradi|tahoua|agadez|dosso|zinder)\b",
    # Visa/bourse explicitement orientés vers l'étranger (hors UAM)
    r"visa [eé]tudiant.{0,60}(france|canada|europe|belgique|maroc|s[eé]n[eé]gal|all?emagne)\b",
    r"bourse.{0,80}([eé]tudier|partir|aller).{0,40}([eé]tranger|abroad|hors du niger)\b",
]]

# Vectorstore global avec protection thread-safe
_vectorstore = None
_vectorstore_lock = threading.Lock()

# Statuts BD considérés comme "inscription validée" — centralisé ici pour éviter la dispersion.
_STATUTS_INSCRIPTION_VALIDES: frozenset = frozenset({
    "validé", "validee", "validated",
    "actif", "active",
    "inscrit", "inscrite", "enregistré", "enregistree",
    "confirmed", "confirmé",
})

# user_id de session, isolé par contexte d'exécution pour éviter les collisions
# inter-sessions. Un ContextVar (et non un threading.local) est nécessaire car le
# ToolNode exécute les outils dans un pool de threads : ces threads héritent du
# contexte de l'appelant, ce qu'un stockage par thread ne permet pas.
# Appelez set_session_user_id() au début de chaque requête ou session.
_session_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "uam_session_user_id", default=None
)


def set_session_user_id(user_id: str) -> None:
    """Fixe l'identifiant de session pour le contexte d'exécution courant."""
    _session_user_id.set(user_id)


def _get_session_user_id() -> str | None:
    return _session_user_id.get()

# Import du module de connexion à la base de données
try:
    from database_connector import (
        is_database_available,
        search_formations_db,
        search_students_db,
        search_schedules_db,
        search_fees_db,
        search_news_announcements_db,
        get_statistics_db,
        get_official_stats_db,
        search_student_courses_db,
    )
    _db_available = is_database_available()
except ImportError:
    _db_available = False
    logger.warning("Module database_connector non disponible")
except Exception as e:
    _db_available = False
    logger.error(f"Erreur lors de l'initialisation de la base de données : {e}")


@traceable
def set_vectorstore(vectorstore: FAISS):
    """Définit le vectorstore global pour les outils (thread-safe)"""
    global _vectorstore
    with _vectorstore_lock:
        _vectorstore = vectorstore
        _cached_similarity_search.cache_clear()


# ==================== OUTILS (TOOLS) ====================


def _normalize_query(query: str) -> str:
    """Normalise une requête pour le cache (minuscules, sans accents superflus, strip)."""
    nfkd = unicodedata.normalize("NFKD", query.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _sans_accents(texte: str) -> str:
    """Retire les signes diacritiques, sans toucher à la casse.

    La saisie sans accents est courante sur téléphone et sur clavier QWERTY :
    « Ou est la faculte ? » doit être comprise comme « Où est la faculté ? ».
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=256)
def _cached_similarity_search(query_normalized: str, k: int) -> tuple:
    """Recherche FAISS avec mise en cache LRU intra-session.

    Appelle directement le vectorstore (sans push_context) pour éviter le double
    enregistrement de contexte quand search_uam_knowledge appelle push_context après.
    Non utilisé en mode grounding (bypassed dans search_uam_knowledge).
    """
    if _vectorstore is None:
        return ()
    docs = _vectorstore.similarity_search(query_normalized, k=k)
    return tuple(doc.page_content for doc in docs)


def _rag_search(query: str, k: int = 5) -> list:
    """Effectue une recherche FAISS et enregistre le contexte pour RAGAS.

    En mode grounding (run gelé), utilise similarity_search_with_score
    et journalise les chunks+scores via grounding_capture.
    """
    if _vectorstore is None:
        return []
    if _GROUNDING_AVAILABLE and _gc.is_enabled():
        docs_scores = _vectorstore.similarity_search_with_score(query, k=k)
        _gc.log_retrieval(query, docs_scores)
        docs = [d for d, _ in docs_scores]
    else:
        docs = _vectorstore.similarity_search(query, k=k)
    push_context([d.page_content for d in docs])
    return docs


def _rag_response(query: str, not_found_msg: str = "Aucune information trouvée.", k: int = 5) -> str:
    """Recherche RAG + formatage unifié. Utilisé par tous les outils de recherche simples."""
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"
    docs = _rag_search(query, k=k)
    logger.debug(f"_rag_response — requête: '{query[:80]}' → {len(docs)} doc(s)")
    if not docs:
        return not_found_msg
    return "\n\n---\n\n".join(doc.page_content[:800] for doc in docs)


def _search_filiere_faculty(
    kw: str, filiere: str, faculty: str, not_found_tpl: str,
    default_target: str = "les filières",
) -> str:
    """Helper pour les outils (filiere, faculty) → requête FAISS + message introuvable.

    Construit la requête : kw+filière d'un côté, nom_complet+kw côté faculté.
    not_found_tpl doit contenir {target} (ex: "Aucune info pour {target}").
    """
    parts = []
    if filiere:
        parts.append(f"{kw} {filiere}")
    if faculty:
        info = get_structure_info(faculty)
        parts.append(f"{info['nom_complet'] if info else faculty} {kw}")
    query = " ".join(parts) if parts else kw
    target = filiere or faculty or default_target
    return _rag_response(query, not_found_tpl.format(target=target))


def _search_by_faculty_or_uam(kw: str, faculty: str, not_found_tpl: str) -> str:
    """Helper pour les outils faculty-only : requête faculté précise ou UAM en général.

    not_found_tpl doit contenir {target}.
    """
    if faculty:
        info = get_structure_info(faculty)
        nom = info["nom_complet"] if info else faculty
        query = f"{nom} {kw}"
    else:
        query = f"{kw} UAM université"
    target = faculty or "l'UAM"
    return _rag_response(query, not_found_tpl.format(target=target))


@tool
@retry_on_failure(max_retries=2, delay=0.5, exceptions=(IOError, OSError, TimeoutError))
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
    try:
        # Valider et nettoyer l'entrée
        config = get_config()
        max_length = min(500, config.max_input_length)
        query = sanitize_input(query, max_length=max_length)
        
        if _vectorstore is None:
            logger.error("Base de connaissances non initialisée")
            return "Erreur: Base de connaissances non initialisée"
        
        logger.debug(f"Recherche dans la base de connaissances: {query[:100]}...")
        
        # Détecter et remplacer les abréviations par leurs noms complets pour améliorer la recherche
        query_expanded = query
        detected_structures = detect_structure_in_text(query)
        
        if detected_structures:
            # Ajouter les noms complets des structures détectées à la requête
            structure_names = [s["nom_complet"] for s in detected_structures]
            query_expanded = f"{query} {' '.join(structure_names)}"
            logger.debug(f"Structures détectées: {[s['abreviation'] for s in detected_structures]}")
        
        # Recherche sémantique — cache LRU en production, bypass en mode grounding
        query_key = _normalize_query(query_expanded)
        k = config.vectorstore.similarity_search_k
        if _GROUNDING_AVAILABLE and _gc.is_enabled():
            docs_scores = _vectorstore.similarity_search_with_score(query_key, k=k)
            _gc.log_retrieval(query_key, docs_scores)
            page_contents = tuple(doc.page_content for doc, _ in docs_scores)
        else:
            page_contents = _cached_similarity_search(query_key, k)
        push_context(list(page_contents))

        if not page_contents:
            logger.warning(f"Aucun document trouvé pour la requête: {query[:100]}")
            return "Aucune information trouvée pour cette requête."

        # Combiner les documents
        context = "\n\n---\n\n".join(page_contents)
        
        logger.debug(f"Trouvé {len(page_contents)} document(s) pertinents")
        return context
        
    except ValueError as e:
        logger.error(f"Erreur de validation dans search_uam_knowledge: {e}")
        return f"Erreur: {str(e)}"
    except Exception as e:
        logger.error(f"Erreur inattendue dans search_uam_knowledge: {e}", exc_info=True)
        return "Une erreur s'est produite lors de la recherche. Veuillez réessayer."


@tool
def detect_greeting(message: str) -> str:
    """
    Détecte la nature du message : salutation, fin de conversation, remerciement ou question.

    Args:
        message: Le message de l'utilisateur

    Returns:
        "GREETING"  – salutation d'ouverture sans question UAM
        "FAREWELL"  – fin de conversation (au revoir, à bientôt, bonne journée…)
        "THANKS"    – remerciement seul
        "BOTH"      – salutation + question UAM
        "QUESTION"  – question ou demande d'information
    """
    message_lower = message.lower().strip()

    # --- Fins de conversation ---
    farewell_patterns = [
        r"\bau revoir\b", r"\b[aà] bient[oô]t\b", r"\b[aà] plus\b",
        r"\b[aà] plus tard\b", r"\bbonne journ[eé]e\b", r"\bbonne soir[eé]e\b",
        r"\bbonne nuit\b", r"\bbon apr[eè]s[-\s]?midi\b", r"\bbonne continuation\b",
        r"\bbye\b", r"\bgoodbye\b", r"\bciao\b", r"\badieu\b",
        r"\btermin[eé]\b", r"\bc['']est tout\b", r"\bc['']est bon\b",
        r"\bje pars\b", r"\bje m'en vais\b",
    ]
    is_farewell = any(re.search(p, message_lower) for p in farewell_patterns)

    # --- Remerciements ---
    thanks_patterns = [
        r"\bmerci\b", r"\bmerci beaucoup\b", r"\bmerci bien\b",
        r"\bje vous remercie\b", r"\bje te remercie\b",
        r"\bc['']est parfait\b", r"\bc['']est g[eé]nial\b",
        r"\btr[eè]s bien\b", r"\bparfait\b", r"\bnickel\b",
        r"\bthank[s]?\b",
    ]
    is_thanks = any(re.search(p, message_lower) for p in thanks_patterns)

    # --- Salutations d'ouverture ---
    greeting_patterns = [
        r"\bbonjour\b", r"\bbonsoir\b", r"\bsalut\b", r"\bcoucou\b",
        r"\bhey\b", r"\bhi\b", r"\bhello\b", r"\byo\b",
        r"\bbon matin\b",
        r"\bs'il vous pla[iî]t\b", r"\bs'il te pla[iî]t\b",
        r"\bsvp\b", r"\bstp\b",
        r"\bexcusez[-\s]?moi\b", r"\bexcuse[-\s]?moi\b", r"\bpardon\b",
        r"\bd[eé]sol[eé]e?\b",
        r"\bcomment allez[-\s]?vous\b", r"\bcomment vas[-\s]?tu\b",
        r"\b[cç]a va\b", r"\bcv\b", r"\bcc\b",
    ]
    is_greeting = any(re.search(p, message_lower) for p in greeting_patterns)

    # --- Question / contenu UAM ---
    question_keywords = [
        "?", "quoi", "comment", "pourquoi", "quand", "où",
        "qui", "quel", "quelle", "quels", "quelles", "combien",
        "est-ce que", "est-ce qu", "puis-je", "peut-on",
    ]
    uam_keywords = [
        "uam", "université", "faculté", "école", "institut", "formation",
        "inscription", "réinscription", "admission", "diplôme",
        "fast", "flsh", "fseg", "fsjp", "fa", "fss", "ens",
        "master", "licence", "doctorat", "thèse", "bourse", "étudiant",
    ]
    is_question = any(kw in message_lower for kw in question_keywords) or "?" in message
    has_uam_content = any(kw in message_lower for kw in uam_keywords)

    # --- Priorité : fin de conv > remerciement > salutation ---
    if is_farewell and not (is_question or has_uam_content):
        return "FAREWELL"
    if is_thanks and not (is_question or has_uam_content):
        return "THANKS"
    if is_greeting and (is_question or has_uam_content):
        return "BOTH"
    if is_greeting:
        return "GREETING"
    return "QUESTION"


@tool
def check_question_relevance(question: str) -> str:
    """
    Vérifie si une question concerne l'Université Abdou Moumouni de Niamey.
    Couvre aussi les cas des étudiants externes, étrangers et les questions sur
    les masters/doctorats pour candidats venant d'autres établissements.

    Args:
        question: La question de l'utilisateur

    Returns:
        "PERTINENT"   – question relative à l'UAM
        "HORS_SUJET"  – question sans rapport avec l'UAM
    """
    question_lower = question.lower()
    question_sans_accents = _sans_accents(question_lower)

    for pat in _OFF_TOPIC_RE:
        if pat.search(question_lower):
            return "HORS_SUJET"

    # Abréviations : recherche en mot entier. Testées par sous-chaîne, « fa »
    # matcherait « fait », « ens » matcherait « pense » — voir BUG-04.
    abreviations_uam = [
        "uam", "fast", "flsh", "fseg", "fsjp", "fa", "fss", "ens",
        "ed-svt", "ed-lashs", "ed-set", "irsh", "irem", "iri",
    ]
    for abbr in abreviations_uam:
        if re.search(rf"\b{re.escape(abbr)}\b", question_lower):
            return "PERTINENT"

    # Mots-clés porteurs de sens : sous-chaîne, pour couvrir les formes fléchies.
    keywords_uam = [
        "abdou moumouni",
        "faculté", "école", "institut", "formation", "filière",
        "inscription", "admission", "diplôme", "attestation",
        # BUG-05 (faux positif post-normalisation) : "relevé" seul est une
        # sous-chaîne de "relever" une fois désaccentué ("releve" ⊂
        # "relever"). On cible donc les tournures qui désignent réellement
        # le document, en gardant "mon relevé" pour les formulations
        # courtes ("je veux mon relevé") qui ne précisent pas "de notes".
        "relevé de notes", "mon relevé",
        "scolarité", "étudiant", "licence", "master", "doctorat", "thèse",
        "cours", "horaire", "service", "recteur", "doyen",
        "réinscription", "réinscrire", "préinscription", "dossier", "pièces",
        "calendrier", "date limite",
        "carte étudiant", "bourse", "logement", "cité universitaire",
        "orientation", "restauration", "bibliothèque",
    ]
    for kw in keywords_uam:
        if _sans_accents(kw) in question_sans_accents:
            return "PERTINENT"

    # "université", "niger", "niamey", "équivalence", "transfert" nécessitent
    # un contexte UAM explicite (trop larges seuls : hôtels, élections, ministère…)
    uam_geo_patterns = [
        r"universit[eé].{0,60}(uam|abdou moumouni|niamey|niger)",
        r"(niamey|niger).{0,60}(uam|universit[eé]|campus|[eé]tudiant|inscription|formation|facult[eé])",
        r"(uam|abdou moumouni|campus).{0,60}(niamey|niger)",
        r"(formation|inscription|[eé]tudier|admission).{0,40}(niamey|niger)\b",
        r"([eé]quivalence|transfert).{0,60}(uam|abdou moumouni|niamey|niger|facult[eé]|inscription)",
        # Restaurant universitaire UAM (≠ restaurants commerciaux à Niamey)
        r"restaurant.{0,40}(uam|campus|universit|[eé]tudiant)",
        r"repas.{0,40}(campus|universit|[eé]tudiant|uam)",
    ]
    for pattern in uam_geo_patterns:
        if re.search(pattern, question_lower):
            return "PERTINENT"

    # Questions d'étudiants externes / étrangers voulant rejoindre l'UAM
    external_patterns = [
        r"venir [aà] l[''']uam", r"int[eé]gr[eé]e? l[''']uam",
        r"venir [eé]tudier", r"[eé]tudier [aà] niamey",
        r"faire (un|mon|ma) master", r"faire (un|mon|ma) th[eè]se",
        r"faire (un|mon|ma) doctorat",
        r"candidature (externe|internationale)",
        r"[eé]tudiant[e]? [eé]tranger", r"[eé]tudiant[e]? international",
        r"venant d[''']une autre universit[eé]",
        r"universi[t]?[eé] [eé]trang[eè]re",
        r"reconnaiss?ance (de|du|des) dipl[ôo]me",
        # Équivalence et visa : requièrent explicitement le contexte UAM/Niger
        r"[eé]quivalence (de|du|des) dipl[ôo]me.{0,60}(uam|niger|niamey|abdou moumouni)",
        r"visa [eé]tudiant.{0,60}(uam|niger|niamey|abdou moumouni)",
        r"titre de s[eé]jour",
        r"d[eé]p[oô]t de candidature", r"soumission de dossier",
        r"accord de partenariat", r"convention inter[-\s]?universit",
        r"cotutelle", r"co-?direction (de|de la) th[eè]se",
        r"directeur de (m[eé]moire|th[eè]se|recherche)",
        r"laboratoire de recherche",
        r"capacit[eé] d[''']accueil",
    ]
    for pattern in external_patterns:
        if re.search(pattern, question_lower):
            return "PERTINENT"

    # Questions générales d'éducation pouvant concerner l'UAM
    education_phrases = [
        "comment s'inscrire", "quelles formations", "quel diplôme",
        "pièces à fournir", "conditions d'admission", "frais d'inscription",
        "comment candidater", "dépôt de dossier",
        # BUG-03 : « frais » seul est ambigu en français (adjectif), on cible
        # donc les tournures où il est un nom désignant un coût.
        "les frais", "des frais", "frais de scolarité", "frais universitaires",
        "frais de formation", "frais de dossier",
    ]
    for phrase in education_phrases:
        if _sans_accents(phrase) in question_sans_accents:
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
                results_parts.append(f"💰 FRAIS D'INSCRIPTION — {level.upper()} (tarifs officiels UAM) :")
                results_parts.append("")
                # Séparer UEMOA et hors UEMOA
                from collections import defaultdict
                by_nat: dict = defaultdict(list)
                for fee in db_results:
                    by_nat[fee.get("nationalite", "uemoa")].append(fee)

                # UEMOA : montant unique
                if "uemoa" in by_nat:
                    results_parts.append("  📋 Étudiants nigériens & zone UEMOA :")
                    for fee in by_nat["uemoa"]:
                        ind = fee.get("montant_indicatif")
                        results_parts.append(f"    • {ind:,} FCFA")
                    results_parts.append("")

                # Hors UEMOA : regrouper les facultés par montant
                if "hors_uemoa" in by_nat:
                    results_parts.append("  📋 Étudiants hors zone UEMOA :")
                    # Regrouper par montant → liste de composantes
                    by_amount: dict = defaultdict(list)
                    for fee in by_nat["hors_uemoa"]:
                        comp = fee.get("composante_sigle") or ""
                        ind = fee.get("montant_indicatif", 0)
                        if comp:
                            by_amount[ind].append(comp)
                    if by_amount:
                        for montant in sorted(by_amount.keys()):
                            composantes = ", ".join(sorted(set(by_amount[montant])))
                            results_parts.append(f"    • {composantes} : {montant:,} FCFA / an")
                    else:
                        # Pas de composante précisée → montant unique
                        for fee in by_nat["hors_uemoa"]:
                            ind = fee.get("montant_indicatif", 0)
                            results_parts.append(f"    • {ind:,} FCFA / an")
                    results_parts.append("")

                source_label = "officielle" if any(f.get("source") == "officiel_uam" for f in db_results) else "indicative"
                if source_label == "officielle":
                    results_parts.append("📄 Source : Service Central de la Scolarité (Formalités d'admission).")
                else:
                    results_parts.append("⚠️ Montants indicatifs — contactez le secrétariat de votre faculté.")
                results_parts.append("Zone UEMOA : Niger, Bénin, Côte d'Ivoire, Togo, Burkina Faso, Sénégal, Mali, Guinée Bissau.")
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche des frais en base de données : {e}")

    # 2. Tarifs officiels (fallback si BDD indisponible)
    # Source : Formalités_d_admission.txt — tarifs officiels d'inscription UAM
    if not results_parts:
        level_lower = level.lower()
        if level_lower in ("licence", "l1", "l2", "l3"):
            results_parts.append("💰 FRAIS D'INSCRIPTION EN LICENCE (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 10 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA (annuel) :")
            results_parts.append("    • FA, FAST : 250 000 FCFA")
            results_parts.append("    • FLSH, ENS, FSEG, FSJP : 150 000 FCFA")
            results_parts.append("    • FSS (Santé, 1ère–6ème année) : 200 000 FCFA")
        elif level_lower in ("master", "m1", "m2"):
            results_parts.append("💰 FRAIS D'INSCRIPTION EN MASTER (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 50 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA :")
            results_parts.append("    • Toutes facultés : 250 000 FCFA")
        elif level_lower == "doctorat":
            results_parts.append("💰 FRAIS D'INSCRIPTION EN DOCTORAT (tarifs officiels UAM) :")
            results_parts.append("")
            results_parts.append("  📋 Étudiants nigériens & zone UEMOA")
            results_parts.append("    • Inscription : 50 000 FCFA")
            results_parts.append("")
            results_parts.append("  📋 Étudiants hors zone UEMOA :")
            results_parts.append("    • FA, FAST, FLSH, ENS, FSEG, FSJP : 250 000 FCFA")
            results_parts.append("    • FSS (Santé, 7ème année – thèse) : 400 000 FCFA")
        else:
            return f"Niveau '{level}' non reconnu. Niveaux disponibles : licence, master, doctorat"
        if faculty:
            results_parts.append(f"\n  • Faculté concernée : {faculty}")
        results_parts.append("\nZone UEMOA : Niger, Bénin, Côte d'Ivoire, Togo, Burkina Faso, Sénégal, Mali, Guinée Bissau.")
        results_parts.append("⚠️ Dépôt du dossier au Service Central de la Scolarité (ENS).")

    result = "\n".join(results_parts)
    # Capture pour RAGAS : la grille tarifaire (codée en dur ou issue de la BD) est
    # la source factuelle de la réponse — sans ce push, faithfulness la voit "non soutenue".
    push_text(result)
    return result


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
                results_parts.append("📊 FORMATIONS DISPONIBLES (BASE DE DONNÉES) :")
                results_parts.append("")
                for formation in db_results[:15]:  # Limiter à 15 résultats
                    formation_info = []
                    if "name" in formation:
                        formation_info.append(f"🎓 {formation['name']}")
                    if "structure_nom" in formation:
                        formation_info.append(f"   Structure : {formation['structure_nom']}")
                    if "level" in formation:
                        formation_info.append(f"   Niveau : {formation['level']}")
                    if "conditions_acces" in formation and formation["conditions_acces"]:
                        formation_info.append(f"   Conditions d'accès : {formation['conditions_acces']}")
                    if "pieces_requises" in formation and formation["pieces_requises"]:
                        formation_info.append(f"   Pièces requises : {formation['pieces_requises']}")
                    if "objectifs" in formation and formation["objectifs"]:
                        formation_info.append(f"   Objectifs : {formation['objectifs']}")
                    
                    results_parts.append("\n".join(formation_info))
                    results_parts.append("")
                
                results_parts.append("---")
                results_parts.append("")
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche des formations en base de données : {e}")

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
        docs = _rag_search(query, k=5)
        
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
def search_admission_requirements(level: str = "", faculty: str = "", filiere: str = "") -> str:
    """
    Recherche les conditions d'admission et d'accès (par niveau, faculté ou filière).
    """
    query_parts = ["conditions d'admission", "conditions d'accès", "critères", "admissibilité"]
    if level:
        query_parts.append(f"niveau {level}")
    if filiere:
        query_parts.append(f"filière {filiere}")
    if faculty:
        structure_info = get_structure_info(faculty)
        query_parts.append(structure_info["nom_complet"] if structure_info else faculty)
    return _rag_response(" ".join(query_parts), "Aucune information sur les conditions d'admission trouvée.")


@tool
def search_required_documents(process: str = "inscription", level: str = "", faculty: str = "") -> str:
    """
    Recherche les pièces à fournir et documents requis (inscription/réinscription).
    """
    query_parts = ["pièces à fournir", "documents requis", "dossier", f"{process} université"]
    if level:
        query_parts.append(f"niveau {level}")
    if faculty:
        structure_info = get_structure_info(faculty)
        query_parts.append(structure_info["nom_complet"] if structure_info else faculty)
    return _rag_response(" ".join(query_parts), "Aucune information sur les pièces à fournir trouvée.")


@tool
def search_registration_procedure(process: str = "inscription") -> str:
    """
    Recherche la procédure/les étapes d'inscription ou de réinscription.
    """
    return _rag_response(
        f"procédure étapes {process} université UAM",
        "Aucune information sur la procédure d'inscription trouvée.",
    )


@tool
def search_registration_calendar(year: str = "") -> str:
    """
    Recherche le calendrier académique et les dates d'inscription.
    """
    query = "calendrier académique dates d'inscription date limite"
    if year:
        query = f"{query} {year}"
    return _rag_response(query, "Aucune information sur le calendrier d'inscription trouvée.")


@tool
def search_student_card() -> str:
    """
    Recherche les informations sur la carte d'étudiant (obtention, retrait, remplacement).
    """
    return _rag_response(
        "carte étudiant badge étudiant obtention retrait remplacement",
        "Aucune information sur la carte d'étudiant trouvée.",
    )


@tool
def search_transfer_equivalence(topic: str = "transfert") -> str:
    """
    Recherche les démarches de transfert, équivalence ou changement de filière.
    """
    return _rag_response(
        f"démarches {topic} équivalence changement de filière reprise d'études",
        "Aucune information sur le transfert/équivalence trouvée.",
    )


@tool
def search_housing_and_services(service: str = "") -> str:
    """
    Recherche les informations sur la vie étudiante (logement, restauration, transport, bibliothèque).
    """
    query = "logement cité universitaire restauration transport bibliothèque service social"
    if service:
        query = f"{query} {service}"
    return _rag_response(query, "Aucune information sur la vie étudiante trouvée.")


@tool
def search_scholarships() -> str:
    """
    Recherche les informations sur les bourses et aides financières.
    """
    return _rag_response(
        "bourse bourses aide financière allocation étudiant",
        "Aucune information sur les bourses trouvée.",
    )


@tool
def search_contacts_services(service: str = "") -> str:
    """
    Recherche les contacts des services (scolarité, secrétariat, admissions, etc.).
    """
    query = "contacts téléphone email adresse service scolarité secrétariat admissions"
    if service:
        query = f"{query} {service}"
    return _rag_response(query, "Aucune information de contact trouvée.")


@tool
def search_international_equivalence(level: str = "", country: str = "") -> str:
    """
    Recherche les procédures d'équivalence internationale et reconnaissance des diplômes étrangers.
    """
    query = "équivalence internationale reconnaissance diplômes étrangers admission"
    if level:
        query = f"{query} niveau {level}"
    if country:
        query = f"{query} pays {country}"
    return _rag_response(query, "Aucune information sur l'équivalence internationale trouvée.")


@tool
def search_late_reenrollment(reason: str = "") -> str:
    """
    Recherche les règles et démarches pour une réinscription tardive.
    """
    query = "réinscription tardive pénalités délais dérogation"
    if reason:
        query = f"{query} motif {reason}"
    return _rag_response(query, "Aucune information sur la réinscription tardive trouvée.")


@tool
def search_internship_info(filiere: str = "", level: str = "") -> str:
    """
    Recherche les informations sur les stages (conditions, durée, procédure).
    """
    query = "stage stages conditions durée convention procédure"
    if filiere:
        query = f"{query} filière {filiere}"
    if level:
        query = f"{query} niveau {level}"
    return _rag_response(query, "Aucune information sur les stages trouvée.")


@tool
def search_double_degree(filiere: str = "", faculty: str = "") -> str:
    """
    Recherche les informations sur les doubles diplômes ou parcours bi-diplômants.
    """
    query = "double diplôme double diplome bi-diplômant parcours double cursus"
    if filiere:
        query = f"{query} filière {filiere}"
    if faculty:
        structure_info = get_structure_info(faculty)
        query = f"{query} {structure_info['nom_complet'] if structure_info else faculty}"
    return _rag_response(query, "Aucune information sur les doubles diplômes trouvée.")


@tool
def generate_registration_checklist(
    profile: str = "nouveau",
    level: str = "",
    faculty: str = "",
    is_international: bool = False
) -> str:
    """
    Génère une checklist guidée pour l'inscription/réinscription selon le profil.
    """
    profile_lower = (profile or "nouveau").strip().lower()
    checklist = []

    if profile_lower in ["nouveau", "nouvel étudiant", "nouvelle etudiante"]:
        checklist.append("Checklist - Nouvel étudiant")
        checklist.append("1. Vérifier les conditions d'admission de la filière")
        checklist.append("2. Préparer les pièces requises (acte de naissance, relevés, etc.)")
        checklist.append("3. Déposer le dossier ou suivre la procédure indiquée")
        checklist.append("4. Payer les frais d'inscription/scolarité")
        checklist.append("5. Récupérer la carte d'étudiant")
    elif profile_lower in ["ancien", "réinscription", "reinscription", "ancien étudiant"]:
        checklist.append("Checklist - Réinscription")
        checklist.append("1. Consulter le calendrier de réinscription")
        checklist.append("2. Mettre à jour les pièces si nécessaire")
        checklist.append("3. Régler les frais de réinscription")
        checklist.append("4. Vérifier la confirmation d'inscription")
    else:
        checklist.append("Checklist - Inscription")
        checklist.append("1. Vérifier les conditions d'accès")
        checklist.append("2. Préparer les pièces requises")
        checklist.append("3. Suivre la procédure d'inscription")

    if level:
        checklist.append(f" Niveau ciblé : {level}")
    if faculty:
        checklist.append(f" Structure : {faculty}")
    if is_international:
        checklist.append(" Ajouter : documents d'équivalence et traduction certifiée si requis")

    checklist.append(" Besoin de détails ? Demandez les pièces ou la procédure exacte.")
    result = "\n".join(checklist)
    push_text(result)
    return result


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
        result_parts.append(f" {structure_info['nom_complet']} ({structure_info['abreviation']})")
        result_parts.append(f"Type: {structure_info['type'].capitalize()}")
        result_parts.append("")
        
        # Recherche spécifique pour la définition et la mission
        nom_complet = structure_info['nom_complet']
        
        # Recherche 1 : Définition
        query_definition = f"{nom_complet} définition présentation description"
        docs_definition = _rag_search(query_definition, k=2)
        
        # Recherche 2 : Mission
        query_mission = f"{nom_complet} mission objectifs rôles fonctions"
        docs_mission = _rag_search(query_mission, k=2)
        
        # Recherche 3 : Informations générales
        query_general = f"{nom_complet} informations générales"
        docs_general = _rag_search(query_general, k=3)
        
        # Combiner tous les résultats uniques
        all_docs = {}
        for doc in docs_definition + docs_mission + docs_general:
            # Utiliser le contenu comme clé pour éviter les doublons
            content_key = doc.page_content[:200]  # Premiers 200 caractères comme clé
            if content_key not in all_docs:
                all_docs[content_key] = doc.page_content
        
        if all_docs:
            result_parts.append(" DÉFINITION ET MISSION :")
            result_parts.append("")
            for i, content in enumerate(all_docs.values(), 1):
                result_parts.append(content[:1000])  # Limiter à 1000 caractères par document
                if i < len(all_docs):
                    result_parts.append("---")
        else:
            # Si pas de résultats spécifiques, faire une recherche générale
            search_query = nom_complet
            docs = _rag_search(search_query, k=3)
            
            if docs:
                result_parts.append(" INFORMATIONS :")
                result_parts.append("")
                for doc in docs:
                    result_parts.append(doc.page_content[:800])
                    result_parts.append("---")
    else:
        # Si la structure n'est pas trouvée dans la base structurée, faire une recherche générale
        search_query = f"{faculty_name} faculté école institut"
        docs = _rag_search(search_query, k=3)
        
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


@tool
def list_all_structures() -> str:
    """
    Liste toutes les facultés, écoles et instituts de l'UAM avec leurs abréviations.

    Returns:
        Liste complète des structures de l'UAM
    """
    result = list_all_structures_internal()
    push_text(result)
    return result


@tool
def save_user_preference(preference_key: str, preference_value: str) -> str:
    """
    Sauvegarde une préférence utilisateur pour la mémoire à long terme.
    L'identifiant de session est géré côté serveur — ne pas fournir de user_id.

    Args:
        preference_key: Clé de la préférence (ex: 'faculte_interesse', 'niveau_etude')
        preference_value: Valeur de la préférence

    Returns:
        Confirmation de sauvegarde
    """
    uid = _get_session_user_id()
    if not uid:
        return "Session non initialisée — préférence non sauvegardée."
    _user_memory.save_user_preference(uid, preference_key, preference_value)
    return f"Préférence '{preference_key}' sauvegardée avec succès : {preference_value}"


@tool
def get_user_preferences() -> str:
    """
    Récupère les préférences sauvegardées de la session courante.
    L'identifiant de session est géré côté serveur.

    Returns:
        Préférences de l'utilisateur au format JSON
    """
    uid = _get_session_user_id()
    if not uid:
        return "Session non initialisée — aucune préférence disponible."
    preferences = _user_memory.get_user_preferences(uid)
    if not preferences:
        return "Aucune préférence sauvegardée pour cette session."
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
    return _search_filiere_faculty(
        "prérequis pré-requis conditions admission",
        filiere, faculty,
        "Aucune information sur les prérequis trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "compétences connaissances requises",
        filiere, faculty,
        "Aucune information sur les compétences requises trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "cycles durée études licence master doctorat",
        filiere, faculty,
        "Aucune information sur les cycles et durées trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "chronogramme modules heures cours emploi temps programme",
        filiere, faculty,
        "Aucune information sur le chronogramme trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "coefficients modules",
        filiere, faculty,
        "Aucune information sur les coefficients trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "professeurs enseignants corps professoral qualifications",
        filiere, faculty,
        "Aucune information sur les professeurs trouvée pour {target}",
    )


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
    return _search_filiere_faculty(
        "débouchés professionnels embauche emploi carrière métiers",
        filiere, faculty,
        "Aucune information sur les débouchés trouvée pour {target}",
    )


@tool
def search_reglement_interieur(faculty: str = "") -> str:
    """
    Recherche le règlement intérieur d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel, si vide recherche le règlement général)

    Returns:
        Informations sur le règlement intérieur
    """
    return _search_by_faculty_or_uam(
        "règlement intérieur règles discipline",
        faculty,
        "Aucune information sur le règlement intérieur trouvée pour {target}",
    )


@tool
def search_organisation_corps_professoral(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps professoral d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)

    Returns:
        Informations sur l'organisation du corps professoral
    """
    return _search_by_faculty_or_uam(
        "organisation corps professoral structure enseignants",
        faculty,
        "Aucune information sur l'organisation du corps professoral trouvée pour {target}",
    )


@tool
def search_organisation_corps_estudiantin(faculty: str = "") -> str:
    """
    Recherche l'organisation du corps estudiantin (associations étudiantes, clubs, etc.) d'une faculté ou de l'université.

    Args:
        faculty: Nom ou abréviation de la faculté (optionnel)

    Returns:
        Informations sur l'organisation du corps estudiantin
    """
    return _search_by_faculty_or_uam(
        "organisation corps estudiantin associations étudiantes clubs étudiants",
        faculty,
        "Aucune information sur l'organisation du corps estudiantin trouvée pour {target}",
    )


@tool
def search_reclamations() -> str:
    """
    Recherche les différents types de réclamations possibles et comment les faire.

    Returns:
        Informations sur les réclamations et les procédures pour les faire
    """
    return _rag_response(
        "réclamations réclamation procédure comment faire démarche",
        "Aucune information sur les réclamations trouvée dans la base de connaissances.",
    )


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
    return _search_filiere_faculty(
        "avantages université UAM écoles instituts",
        filiere, faculty,
        "Aucune information sur les avantages trouvée pour {target}",
        default_target="l'université",
    )


@tool
def search_student_record(matricule: str, query_type: str = "inscription") -> str:
    """
    Consulte le dossier d'un étudiant par son matricule dans la base de données UAM.
    Permet de vérifier le statut d'inscription, les paiements, les résultats et les cours inscrits.

    Args:
        matricule: Numéro de matricule de l'étudiant (ex: UAM240001)
        query_type: Type de consultation —
            "inscription" : statut d'inscription uniquement
            "paiement"    : montants payés et frais
            "resultats"   : notes et crédits ECTS
            "cours"       : liste des UEs inscrites ce semestre
            "general"     : toutes les informations disponibles

    Returns:
        Informations sur le dossier de l'étudiant avec statut d'inscription, montants FCFA, notes, ECTS.
    """
    if not matricule or not matricule.strip():
        return "Veuillez fournir un numéro de matricule valide (ex: UAM240001)."

    matricule = matricule.strip().upper()

    if not _db_available:
        return (
            f"La base de données n'est pas disponible pour consulter le matricule {matricule}.\n"
            "Veuillez contacter directement le service de scolarité de votre faculté.\n"
            "Scolarité Centrale UAM : +227 20 74 06 61 — Lun–Ven 7h30–15h30."
        )

    try:
        students = search_students_db(student_id=matricule)
    except Exception as e:
        logger.error(f"Erreur BDD lors de la consultation du matricule {matricule}: {e}")
        return (
            f"Une erreur est survenue lors de la consultation du matricule {matricule}.\n"
            "Veuillez réessayer ou contacter le service de scolarité."
        )

    if not students:
        return (
            f"Aucun étudiant trouvé avec le matricule {matricule}.\n"
            "Vérifiez le numéro saisi ou contactez le service des inscriptions de l'UAM."
        )

    def _first_not_none(d: dict, *keys):
        """Retourne la première valeur non-None parmi les clés données (gère 0 correctement)."""
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    student = students[0]
    lines = [f"Dossier étudiant — Matricule : **{matricule}**\n"]

    # sanitize_input protège contre l'injection indirecte depuis la BDD
    nom = sanitize_input(
        f"{student.get('last_name', '')} {student.get('first_name', '')}".strip(),
        max_length=100
    )
    if nom:
        lines.append(f"**Nom :** {nom}")

    faculte = sanitize_input(
        student.get("faculty_abbreviation") or student.get("faculty", ""),
        max_length=50
    )
    if faculte:
        lines.append(f"**Faculté :** {faculte}")

    niveau = sanitize_input(student.get("level", ""), max_length=30)
    if niveau:
        lines.append(f"**Niveau :** {niveau}")

    # Statut d'inscription
    statut = student.get("inscription_status") or student.get("status", "")
    if statut:
        statut_label = "validée ✓" if statut.lower() in _STATUTS_INSCRIPTION_VALIDES else statut
        lines.append(f"\n**Statut d'inscription :** {statut_label}")
    else:
        lines.append("\n**Statut d'inscription :** non renseigné — contactez la scolarité pour confirmation.")

    # Paiements / frais (FCFA) — _first_not_none gère correctement la valeur 0
    if query_type in ("paiement", "general"):
        montant = _first_not_none(student, "fees_paid", "montant_paye")
        if montant is not None:
            lines.append(f"**Montant payé :** {int(montant):,} FCFA")
        frais_total = _first_not_none(student, "total_fees", "frais_total")
        if frais_total is not None:
            lines.append(f"**Frais totaux :** {int(frais_total):,} FCFA")
        reste = _first_not_none(student, "remaining_fees", "reste_a_payer")
        if reste is not None:
            lines.append(f"**Reste à payer :** {int(reste):,} FCFA")

    # Résultats académiques — idem pour 0 crédit ou 0/20
    if query_type in ("resultats", "general"):
        moyenne = _first_not_none(student, "average", "moyenne_generale")
        if moyenne is not None:
            lines.append(f"\n**Moyenne générale :** {moyenne}/20")
        credits = _first_not_none(student, "credits_valides", "ects_valides")
        if credits is not None:
            lines.append(f"**Crédits ECTS validés :** {credits}")
        notes_raw = student.get("notes") or student.get("results")
        if notes_raw:
            lines.append("**Notes par UE :**")
            if isinstance(notes_raw, list):
                for ue in notes_raw[:8]:
                    ue_name = ue.get("ue") or ue.get("matiere", "UE inconnue")
                    note = ue.get("note") or ue.get("grade", "—")
                    valide = " ✓ validé" if ue.get("valide") or ue.get("validated") else ""
                    lines.append(f"  • {ue_name} : {note}/20{valide}")
            else:
                lines.append(f"  {notes_raw}")

    # Cours inscrits (UEs de la formation)
    if query_type in ("cours", "general"):
        try:
            cours = search_student_courses_db(matricule)
        except Exception as e:
            logger.error(f"Erreur récupération cours pour {matricule}: {e}")
            cours = []
        if cours:
            lines.append("\n**Cours inscrits cette année :**")
            sem_courant = None
            for c in cours:
                sem = c.get("semestre")
                if sem != sem_courant:
                    sem_courant = sem
                    lines.append(f"\n  *Semestre {sem}*")
                code   = sanitize_input(c.get("code_ue", ""), max_length=20)
                titre  = sanitize_input(c.get("intitule", ""), max_length=80)
                ects   = c.get("credits_ects", "?")
                statut = c.get("statut_ue", "")
                statut_label = " ✓" if statut == "valide" else (" ⏳" if statut == "en_cours" else "")
                lines.append(f"  • {code} — {titre} ({ects} ECTS){statut_label}")
        else:
            lines.append("\nAucun cours trouvé pour cette inscription. Contactez la scolarité.")

    lines.append(
        "\nPour toute contestation ou information complémentaire, contactez le service de scolarité "
        "de votre faculté ou la Scolarité Centrale (Tél : +227 20 74 06 61)."
    )
    result = "\n".join(lines)
    push_text(result)
    return result


@tool
def search_statistics_uam(faculty: str = "", level: str = "", year: str = "2024-2025") -> str:
    """
    Donne les statistiques de l'UAM : effectifs étudiants par composante/niveau ET
    nombre d'enseignants-chercheurs, PAT et vacataires issus des données officielles.
    Utiliser pour : "Combien d'étudiants à la FAST ?", "Combien d'enseignants-chercheurs ?",
    "Effectif total UAM ?", "Combien d'inscrits en L1 ?".

    Args:
        faculty: Sigle de la composante (FAST, FLSH, FA, FSEG, FSJP…) — vide = toutes
        level:   Niveau (L1, L2, L3, M1, M2…) — vide = tous
        year:    Année académique pour les inscriptions courantes (défaut : 2024-2025)
    """
    if not _db_available:
        return (
            "La base de données n'est pas disponible pour les statistiques.\n"
            "Contactez la Direction des Études et des Stages (DES) de l'UAM : +227 20 74 06 61."
        )

    from collections import defaultdict
    lines = []

    # ── Partie 1 : inscriptions courantes (table inscriptions) ─────────────────
    try:
        rows = get_statistics_db(
            faculty=faculty.strip() or None,
            level=level.strip() or None,
            year=year.strip() or "2024-2025",
        )
    except Exception as e:
        logger.error(f"Erreur BDD statistiques inscriptions: {e}")
        rows = []

    if rows:
        lines.append(f"**Inscriptions — Année {year}**\n")
        by_faculty: dict = defaultdict(list)
        for r in rows:
            by_faculty[f"{r.get('faculty','?')} — {r.get('faculty_name','?')}"].append(
                (r.get("level", "?"), int(r.get("effectif", 0)))
            )
        total_global = 0
        for fac_label, niveaux in sorted(by_faculty.items()):
            sous_total = sum(n for _, n in niveaux)
            total_global += sous_total
            lines.append(f"- **{fac_label}** : {sous_total} étudiant(s)")
            if len(niveaux) > 1 or level:
                for niv, nb in niveaux:
                    lines.append(f"    • {niv} : {nb}")
        if not faculty:
            lines.append(f"\n**Total inscriptions {year} : {total_global} étudiant(s)**")

    # ── Partie 2 : statistiques officielles (enseignants-chercheurs, effectifs historiques) ─
    try:
        official = get_official_stats_db(faculty=faculty.strip() or None)
    except Exception as e:
        logger.error(f"Erreur BDD statistiques officielles: {e}")
        official = []

    if official:
        if lines:
            lines.append("")
        lines.append("**Données officielles (source : documents UAM)**\n")
        for o in official:
            fac   = o.get("faculty", "?")
            fname = o.get("faculty_name", "?")
            annee = o.get("annee_reference", "?")
            nb_e  = o.get("nb_etudiants")
            nb_ec = o.get("nb_enseignants_chercheurs")
            rang_a= o.get("dont_rang_a")
            vacat = o.get("nb_vacataires")
            pat   = o.get("nb_pat")

            entry = [f"- **{fac} — {fname}** ({annee}) :"]
            if nb_e  is not None: entry.append(f"    • Étudiants : {nb_e:,}")
            if nb_ec is not None:
                ec_detail = f" (dont {rang_a} rang A)" if rang_a else ""
                entry.append(f"    • Enseignants-chercheurs : {nb_ec}{ec_detail}")
            if vacat is not None: entry.append(f"    • Vacataires : {vacat}")
            if pat   is not None: entry.append(f"    • PAT : {pat}")
            lines.extend(entry)

    if not lines:
        target = faculty.upper() if faculty else "l'UAM"
        return (
            f"Aucune statistique trouvée pour {target}.\n"
            "Contactez la scolarité ou la Direction des Études de l'UAM : +227 20 74 06 61."
        )

    lines.append(
        "\n*Inscriptions courantes : base scolarité UAM. "
        "Données officielles : documents UAM (info_UAM.md, rapport 2022-2023).*"
    )
    result = "\n".join(lines)
    push_text(result)
    return result


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
        return " Base de données non disponible. Les actualités ne peuvent pas être récupérées."
    
    try:
        announcements = search_news_announcements_db(limit=limit, category=category)
        
        if not announcements:
            return "Aucune actualité trouvée."
        
        results_parts = []
        results_parts.append(" DERNIÈRES ACTUALITÉS ET ANNONCES UAM :")
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

        result = "\n".join(results_parts)
        push_text(result)
        return result
        
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
        return " Base de données non disponible. Les horaires ne peuvent pas être récupérés depuis la BD."
    
    try:
        # Détecter l'abréviation de la faculté si nécessaire
        faculty_abbrev = None
        if faculty:
            structure_info = get_structure_info(faculty)
            if structure_info:
                faculty_abbrev = structure_info["abreviation"]
            else:
                faculty_abbrev = faculty.upper()
        
        schedules = search_schedules_db(faculty=faculty_abbrev, filiere=filiere, level=level)
        
        if not schedules:
            return f"Aucun horaire trouvé pour {faculty if faculty else 'les structures'}."
        
        results_parts = []
        results_parts.append("⏰ HORAIRES DES SERVICES UAM (BASE DE DONNÉES) :")
        results_parts.append("")
        
        for schedule in schedules[:20]:  # Limiter à 20 résultats
            sched_info = []
            if "service" in schedule:
                sched_info.append(f"📍 {schedule['service']}")
            if "jours" in schedule:
                sched_info.append(f"   Jours : {schedule['jours']}")
            if "heures_ouverture" in schedule and "heures_fermeture" in schedule:
                sched_info.append(f"   Horaires : {schedule['heures_ouverture']} - {schedule['heures_fermeture']}")
            elif "start_time" in schedule and "end_time" in schedule:
                sched_info.append(f"   Horaires : {schedule['start_time']} - {schedule['end_time']}")
            if "notes" in schedule and schedule["notes"]:
                sched_info.append(f"   Notes : {schedule['notes']}")
            
            results_parts.append("\n".join(sched_info))
            results_parts.append("")
        
        result = "\n".join(results_parts)
        push_text(result)
        return result

    except Exception as e:
        return f"Erreur lors de la récupération des horaires : {e}"


@tool
def detect_user_profile(message: str) -> str:
    """
    Détecte le profil de l'utilisateur à partir de son message pour personnaliser la réponse.

    Args:
        message: Le message de l'utilisateur

    Returns:
        Un des profils : ETUDIANT_UAM | BACHELIER | ETUDIANT_EXTERNE | ETUDIANT_ETRANGER |
                         CANDIDAT_MASTER | CANDIDAT_DOCTORAT | PARENT | PROFESSIONNEL | INCONNU
    """
    msg = message.lower()

    # Candidat doctorat / thèse
    doctorat_patterns = [
        r"\bth[eè]se\b", r"\bdoctorat\b", r"\bphd\b",
        r"\bdirecteur de th[eè]se\b", r"\bcotutelle\b",
        r"\b[eé]cole doctorale\b", r"\bed[-\s]?(svt|lashs|set)\b",
        r"\bsoutenance\b",
    ]
    if any(re.search(p, msg) for p in doctorat_patterns):
        return "CANDIDAT_DOCTORAT"

    # Candidat master venant d'ailleurs
    master_external_patterns = [
        r"faire (un|mon|ma) master",
        r"(venir|int[eé]grer|rejoindre|candidater).{0,30}master",
        r"master.{0,30}(venant|externe|[eé]tranger|autre universit[eé])",
        r"(licence|bac\+3|l3|bac 3).{0,30}master",
    ]
    if any(re.search(p, msg) for p in master_external_patterns):
        return "CANDIDAT_MASTER"

    # Étudiant étranger (hors Niger)
    etranger_patterns = [
        r"[eé]tudiant.{0,15}[eé]tranger", r"[eé]tudiant.{0,15}international",
        r"je viens (de|du|d['''])", r"je suis (de|du|d['''])",
        r"pays.{0,20}[eé]tranger", r"[eé]trang[eè]re?",
        r"visa [eé]tudiant", r"titre de s[eé]jour",
        r"ambassade", r"consulat",
    ]
    if any(re.search(p, msg) for p in etranger_patterns):
        return "ETUDIANT_ETRANGER"

    # Étudiant venant d'une autre université nigérienne
    externe_patterns = [
        r"autre universit[eé]", r"universit[eé] (de|d['''])\w+",
        r"(venant|venu|transf[eé]r[eé]).{0,20}(universit[eé]|[eé]tablissement|[eé]cole)",
        r"transfert (depuis|de|d['''])",
        r"[eé]quivalence (de|du|des) (dipl[ôo]me|cr[eé]dit)",
    ]
    if any(re.search(p, msg) for p in externe_patterns):
        return "ETUDIANT_EXTERNE"

    # Bachelier / nouveau lycéen
    bachelier_patterns = [
        r"\bbac\b", r"\bbaccalaur[eé]at\b", r"\bterminale\b",
        r"\blyc[eé]e\b", r"\bnouvel[le]? [eé]tudiant\b",
        r"\bpremi[eè]re.{0,10}(ann[eé]e|inscription|fois)\b",
        r"\bfutur [eé]tudiant\b", r"je veux (m[''']inscrire|int[eé]grer)",
    ]
    if any(re.search(p, msg) for p in bachelier_patterns):
        return "BACHELIER"

    # Parent
    parent_patterns = [
        r"\bmon (fils|enfant|fille|kid)\b", r"\bma fille\b",
        r"\bpour mon enfant\b", r"\bparent\b",
    ]
    if any(re.search(p, msg) for p in parent_patterns):
        return "PARENT"

    # Professionnel (formation continue, VAE)
    pro_patterns = [
        r"\bformation continue\b", r"\bvae\b", r"\bvap\b",
        r"\bvalidation des acquis\b", r"\breprise d[''']études\b",
        r"\bsalarié\b", r"\bnouveaux horizons\b",
    ]
    if any(re.search(p, msg) for p in pro_patterns):
        return "PROFESSIONNEL"

    # Étudiant UAM actuel (réinscription, carte étudiant, notes…)
    uam_student_patterns = [
        r"\br[eé]inscription\b", r"\bma carte [eé]tudiant\b",
        r"\bmes notes\b", r"\bmon (relevé|attestation|diplôme)\b",
        r"\bje suis [eé]tudiant(e)? [aà] l[''']uam\b",
        r"\bje suis inscrit\b",
    ]
    if any(re.search(p, msg) for p in uam_student_patterns):
        return "ETUDIANT_UAM"

    return "INCONNU"


@tool
def detect_frustration_or_confusion(message: str) -> str:
    """
    Détecte si l'utilisateur est frustré, confus, répète une question ou est insatisfait.

    Args:
        message: Le message de l'utilisateur

    Returns:
        "FRUSTRATION" | "CONFUSION" | "REPETITION" | "NORMAL"
    """
    msg = message.lower()

    frustration_patterns = [
        r"\bça ne marche pas\b", r"\bnul\b", r"\binutile\b",
        r"\baucune aide\b", r"\bpas utile\b", r"\bc[''']est nul\b",
        r"\bc[''']est mauvais\b", r"\bmauvais (assistant|agent|bot)\b",
        r"\btu ne comprends? pas\b", r"\btu comprends? rien\b",
        r"\btu sers? [aà] rien\b", r"\bje suis d[eé][cç]u\b",
        r"\bje suis frustr[eé]\b", r"\bc[''']est inacceptable\b",
        r"\blaisse tomber\b", r"\bc[''']est peine perdue\b",
        r"\bpas de r[eé]ponse\b", r"\b(tr[eè]s|vraiment) d[eé][cç]evant\b",
    ]
    if any(re.search(p, msg) for p in frustration_patterns):
        return "FRUSTRATION"

    confusion_patterns = [
        r"\bje ne comprends? pas\b", r"\bje n[''']y comprends? rien\b",
        r"\bc[''']est confus\b", r"\bpeux.tu (expliquer|clarifier|r[eé]p[eé]ter)\b",
        r"\bpeux.vous (expliquer|clarifier|r[eé]p[eé]ter)\b",
        r"\bje suis perdu\b", r"\bje suis perdue\b",
        r"\bque veux.tu dire\b", r"\bque voulez.vous dire\b",
        r"\bc[''']est quoi exactement\b", r"\bje ne sais pas (quoi|comment)\b",
        r"\btu parles? de quoi\b",
    ]
    if any(re.search(p, msg) for p in confusion_patterns):
        return "CONFUSION"

    repetition_patterns = [
        r"\bj[''']ai (d[eé]j[aà]|encore) demand[eé]\b",
        r"\btu as d[eé]j[aà] dit\b", r"\btu l[''']as d[eé]j[aà] dit\b",
        r"\btu r[eé]p[eè]tes?\b", r"\bm[eê]me r[eé]ponse\b",
        r"\btoujours (la m[eê]me|pareil)\b",
        r"\bcomme (avant|tout [aà] l[''']heure|pr[eé]c[eé]demment)\b",
        r"\bque j[''']ai dit\b", r"\bj[''']ai dit que\b",
    ]
    if any(re.search(p, msg) for p in repetition_patterns):
        return "REPETITION"

    return "NORMAL"


@tool
def get_agent_capabilities() -> str:
    """
    Retourne la liste des domaines couverts par l'assistant UAM.
    À utiliser quand l'utilisateur demande ce que l'agent peut faire, ses limites ou ses fonctions.

    Returns:
        Description structurée des capacités de l'assistant
    """
    return """Je suis l'assistant virtuel officiel de l'Université Abdou Moumouni de Niamey (UAM).

DOMAINES OÙ JE PEUX VOUS AIDER :

🎓 FORMATIONS & FILIÈRES
- Formations disponibles par faculté et par niveau (Licence, Master, Doctorat)
- Cycles d'études et durées
- Prérequis et conditions d'accès
- Compétences requises

📝 INSCRIPTION & ADMISSION
- Procédures d'inscription et de réinscription
- Pièces à fournir selon votre profil
- Calendrier académique et dates limites
- Frais de scolarité
- Carte d'étudiant

🌍 ÉTUDIANTS VENANT D'AUTRES ÉTABLISSEMENTS
- Transfert et équivalence de crédits (étudiants d'autres universités nigériennes)
- Reconnaissance de diplômes étrangers
- Procédures spécifiques aux étudiants internationaux
- Visa étudiant et titre de séjour

🔬 MASTER & DOCTORAT
- Conditions d'admission en Master (candidats externes et internes)
- Admission en Doctorat / Thèse
- Écoles doctorales (ED-SVT, ED-LASHS, ED-SET)
- Recherche de directeur de mémoire / thèse
- Partenariats et cotutelles internationales

🏛️ STRUCTURES DE L'UAM
- Présentation des 7 facultés, 3 instituts et 4 écoles
- Organisation administrative
- Contacts et services

🌟 VIE ÉTUDIANTE & SERVICES
- Logement et cités universitaires
- Restauration, bibliothèque, transport
- Bourses et aides financières
- Associations étudiantes

LIMITES :
- Je ne peux pas accéder à vos données personnelles (notes, inscription individuelle)
- Pour des démarches officielles, je vous oriente vers le service compétent
- Certaines informations peuvent nécessiter confirmation auprès de la scolarité"""


@tool
def search_external_student_master(
    origin_country: str = "",
    origin_university: str = "",
    filiere: str = "",
    faculty: str = ""
) -> str:
    """
    Recherche les informations pour les étudiants venant d'autres universités (nigériennes
    ou étrangères) souhaitant s'inscrire en Master à l'UAM.
    Couvre : conditions d'admission, reconnaissance des crédits, dossier à fournir, délais.

    Args:
        origin_country: Pays d'origine de l'étudiant (optionnel)
        origin_university: Université ou établissement d'origine (optionnel)
        filiere: Filière de master souhaitée (optionnel)
        faculty: Faculté cible à l'UAM (optionnel)

    Returns:
        Informations détaillées sur l'admission en Master pour candidats externes
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "admission master candidat externe",
        "conditions accès master",
        "dossier inscription master",
        "équivalence crédits master",
        "transfert master",
    ]
    if filiere:
        query_parts.append(f"master {filiere}")
    if faculty:
        info = get_structure_info(faculty)
        query_parts.append(info["nom_complet"] if info else faculty)
    if origin_country and origin_country.lower() not in ("niger", "nigérien", "nigérienne"):
        query_parts.append("étudiant étranger international admission")
    if origin_university:
        query_parts.append(f"université {origin_university} équivalence")

    query = " ".join(query_parts)
    docs = _rag_search(query, k=5)

    intro = []
    if origin_country:
        intro.append(f"Pays d'origine : {origin_country}")
    if origin_university:
        intro.append(f"Établissement d'origine : {origin_university}")
    if filiere:
        intro.append(f"Master visé : {filiere}")

    if not docs:
        header = "\n".join(intro) + "\n\n" if intro else ""
        return (
            header
            + "Aucune information spécifique trouvée dans la base de connaissances.\n\n"
            + "Conseil : Contactez directement le service des admissions ou la scolarité "
            + "de la faculté concernée pour connaître les modalités exactes d'admission en Master "
            + "pour les candidats venant d'autres établissements."
        )

    results = ["\n".join(intro)] if intro else []
    results += [doc.page_content[:900] for doc in docs]
    return "\n\n---\n\n".join(results)


@tool
def search_phd_admission(
    specialty: str = "",
    faculty: str = "",
    doctoral_school: str = ""
) -> str:
    """
    Recherche les conditions et procédures d'admission en Doctorat / Thèse à l'UAM.
    Inclut les informations sur les Écoles Doctorales (ED-SVT, ED-LASHS, ED-SET),
    la recherche d'un directeur, le dépôt de candidature et les délais.

    Args:
        specialty: Spécialité ou domaine de recherche visé (optionnel)
        faculty: Faculté ou structure d'accueil (optionnel)
        doctoral_school: École doctorale cible (optionnel, ex: "ED-SVT", "ED-SET")

    Returns:
        Informations sur l'admission en Doctorat à l'UAM
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "admission doctorat thèse",
        "conditions inscription doctorat",
        "école doctorale",
        "directeur de thèse",
        "dépôt dossier doctorat",
    ]
    if specialty:
        query_parts.append(f"doctorat {specialty}")
    if doctoral_school:
        info = get_structure_info(doctoral_school)
        query_parts.append(info["nom_complet"] if info else doctoral_school)
    if faculty:
        info = get_structure_info(faculty)
        query_parts.append(info["nom_complet"] if info else faculty)

    query = " ".join(query_parts)
    docs = _rag_search(query, k=5)

    # Informations structurées sur les écoles doctorales UAM
    doctoral_schools_info = (
        "\n📚 ÉCOLES DOCTORALES DE L'UAM :\n"
        "• ED-SVT  – École Doctorale des Sciences de la Vie et de la Terre\n"
        "• ED-LASHS – École Doctorale Lettres, Arts, Sciences Humaines et Sociales\n"
        "• ED-SET  – École Doctorale des Sciences Exactes et Techniques\n"
    )
    # Préambule statique = source factuelle (noms des écoles doctorales) à capturer
    # pour RAGAS ; les chunks FAISS sont déjà poussés par _rag_search.
    push_text(doctoral_schools_info)

    if not docs:
        return (
            doctoral_schools_info
            + "\nAucune information complémentaire trouvée dans la base de connaissances.\n\n"
            + "Conseil : Contactez directement l'école doctorale ou la direction de la recherche "
            + "de l'UAM pour connaître les conditions d'admission en Doctorat."
        )

    results = [doctoral_schools_info] + [doc.page_content[:900] for doc in docs]
    return "\n\n---\n\n".join(results)


@tool
def search_foreign_student_procedures(
    country: str = "",
    level: str = ""
) -> str:
    """
    Recherche les procédures spécifiques pour les étudiants étrangers souhaitant
    étudier à l'UAM : visa étudiant, titre de séjour, logement dédié, frais spécifiques,
    reconnaissance de diplômes, procédures d'inscription.

    Args:
        country: Pays d'origine de l'étudiant (optionnel)
        level: Niveau d'études visé (licence, master, doctorat) – optionnel

    Returns:
        Informations sur les démarches pour étudiants internationaux
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "étudiant étranger international",
        "visa étudiant Niger Niamey",
        "titre de séjour étudiant",
        "inscription étudiant étranger",
        "reconnaissance diplôme étranger équivalence",
        "logement international cité universitaire",
    ]
    if level:
        query_parts.append(f"niveau {level} étudiant étranger")
    if country:
        query_parts.append(f"étudiant {country}")

    query = " ".join(query_parts)
    docs = _rag_search(query, k=5)

    static_info = (
        "\n🌍 INFORMATIONS POUR ÉTUDIANTS ÉTRANGERS À L'UAM :\n\n"
        "📋 Démarches générales recommandées :\n"
        "1. Obtenir l'admission de la faculté souhaitée (lettre d'acceptation)\n"
        "2. Demander un visa étudiant auprès de l'ambassade du Niger dans votre pays\n"
        "3. Faire valider votre diplôme (équivalence) par le Ministère de l'Éducation du Niger\n"
        "4. Déposer votre dossier d'inscription à la scolarité de la faculté\n"
        "5. Vous enregistrer à la Direction des Affaires Étudiantes (DAE) pour le logement\n\n"
        "📞 Pour plus d'informations, contactez la Direction des Relations Internationales de l'UAM.\n"
    )
    # Démarches statiques = source factuelle à capturer pour RAGAS.
    push_text(static_info)

    if not docs:
        return static_info
    results = [static_info] + [doc.page_content[:800] for doc in docs]
    return "\n\n---\n\n".join(results)


@tool
def search_recognition_prior_learning(
    level: str = "",
    faculty: str = "",
    experience_type: str = ""
) -> str:
    """
    Recherche les procédures de Validation des Acquis de l'Expérience (VAE) ou
    Validation des Acquis Professionnels (VAP) et de reprise d'études à l'UAM.
    Pour les professionnels souhaitant reprendre des études ou faire valider leur parcours.

    Args:
        level: Niveau visé (licence, master, doctorat) – optionnel
        faculty: Faculté ou domaine (optionnel)
        experience_type: Type d'expérience (professionnelle, académique, etc.) – optionnel

    Returns:
        Informations sur la VAE/VAP et la reprise d'études
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "validation acquis expérience VAE VAP",
        "reprise d'études formation continue",
        "reconnaissance acquis antérieurs",
        "expérience professionnelle admission",
    ]
    if level:
        query_parts.append(f"niveau {level}")
    if faculty:
        info = get_structure_info(faculty)
        query_parts.append(info["nom_complet"] if info else faculty)
    if experience_type:
        query_parts.append(experience_type)

    query = " ".join(query_parts)
    docs = _rag_search(query, k=4)

    if not docs:
        return (
            "Aucune information spécifique sur la VAE/VAP trouvée dans la base de connaissances.\n\n"
            "Conseil : La validation des acquis de l'expérience est une procédure qui varie selon "
            "les facultés. Contactez directement la scolarité de la faculté concernée ou la "
            "Direction des Études et de la Vie Universitaire (DEVU) de l'UAM pour connaître "
            "les modalités de reconnaissance de votre parcours."
        )
    return "\n\n---\n\n".join(doc.page_content[:800] for doc in docs)


@tool
def search_master_thesis_supervision(
    specialty: str = "",
    faculty: str = "",
    research_axis: str = ""
) -> str:
    """
    Recherche les informations sur les directeurs de mémoire / thèse disponibles à l'UAM,
    les axes de recherche, les laboratoires, et la procédure pour trouver et contacter
    un directeur de recherche.

    Args:
        specialty: Spécialité ou domaine de recherche (optionnel)
        faculty: Faculté ou structure (optionnel)
        research_axis: Axe de recherche spécifique (optionnel)

    Returns:
        Informations sur l'encadrement et la direction de recherche à l'UAM
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "directeur de mémoire thèse encadrement",
        "laboratoire de recherche",
        "axes de recherche",
        "enseignants chercheurs",
    ]
    if specialty:
        query_parts.append(f"recherche {specialty}")
    if faculty:
        info = get_structure_info(faculty)
        query_parts.append(info["nom_complet"] if info else faculty)
    if research_axis:
        query_parts.append(research_axis)

    query = " ".join(query_parts)
    docs = _rag_search(query, k=4)

    guidance = (
        "\n🔬 COMMENT TROUVER UN DIRECTEUR DE MÉMOIRE/THÈSE À L'UAM :\n\n"
        "1. Identifiez votre domaine de recherche et la faculté/école doctorale correspondante\n"
        "2. Consultez la liste des enseignants-chercheurs de la structure cible\n"
        "3. Prenez contact par email ou en présentiel avec le(s) directeur(s) potentiel(s)\n"
        "4. Soumettez un pré-projet de recherche (2-3 pages) pour discussion\n"
        "5. Une fois l'accord obtenu, formalisez la direction par un document officiel\n\n"
        "📞 Pour les thèses en cotutelle internationale : contactez la Direction des Relations "
        "Internationales de l'UAM.\n"
    )
    # Guide statique = source factuelle à capturer pour RAGAS.
    push_text(guidance)

    if not docs:
        return guidance
    results = [guidance] + [doc.page_content[:800] for doc in docs]
    return "\n\n---\n\n".join(results)


@tool
def search_academic_partnership(
    country: str = "",
    institution: str = "",
    program_type: str = ""
) -> str:
    """
    Recherche les partenariats académiques de l'UAM avec d'autres universités nationales
    ou internationales : accords d'échange, cotutelles, programmes conjoints, mobilité.

    Args:
        country: Pays partenaire (optionnel)
        institution: Université ou institution partenaire (optionnel)
        program_type: Type de programme (échange, cotutelle, double diplôme…) – optionnel

    Returns:
        Informations sur les partenariats et accords de coopération de l'UAM
    """
    if _vectorstore is None:
        return "Erreur: Base de connaissances non initialisée"

    query_parts = [
        "partenariat accord coopération universités",
        "mobilité étudiante échange international",
        "convention inter-universitaire",
    ]
    if country:
        query_parts.append(f"partenariat {country}")
    if institution:
        query_parts.append(f"accord {institution}")
    if program_type:
        query_parts.append(program_type)

    query = " ".join(query_parts)
    docs = _rag_search(query, k=4)

    if not docs:
        return (
            "Aucune information détaillée sur les partenariats trouvée dans la base de connaissances.\n\n"
            "Pour connaître les accords de coopération et partenariats de l'UAM, contactez :\n"
            "• La Direction des Relations Internationales et de la Coopération (DRIC) de l'UAM\n"
            "• Le Bureau des Relations Extérieures de la faculté concernée"
        )
    return "\n\n---\n\n".join(doc.page_content[:800] for doc in docs)


@traceable
def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    tools = [
        # Détection et profiling conversationnel
        detect_greeting,
        detect_user_profile,
        detect_frustration_or_confusion,
        get_agent_capabilities,
        check_question_relevance,

        # Recherche générale
        search_uam_knowledge,
        get_faculty_info,
        get_structure_by_abbreviation,
        list_all_structures,

        # Formations et filières
        search_formations,
        search_prerequisites,
        search_competences_requises,
        search_cycles_et_duree,
        search_chronogramme,
        search_coefficients,
        search_debouches,
        search_avantages_universite,

        # Admission et inscription
        search_admission_requirements,
        search_required_documents,
        search_registration_procedure,
        search_registration_calendar,
        search_late_reenrollment,
        generate_registration_checklist,
        calculate_fees,

        # Étudiants externes / étrangers / master / doctorat
        search_external_student_master,
        search_phd_admission,
        search_foreign_student_procedures,
        search_recognition_prior_learning,
        search_master_thesis_supervision,
        search_academic_partnership,
        search_international_equivalence,
        search_transfer_equivalence,

        # Documents et démarches
        search_student_card,
        search_internship_info,
        search_double_degree,
        search_reclamations,

        # Services et vie étudiante
        search_housing_and_services,
        search_scholarships,
        search_contacts_services,

        # Corps universitaire
        search_professeurs,
        search_organisation_corps_professoral,
        search_organisation_corps_estudiantin,
        search_reglement_interieur,

        # Mémoire utilisateur
        save_user_preference,
        get_user_preferences,
    ]

    # Ajouter les outils de base de données si disponible
    if _db_available:
        tools.extend([
            search_latest_news,
            get_schedules_from_db,
            search_student_record,
            search_statistics_uam,
        ])
    
    return tools



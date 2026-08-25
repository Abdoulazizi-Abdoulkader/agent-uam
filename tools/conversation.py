"""Outils de lecture du message : salutation, pertinence, profil, ressenti."""
import re
import unicodedata

from langchain_core.tools import tool

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

# BUG-07 : exception à la ligne 25 ci-dessus, pour la seule variante
# "étrangère" — un candidat qui se décrit lui-même (« je suis », « je
# viens », « mon diplôme vient ») comme venant d'une université étrangère
# n'est pas hors sujet, contrairement à une question où l'université
# étrangère est le sujet impersonnel de la phrase.
_SELF_ETUDIANT_ETRANGER_RE = re.compile(
    r"\b(je suis|je viens|mon dipl[ôo]me (vient|est issu))\b"
    r".{0,40}universit[eé].{0,20}[eé]trang[eè]re?\b"
)


def _sans_accents(texte: str) -> str:
    """Retire les signes diacritiques, sans toucher à la casse.

    La saisie sans accents est courante sur téléphone et sur clavier QWERTY :
    « Ou est la faculte ? » doit être comprise comme « Où est la faculté ? ».
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


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

    # BUG-07 : un candidat qui se décrit lui-même comme venant d'une
    # université étrangère (pour demander une inscription/équivalence à
    # l'UAM) ne doit pas être intercepté par _OFF_TOPIC_RE ci-dessous, qui
    # vise les questions où une université étrangère est le *sujet* (ex.
    # « frais à l'université française »), pas l'origine du locuteur.
    # Vérifié avant la boucle hors-sujet, sur la seule variante "étrangère"
    # concernée par la collision décrite dans l'audit.
    if _SELF_ETUDIANT_ETRANGER_RE.search(question_lower):
        return "PERTINENT"

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

    # BUG-05 (revue x4) : "relevé" (nom) recherché en mot entier, pluriel
    # optionnel, sur la forme désaccentuée. Couvre tout déterminant, la
    # forme nue et le pluriel ("les relevés", "ses relevés", "ce relevé",
    # "relevé disponible ?") sans liste à énumérer ni à tenir à jour.
    #
    # Ce choix est délibéré, tranché par le contrôleur après trois tours :
    # une liste fermée de tournures à déterminant (round 3) évite les faux
    # positifs mais rate des formulations réelles ("les relevés sont-ils
    # disponibles ?", "relevé svp") — un faux négatif éconduit une vraie
    # question, un faux positif ne fait au pire que répondre à côté. Le
    # motif générique accepte donc, en connaissance de cause, de reclasser
    # en PERTINENT des phrases sans rapport où "relevé" et le verbe
    # conjugué "relève"/"relèves" sont des homographes exacts après
    # désaccentuation ("releve" des deux côtés) — \b ne peut pas les
    # séparer, ce ne sont pas deux chaînes différentes. Dette inscrite et
    # détaillée en BUG-06 (rapport d'audit) : dernier tour sur ce mot-clé,
    # la dette restante est acceptée telle quelle.
    keywords_mot_entier = ["relevé"]
    for kw in keywords_mot_entier:
        if re.search(rf"\b{re.escape(_sans_accents(kw))}s?\b", question_sans_accents):
            return "PERTINENT"

    # Mots-clés porteurs de sens : sous-chaîne, pour couvrir les formes fléchies.
    keywords_uam = [
        "abdou moumouni",
        "faculté", "école", "institut", "formation", "filière",
        "inscription", "admission", "diplôme", "attestation",
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

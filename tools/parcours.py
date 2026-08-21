"""Outils des parcours d'entrée à l'UAM : master externe, doctorat, étudiants
étrangers, validation des acquis, encadrement de recherche et partenariats."""
from langchain_core.tools import tool

from context_tracker import push_text
from uam_structures import get_structure_info

from ._rag import _rag_search
from ._vectorstore import get_vectorstore


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
    if get_vectorstore() is None:
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
    if get_vectorstore() is None:
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
    if get_vectorstore() is None:
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
    if get_vectorstore() is None:
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
    if get_vectorstore() is None:
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
    if get_vectorstore() is None:
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

"""
Génère Memoire.docx à partir des fichiers markdown du mémoire M2 UAM.
Mise en forme académique : A4, Times New Roman 12pt, interligne 1.5, justifié.
"""

import os
import re
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "Memoire.docx")

# Mapping figure number -> fichier
FIGURE_MAP = {
    "1.1": "figure1-1.png",
    "1.2": "figure1-2.png",
    "1.3": "figure1-3.png",
    "2.1": "figure2-1.png",
    "2.2": "figure2-2.png",
    "2.3": "figure2-3.png",
    "2.4": "figure2-4.png",
    "3.1": "figure3-1.png",
    "3.4": "figure3-4.png",
    "3.5": "figure3-5.png",
    "4.1": "fig_4_1_keyword_recall.png",
    "4.2": "fig_4_2_latence.png",
    "4.3": "fig_4_3_confusion_routeur.png",
    "4.4": "fig_4_4_radar_eval_humaine.png",
    "4.5": "fig_4_5_comparaison.png",
}

FIGURE_CAPTIONS = {
    "1.1": "Évolution des architectures d'agents conversationnels",
    "1.2": "Pipeline Retrieval-Augmented Generation générique",
    "1.3": "Boucle ReAct : raisonnement et action",
    "2.1": "Architecture à trois couches du prototype",
    "2.2": "Graphe d'états du système",
    "2.3": "Pipeline RAG détaillé",
    "2.4": "Mécanisme de détection du profil utilisateur",
    "3.1": "Organisation modulaire du code",
    "3.4": "Schéma entité-relation de la base de scolarité",
    "3.5": "Diagramme de séquence d'exécution",
    "4.1": "Keyword Recall par catégorie",
    "4.2": "Distribution des latences",
    "4.3": "Matrice de confusion du routeur",
    "4.4": "Radar de l'évaluation humaine",
    "4.5": "Comparaison avec les travaux apparentés",
}

# Point d'insertion : figure insérée APRÈS avoir vu le titre de section indiqué
# Clé : numéro de section ; valeur : liste de figures à insérer après ce bloc
SECTION_FIGURES = {
    # Chapitre 1
    "1.1.4": ["1.1"],          # Après synthèse typologie
    "1.4.1": ["1.2"],          # Après principe RAG
    "1.5.1": ["1.3"],          # Après définition agents LLM
    # Chapitre 2
    "2.4.1": ["2.1"],          # Après vue d'ensemble architecture
    "2.4.2": ["2.2"],          # Après graphe d'états formel
    "2.4.3": ["2.3"],          # Après pipeline RAG
    "2.4.4": ["2.4"],          # Après détection profil
    # Chapitre 3
    "3.2.2": ["3.1"],          # Après organisation modules
    "3.10.2": ["3.4"],         # Après schéma BDD
    "3.12": ["3.5"],           # Après flux d'exécution complet
    # Chapitre 4
    "4.3.1": ["4.1"],          # Après keyword recall
    "4.3.3": ["4.2"],          # Après latence
    "4.4.3": ["4.3"],          # Après analyse routage
    "4.5.2": ["4.4"],          # Après éval humaine
    "4.7": ["4.5"],            # Après comparaison
}


def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn('w:tcBorders'))
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '808080')
        tcBorders.append(el)


def add_page_number(paragraph):
    run = paragraph.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.text = 'PAGE'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)


def setup_document():
    doc = Document()

    # Styles de base
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    pf = style.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_after = Pt(6)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Styles pour titres
    for level, size in [(1, 18), (2, 14), (3, 12), (4, 11)]:
        s = doc.styles[f'Heading {level}']
        s.font.name = 'Times New Roman'
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        s.paragraph_format.space_before = Pt(18 if level == 1 else 12)
        s.paragraph_format.space_after = Pt(8)
        s.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

    # Mise en page A4
    for section in doc.sections:
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(2.5)

    return doc


def add_cover_page(doc):
    s = doc.sections[0]
    # Numérotation de pages dans pied de page
    footer = s.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number(fp)

    # Logo / En-tête
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RÉPUBLIQUE DU NIGER")
    r.bold = True
    r.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Ministère de l'Enseignement Supérieur et de la Recherche")
    r.italic = True
    r.font.size = Pt(11)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("UNIVERSITÉ ABDOU MOUMOUNI DE NIAMEY")
    r.bold = True
    r.font.size = Pt(14)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Faculté des Sciences et Techniques")
    r.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Département de Mathématiques et Informatique")
    r.font.size = Pt(12)

    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("MÉMOIRE DE MASTER II")
    r.bold = True
    r.font.size = Pt(16)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Mention : Informatique")
    r.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Spécialité : Intelligence Artificielle et Systèmes d'Information")
    r.italic = True
    r.font.size = Pt(12)

    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("THÈME")
    r.bold = True
    r.font.size = Pt(13)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(12)
    pf.space_after = Pt(12)
    r = p.add_run(
        "Conception et évaluation d'un agent conversationnel agentique pour "
        "l'accès à l'information administrative universitaire : application "
        "aux procédures d'inscription à l'Université Abdou Moumouni de Niamey"
    )
    r.bold = True
    r.font.size = Pt(14)

    for _ in range(2):
        doc.add_paragraph()

    # Bloc auteur / superviseur
    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    left = tbl.cell(0, 0)
    right = tbl.cell(0, 1)

    p = left.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("Présenté et soutenu par :")
    r.bold = True
    left.add_paragraph("[Nom et Prénoms de l'étudiant]")

    p = right.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("Sous la direction de :")
    r.bold = True
    right.add_paragraph("[Directeur de mémoire]")
    right.add_paragraph("[Co-directeur / Encadrant]")

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Année universitaire 2025 – 2026")
    r.bold = True
    r.font.size = Pt(12)

    doc.add_page_break()


def add_toc_placeholder(doc):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("SOMMAIRE")
    r.bold = True
    r.font.size = Pt(16)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(
        "La table des matières automatique peut être générée dans Word "
        "via : Références → Table des matières → Table automatique. "
        "Les styles « Titre 1 » et « Titre 2 » appliqués aux sections de "
        "ce mémoire permettent la génération automatique."
    )
    r.italic = True

    # Insertion d'un champ TOC
    p = doc.add_paragraph()
    run = p.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    fldChar3 = OxmlElement('w:t')
    fldChar3.text = "Mettez à jour la table des matières dans Word (F9)."
    fldChar4 = OxmlElement('w:fldChar')
    fldChar4.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)
    run._r.append(fldChar4)

    doc.add_page_break()


def add_dedicace(doc):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("DÉDICACE")
    r.bold = True
    r.font.size = Pt(16)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("À ma famille,\npour son soutien indéfectible tout au long de ce parcours.")
    r.italic = True
    r.font.size = Pt(12)
    doc.add_page_break()


def add_remerciements(doc):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("REMERCIEMENTS")
    r.bold = True
    r.font.size = Pt(16)
    doc.add_paragraph()
    txt = (
        "Je tiens à adresser mes sincères remerciements à l'ensemble des personnes "
        "qui ont contribué, de près ou de loin, à la réalisation de ce travail de "
        "recherche.\n\n"
        "Mes remerciements les plus chaleureux vont à mon directeur de mémoire, "
        "pour sa disponibilité, ses conseils avisés et la rigueur scientifique qui "
        "ont jalonné ce parcours. Je remercie également les enseignants du "
        "Département de Mathématiques et Informatique de la Faculté des Sciences "
        "et Techniques de l'Université Abdou Moumouni de Niamey pour la qualité "
        "de la formation dispensée.\n\n"
        "Je suis reconnaissant aux personnels administratifs de l'Université "
        "Abdou Moumouni qui ont accepté de partager leur expertise sur les "
        "procédures d'inscription, ainsi qu'aux étudiants ayant participé "
        "aux tests utilisateurs du prototype.\n\n"
        "Enfin, j'exprime ma profonde gratitude à ma famille et à mes amis pour "
        "leur soutien moral constant durant ces années d'études."
    )
    for para in txt.split("\n\n"):
        p = doc.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    doc.add_page_break()


def add_resume(doc):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("RÉSUMÉ")
    r.bold = True
    r.font.size = Pt(16)
    doc.add_paragraph()

    fr = (
        "Ce mémoire présente la conception, l'implémentation et l'évaluation d'un "
        "agent conversationnel destiné à faciliter l'accès à l'information "
        "administrative de l'Université Abdou Moumouni de Niamey, avec un accent "
        "particulier sur les procédures d'inscription. L'architecture proposée "
        "combine un pipeline Retrieval-Augmented Generation (RAG) — fondé sur des "
        "embeddings multilingues et un index vectoriel FAISS — avec un graphe "
        "d'états LangGraph orchestrant un routage conditionnel, une boucle "
        "réactive (ReAct) et quarante-sept outils spécialisés invocables "
        "dynamiquement par le LLM. Le prototype intègre en outre un accès "
        "sécurisé en lecture seule à une base de données relationnelle simulant "
        "le système de gestion de la scolarité. L'évaluation, conduite sur un "
        "jeu de trente-quatre cas de test répartis en neuf catégories, combine "
        "des métriques automatiques (keyword recall, taux d'ancrage factuel, "
        "latence) et une évaluation humaine sur quatre critères (exactitude, "
        "complétude, clarté, utilité). Les résultats obtenus permettent de "
        "discuter les trois hypothèses formulées : niveau d'ancrage factuel, "
        "pertinence contextuelle et validité du protocole hybride d'évaluation."
    )
    p = doc.add_paragraph(fr)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p = doc.add_paragraph()
    r = p.add_run("Mots-clés : ")
    r.bold = True
    p.add_run(
        "Agent conversationnel, RAG, LangGraph, LLM, Université Abdou "
        "Moumouni, ReAct, FAISS, embeddings multilingues, évaluation "
        "d'agents conversationnels."
    )

    doc.add_paragraph()
    h = doc.add_paragraph()
    r = h.add_run("ABSTRACT")
    r.bold = True
    r.font.size = Pt(13)

    en = (
        "This thesis presents the design, implementation and evaluation of a "
        "conversational agent aimed at facilitating access to administrative "
        "information at Université Abdou Moumouni of Niamey, with a particular "
        "focus on enrollment procedures. The proposed architecture combines a "
        "Retrieval-Augmented Generation (RAG) pipeline — based on multilingual "
        "embeddings and a FAISS vector index — with a LangGraph state graph "
        "orchestrating conditional routing, a reactive (ReAct) loop and forty-"
        "seven specialized tools dynamically invoked by the LLM. The prototype "
        "also integrates a secure read-only access to a relational database "
        "simulating the academic registry. The evaluation, conducted on a "
        "dataset of thirty-four test cases across nine categories, combines "
        "automatic metrics (keyword recall, factual grounding rate, latency) "
        "with a human evaluation on four criteria (accuracy, completeness, "
        "clarity, usefulness). The results obtained allow to discuss the three "
        "hypotheses formulated: factual grounding level, contextual relevance, "
        "and validity of the hybrid evaluation protocol."
    )
    p = doc.add_paragraph(en)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p = doc.add_paragraph()
    r = p.add_run("Keywords: ")
    r.bold = True
    p.add_run(
        "Conversational agent, RAG, LangGraph, LLM, Abdou Moumouni "
        "University, ReAct, FAISS, multilingual embeddings, chatbot evaluation."
    )

    doc.add_page_break()


def add_abbreviations(doc):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("LISTE DES ABRÉVIATIONS ET SIGLES")
    r.bold = True
    r.font.size = Pt(14)
    doc.add_paragraph()

    rows = [
        ("API", "Application Programming Interface"),
        ("BERT", "Bidirectional Encoder Representations from Transformers"),
        ("BDD", "Base De Données"),
        ("CLI", "Command Line Interface"),
        ("DOCX", "Document Office Open XML"),
        ("ECTS", "European Credits Transfer System"),
        ("ENA", "École Nationale d'Administration"),
        ("ENS", "École Normale Supérieure"),
        ("FA", "Faculté d'Agronomie"),
        ("FAISS", "Facebook AI Similarity Search"),
        ("FAST", "Faculté des Sciences et Techniques"),
        ("FLSH", "Faculté des Lettres et Sciences Humaines"),
        ("FSEG", "Faculté des Sciences Économiques et de Gestion"),
        ("FSJP", "Faculté des Sciences Juridiques et Politiques"),
        ("FSS", "Faculté des Sciences Sociales"),
        ("GPT", "Generative Pre-trained Transformer"),
        ("IA", "Intelligence Artificielle"),
        ("IRIM", "Institut de Radiologie et Imagerie Médicale"),
        ("LLM", "Large Language Model"),
        ("LMD", "Licence-Master-Doctorat"),
        ("LSTM", "Long Short-Term Memory"),
        ("NLG", "Natural Language Generation"),
        ("NLU", "Natural Language Understanding"),
        ("PDF", "Portable Document Format"),
        ("RAG", "Retrieval-Augmented Generation"),
        ("RAGAS", "Retrieval-Augmented Generation Assessment"),
        ("ReAct", "Reasoning and Acting"),
        ("RLHF", "Reinforcement Learning from Human Feedback"),
        ("SQL", "Structured Query Language"),
        ("SUS", "System Usability Scale"),
        ("TALN", "Traitement Automatique du Langage Naturel"),
        ("UAM", "Université Abdou Moumouni de Niamey"),
        ("UE", "Unité d'Enseignement"),
        ("UUID", "Universally Unique Identifier"),
        ("WAL", "Write-Ahead Logging"),
    ]
    tbl = doc.add_table(rows=len(rows), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.columns[0].width = Cm(3.5)
    tbl.columns[1].width = Cm(12.0)
    for i, (abbr, defn) in enumerate(rows):
        c0 = tbl.cell(i, 0)
        c0.width = Cm(3.5)
        p = c0.paragraphs[0]
        r = p.add_run(abbr)
        r.bold = True
        c1 = tbl.cell(i, 1)
        c1.width = Cm(12.0)
        c1.paragraphs[0].add_run(defn)
    doc.add_page_break()


# ────────────────────────── parsing markdown ──────────────────────

HEADING_RE = re.compile(r'^(\d+(?:\.\d+)*\.?)\s+(.+)$')
FIGURE_TAG_RE = re.compile(r'Figure\s+(\d+\.\d+)', re.IGNORECASE)
TABLE_TAG_RE = re.compile(r'^Tableau\s+\d+\.\d+\s*[—-]', re.IGNORECASE)


def strip_md_inline(text):
    # Gras **x** / italique *x* / code `x`
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text


def add_run_with_bold(paragraph, text):
    """Ajoute du texte dans un paragraphe en conservant **gras** et *italique*."""
    # Tokenize en préservant gras et italique
    pattern = re.compile(r'(\*\*[^\*]+\*\*|\*[^\*]+\*|`[^`]+`)')
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        tok = m.group()
        if tok.startswith('**') and tok.endswith('**'):
            r = paragraph.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith('`') and tok.endswith('`'):
            r = paragraph.add_run(tok[1:-1])
            r.font.name = 'Consolas'
            r.font.size = Pt(10)
        elif tok.startswith('*') and tok.endswith('*'):
            r = paragraph.add_run(tok[1:-1]); r.italic = True
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def insert_figure(doc, num):
    path = os.path.join(FIG_DIR, FIGURE_MAP[num])
    if not os.path.exists(path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    try:
        r.add_picture(path, width=Cm(15))
    except Exception as e:
        print(f"  ⚠ image error {num}: {e}")
        return
    # Légende
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run(f"Figure {num} — {FIGURE_CAPTIONS.get(num, '')}")
    cr.bold = True
    cr.italic = True
    cr.font.size = Pt(10)


def parse_table_block(lines, start):
    """Parse un bloc de tableau markdown débutant à start. Retourne (rows, end)."""
    rows = []
    i = start
    while i < len(lines) and lines[i].lstrip().startswith('|'):
        row = lines[i].strip()
        # Séparateur |---|---|
        if re.match(r'^\|[\s\-:|]+\|$', row):
            i += 1
            continue
        cells = [c.strip() for c in row.strip('|').split('|')]
        rows.append(cells)
        i += 1
    return rows, i


def add_table(doc, rows):
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = 'Table Grid'
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = tbl.cell(i, j)
            text = row[j] if j < len(row) else ""
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.space_after = Pt(2)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            add_run_with_bold(p, text)
            for run in p.runs:
                run.font.size = Pt(10)
                if i == 0:
                    run.bold = True
            if i == 0:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto')
                shd.set(qn('w:fill'), 'DCE6F1')
                tcPr.append(shd)
    # Espacement après
    doc.add_paragraph()


def process_markdown(doc, md_text, is_intro=False):
    lines = md_text.split('\n')
    # Supprimer ligne de titre (premier titre) — remplacée par add_chapter_title
    # mais pour INTRODUCTION, ajouter comme heading1
    if is_intro:
        first_heading_added = False
    else:
        first_heading_added = False  # on skippe le titre du chapitre (géré à l'extérieur)

    i = 0
    skip_first_title = not is_intro
    first_line_processed = False
    in_code = False
    code_buf = []
    in_references = False
    # Mémoire des sections visitées pour insérer les figures une seule fois
    inserted_sections = set()
    # Contexte : quelle section courante pour insertion différée
    pending_figure_section = None

    while i < len(lines):
        line = lines[i]
        raw = line
        stripped = line.strip()

        # Début/fin de bloc de code
        if stripped.startswith('```'):
            if in_code:
                # fin
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.left_indent = Cm(0.5)
                pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
                pf.space_after = Pt(6)
                for cl in code_buf:
                    r = p.add_run(cl + '\n')
                    r.font.name = 'Consolas'
                    r.font.size = Pt(9)
                # bordure gauche
                pPr = p._p.get_or_add_pPr()
                pBdr = OxmlElement('w:pBdr')
                left = OxmlElement('w:left')
                left.set(qn('w:val'), 'single')
                left.set(qn('w:sz'), '12')
                left.set(qn('w:space'), '8')
                left.set(qn('w:color'), '4472C4')
                pBdr.append(left)
                pPr.append(pBdr)
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto')
                shd.set(qn('w:fill'), 'F5F5F5')
                pPr.append(shd)
                in_code = False
                code_buf = []
            else:
                in_code = True
                code_buf = []
            i += 1
            continue
        if in_code:
            code_buf.append(raw)
            i += 1
            continue

        # Ligne vide
        if not stripped:
            i += 1
            continue

        # Premier titre (à skipper pour les chapitres : déjà ajouté comme H1)
        if not first_line_processed:
            first_line_processed = True
            if skip_first_title:
                # Skipper aussi lignes suivantes jusqu'à la première section
                i += 1
                continue
            else:
                # Introduction générale : titre comme H1
                h = doc.add_heading(stripped.upper(), level=1)
                h.alignment = WD_ALIGN_PARAGRAPH.CENTER
                i += 1
                continue

        # Section "Références" à la fin
        if stripped.lower().startswith('références') or stripped.lower() == 'références':
            # Flusher les figures en attente
            if pending_figure_section and pending_figure_section in SECTION_FIGURES:
                for fnum in SECTION_FIGURES[pending_figure_section]:
                    if fnum not in inserted_sections:
                        insert_figure(doc, fnum)
                        inserted_sections.add(fnum)
                pending_figure_section = None
            in_references = True
            h = doc.add_heading("Références bibliographiques", level=2)
            i += 1
            continue

        if in_references:
            # Chaque ligne non vide est une référence
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.left_indent = Cm(1.0)
            pf.first_line_indent = Cm(-1.0)
            pf.space_after = Pt(4)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            add_run_with_bold(p, strip_md_inline(stripped))
            for r in p.runs:
                r.font.size = Pt(11)
            i += 1
            continue

        # Tableau
        if stripped.startswith('|'):
            rows, end = parse_table_block(lines, i)
            add_table(doc, rows)
            i = end
            continue

        # Légende "Tableau X.Y — ..." : déjà affichée en paragraphe gras centré
        if TABLE_TAG_RE.match(stripped):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = p.paragraph_format
            pf.space_before = Pt(6)
            pf.space_after = Pt(4)
            r = p.add_run(strip_md_inline(stripped))
            r.bold = True
            r.italic = True
            r.font.size = Pt(10)
            i += 1
            continue

        # Légende "Figure X.Y — ..." : insérer l'image correspondante
        mfig = FIGURE_TAG_RE.match(stripped)
        if mfig and stripped.lower().startswith('figure '):
            num = mfig.group(1)
            # Vérifier que c'est bien une ligne de légende (contient "—" ou "-")
            if '—' in stripped or ' - ' in stripped:
                if num in FIGURE_MAP:
                    insert_figure(doc, num)
                    i += 1
                    continue

        # Détection de heading numéroté (1., 1.1., 1.1.1.)
        mh = HEADING_RE.match(stripped)
        if mh:
            num = mh.group(1).rstrip('.')
            title = mh.group(2).strip()
            # Insérer les figures en attente (avant le nouveau heading)
            if pending_figure_section and pending_figure_section in SECTION_FIGURES:
                for fnum in SECTION_FIGURES[pending_figure_section]:
                    if fnum not in inserted_sections:
                        insert_figure(doc, fnum)
                        inserted_sections.add(fnum)
                pending_figure_section = None
            depth = num.count('.') + 1
            level = min(depth, 4)
            # H1 est réservé au titre du chapitre → décaler
            h = doc.add_heading(f"{num}. {title}", level=level + 1 if level == 1 else level)
            h.paragraph_format.keep_with_next = True
            # Mémoriser cette section comme candidate à l'insertion de figure
            if num in SECTION_FIGURES:
                pending_figure_section = num
            i += 1
            continue

        # Ligne de liste "-" ou "•"
        if stripped.startswith(('- ', '• ', '*   ', '*\t')):
            txt = stripped[2:].strip() if stripped.startswith(('- ', '• ')) else stripped.lstrip('*').strip()
            # Nettoyage tab séparateur
            txt = re.sub(r'^[\-•]\s*', '', txt)
            p = doc.add_paragraph(style='List Bullet')
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_run_with_bold(p, strip_md_inline(txt))
            i += 1
            continue

        # Liste ordonnée "(1)", "(a)", "1.":
        if re.match(r'^\(\w+\)\s', stripped) or re.match(r'^\d+\)\s', stripped):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf = p.paragraph_format
            pf.left_indent = Cm(0.8)
            add_run_with_bold(p, strip_md_inline(stripped))
            i += 1
            continue

        # Citation > ...
        if stripped.startswith('> '):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf = p.paragraph_format
            pf.left_indent = Cm(1.0)
            pf.right_indent = Cm(0.5)
            add_run_with_bold(p, strip_md_inline(stripped[2:]))
            for r in p.runs:
                r.italic = True
            i += 1
            continue

        # Regrouper paragraphes (lignes consécutives sans ligne vide)
        para_lines = [stripped]
        j = i + 1
        while j < len(lines):
            ns = lines[j].strip()
            if not ns: break
            if ns.startswith(('|', '```', '- ', '• ', '> ')): break
            if HEADING_RE.match(ns): break
            if TABLE_TAG_RE.match(ns): break
            if ns.lower().startswith('figure '): break
            para_lines.append(ns)
            j += 1
        full = ' '.join(para_lines)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0.8)
        add_run_with_bold(p, strip_md_inline(full))
        i = j


def add_chapter_title(doc, chapter_num, title):
    doc.add_page_break()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(36)
    pf.space_after = Pt(6)
    r = p.add_run(f"CHAPITRE {chapter_num}")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    h = doc.add_heading(title, level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h.paragraph_format.space_after = Pt(24)


def main():
    print("Génération de Memoire.docx ...")
    doc = setup_document()

    add_cover_page(doc)
    add_dedicace(doc)
    add_remerciements(doc)
    add_resume(doc)
    add_abbreviations(doc)
    add_toc_placeholder(doc)

    # Introduction générale
    print("  → Introduction générale")
    doc.add_page_break()
    with open(os.path.join(ROOT, "INTRODUCTION GÉNÉRALE.md"), encoding='utf-8') as f:
        txt = f.read()
    process_markdown(doc, txt, is_intro=True)

    # Chapitres
    chapters = [
        (1, "CHAPITRE 1.md", "Cadre théorique et état de l'art"),
        (2, "CHAPITRE 2.md", "Analyse du domaine et conception de l'architecture"),
        (3, "CHAPITRE 3.md", "Réalisation technique du prototype"),
        (4, "CHAPITRE 4.md", "Résultats expérimentaux et évaluation"),
        (5, "CHAPITRE 5.md", "Conclusion générale et perspectives"),
    ]
    for num, fn, title in chapters:
        print(f"  → Chapitre {num}")
        add_chapter_title(doc, num, title)
        with open(os.path.join(ROOT, fn), encoding='utf-8') as f:
            txt = f.read()
        # Nettoyage : supprimer le bloc de duplicata (chapitre 2) encadré par "" """
        # Supprimer tout ce qui se trouve entre les triples guillemets de duplication
        txt = re.sub(r'""[^"]*""', '', txt, flags=re.DOTALL)
        process_markdown(doc, txt, is_intro=False)

    doc.save(OUT)
    print(f"✓ Généré : {OUT}")
    print(f"  Taille : {os.path.getsize(OUT) // 1024} Ko")


if __name__ == "__main__":
    main()

"""
Utilitaires pour l'export des conversations en PDF et JSON
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER


def export_to_json(conversations: List[Dict], user_id: str, preferences: Optional[Dict] = None, output_path: str = None) -> str:
    """
    Exporte les conversations en format JSON
    
    Args:
        conversations: Liste des conversations
        user_id: ID de l'utilisateur
        preferences: Préférences utilisateur (optionnel)
        output_path: Chemin de sortie (optionnel)
    
    Returns:
        Chemin du fichier JSON créé
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"exports/uam_conversation_{timestamp}.json"
    
    # Créer le dossier exports s'il n'existe pas
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    export_data = {
        "user_id": user_id,
        "export_date": datetime.now().isoformat(),
        "conversations": conversations,
        "preferences": preferences or {},
        "total_conversations": len(conversations)
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    return output_path


def export_to_pdf(conversations: List[Dict], user_id: str, preferences: Optional[Dict] = None, output_path: str = None) -> str:
    """
    Exporte les conversations en format PDF
    
    Args:
        conversations: Liste des conversations
        user_id: ID de l'utilisateur
        preferences: Préférences utilisateur (optionnel)
        output_path: Chemin de sortie (optionnel)
    
    Returns:
        Chemin du fichier PDF créé
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"exports/uam_conversation_{timestamp}.pdf"
    
    # Créer le dossier exports s'il n'existe pas
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Créer le document PDF
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor='#1f77b4',
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#333333',
        spaceAfter=12,
        spaceBefore=12
    )
    
    normal_style = styles['Normal']
    user_style = ParagraphStyle(
        'UserMessage',
        parent=styles['Normal'],
        fontSize=10,
        textColor='#1565c0',
        leftIndent=20,
        spaceAfter=6
    )
    
    assistant_style = ParagraphStyle(
        'AssistantMessage',
        parent=styles['Normal'],
        fontSize=10,
        textColor='#424242',
        leftIndent=20,
        spaceAfter=6
    )
    
    # Titre
    story.append(Paragraph("Agent Conversationnel UAM", title_style))
    story.append(Paragraph("Université Abdou Moumouni de Niamey", styles['Heading2']))
    story.append(Spacer(1, 0.2*inch))
    
    # Informations de l'export
    story.append(Paragraph(f"<b>Date d'export:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", normal_style))
    story.append(Paragraph(f"<b>ID Utilisateur:</b> {user_id}", normal_style))
    story.append(Paragraph(f"<b>Nombre de conversations:</b> {len(conversations)}", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Préférences utilisateur
    if preferences:
        story.append(Paragraph("Préférences Utilisateur", heading_style))
        prefs_text = json.dumps(preferences, ensure_ascii=False, indent=2)
        story.append(Paragraph(f"<pre>{prefs_text}</pre>", normal_style))
        story.append(Spacer(1, 0.2*inch))
    
    # Conversations
    story.append(Paragraph("Historique des Conversations", heading_style))
    
    for idx, conv in enumerate(conversations, 1):
        # Question
        question = conv.get("question", "")
        timestamp = conv.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                timestamp_str = timestamp
        else:
            timestamp_str = ""
        
        story.append(Paragraph(f"<b>Conversation {idx}</b> - {timestamp_str}", heading_style))
        story.append(Paragraph(f"<b>👤 Question:</b>", normal_style))
        story.append(Paragraph(question.replace('\n', '<br/>'), user_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Réponse
        response = conv.get("response", "")
        story.append(Paragraph(f"<b>🤖 Réponse:</b>", normal_style))
        story.append(Paragraph(response.replace('\n', '<br/>'), assistant_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Saut de page tous les 3 conversations
        if idx % 3 == 0 and idx < len(conversations):
            story.append(PageBreak())
    
    # Footer
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        f"<i>Généré par l'Agent Conversationnel UAM - {datetime.now().strftime('%d/%m/%Y')}</i>",
        styles['Italic']
    ))
    
    # Construire le PDF
    doc.build(story)
    
    return output_path


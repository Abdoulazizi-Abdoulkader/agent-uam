"""
Canal WhatsApp — WhatsApp Business Cloud API (Meta, Graph API v21.0).

Trois responsabilités : vérifier l'authenticité des webhooks reçus, en extraire
le message utilisateur, et renvoyer la réponse de l'agent.

Configuration (.env) :
    WHATSAPP_VERIFY_TOKEN=...      # chaîne libre, à recopier dans la console Meta
    WHATSAPP_ACCESS_TOKEN=...      # token de l'app (temporaire : 24 h)
    WHATSAPP_PHONE_NUMBER_ID=...   # identifiant du numéro expéditeur
    WHATSAPP_APP_SECRET=...        # secret de l'app, pour valider les signatures
"""
import hashlib
import hmac
import os
import re
from typing import List, Optional, Tuple

from logger_config import get_logger

logger = get_logger(__name__)

GRAPH_API_VERSION = "v21.0"
# Limite d'un message WhatsApp ; on découpe au-delà.
MAX_MESSAGE_LENGTH = 4000


def is_configured() -> bool:
    """Indique si les identifiants WhatsApp sont présents."""
    return bool(os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID"))


def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Valide l'en-tête X-Hub-Signature-256 envoyé par Meta.

    Sans app secret configuré, la vérification est désactivée (mode démo local).
    """
    app_secret = os.getenv("WHATSAPP_APP_SECRET")
    if not app_secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.split("=", 1)[1])


def extract_incoming_message(payload: dict) -> Optional[Tuple[str, str, str]]:
    """Extrait (message_id, numéro, texte) d'un webhook Meta.

    Retourne None pour tout ce qui n'est pas un message texte entrant —
    notamment les notifications de statut (envoyé / distribué / lu), qui
    représentent la majorité des appels reçus.
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return None

    messages = value.get("messages")
    if not messages:
        return None

    message = messages[0]
    if message.get("type") != "text":
        return None

    text = message.get("text", {}).get("body", "").strip()
    if not text:
        return None

    return message.get("id", ""), message.get("from", ""), text


def to_whatsapp_format(text: str) -> str:
    """Convertit le markdown produit par le LLM au formatage WhatsApp.

    WhatsApp utilise *gras*, _italique_ et ne connaît ni les titres ni les liens
    markdown.
    """
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)   # titres
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text, flags=re.S)   # **gras** -> *gras*
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)  # [texte](url)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)  # puces
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Découpe un texte long en plusieurs messages, sur les sauts de paragraphe."""
    if len(text) <= limit:
        return [text]

    chunks, current = [], ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # Paragraphe seul trop long : découpage brut
            while len(paragraph) > limit:
                chunks.append(paragraph[:limit])
                paragraph = paragraph[limit:]
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def send_message(to_number: str, text: str) -> bool:
    """Envoie un message texte via l'API Cloud de Meta.

    Returns:
        True si tous les fragments ont été acceptés par l'API.
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not access_token or not phone_number_id:
        logger.error("WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID manquants.")
        return False

    import httpx

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}

    ok = True
    with httpx.Client(timeout=30.0) as client:
        for chunk in split_message(to_whatsapp_format(text)):
            response = client.post(
                url,
                headers=headers,
                json={
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": "text",
                    "text": {"preview_url": False, "body": chunk},
                },
            )
            if response.status_code >= 400:
                logger.error(f"Envoi WhatsApp refusé ({response.status_code}) : {response.text}")
                ok = False
                break
    return ok

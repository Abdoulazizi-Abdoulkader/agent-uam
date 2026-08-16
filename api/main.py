"""
Serveur web de l'agent UAM.

Expose trois choses :
  • le site institutionnel de l'UAM avec l'assistant intégré (GET /)
  • l'API de conversation utilisée par le widget de chat (POST /api/chat)
  • le webhook WhatsApp Business Cloud API (GET/POST /webhook/whatsapp)

Lancement : ./run_api.sh  (ou : uvicorn api.main:app --port 8000)
"""
import json
import os
import sys
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
from fastapi import BackgroundTasks, FastAPI, Request, Response  # noqa: E402
from fastapi.responses import (  # noqa: E402
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

load_dotenv()

from api import site_data  # noqa: E402
from api.agent_service import answer, answer_stream, get_agent  # noqa: E402
from api.whatsapp import (  # noqa: E402
    extract_incoming_message,
    is_configured as whatsapp_is_configured,
    send_message,
    verify_signature,
)
from logger_config import get_logger  # noqa: E402

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

# Messages WhatsApp déjà traités — Meta rejoue les webhooks non acquittés à temps,
# sans cette déduplication l'utilisateur reçoit des réponses en double.
_seen_messages: "OrderedDict[str, None]" = OrderedDict()
_SEEN_MAX = 500


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge l'agent et le contenu du site avant d'accepter du trafic."""
    logger.info("Démarrage du serveur UAM…")
    site_data.warmup()
    get_agent()  # ~5-12 s : modèle d'embeddings + index FAISS
    logger.info("Serveur prêt.")
    yield
    logger.info("Arrêt du serveur UAM.")


app = FastAPI(title="Université Abdou Moumouni — Assistant", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


# ==================== SITE WEB ====================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Page d'accueil du site institutionnel."""
    return templates.TemplateResponse(request, "index.html", site_data.get_site_context())


@app.get("/health")
def health():
    """État du service."""
    return {
        "status": "ok",
        "composantes": len(site_data.get_composantes()),
        "formations": len(site_data.get_formations()),
        "whatsapp": whatsapp_is_configured(),
    }


# ==================== API DE CONVERSATION ====================

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1, max_length=128)


@app.post("/api/chat/stream")
def chat_stream(payload: ChatRequest):
    """Même chose que /api/chat, mais en Server-Sent Events.

    Le temps total est identique ; ce qui change est le délai avant les premiers
    mots. Le générateur est synchrone : FastAPI l'itère dans son pool de threads,
    comme il le fait pour les handlers `def`.
    """
    def evenements():
        try:
            for evenement in answer_stream(payload.question, session_id=payload.session_id):
                yield f"data: {json.dumps(evenement, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error(f"Flux interrompu : {exc}", exc_info=True)
            erreur = {"type": "erreur", "message": "La réponse a été interrompue."}
            yield f"data: {json.dumps(erreur, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        evenements(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # empêche nginx de tamponner le flux
        },
    )


@app.post("/api/chat")
def chat(payload: ChatRequest):
    """Pose une question à l'agent.

    Handler synchrone volontairement : le graphe LangGraph est bloquant, FastAPI
    l'exécute donc dans son pool de threads. En `async def`, une seule question
    figerait la boucle d'événements et tout le site avec elle.
    """
    result = answer(payload.question, session_id=payload.session_id)
    return JSONResponse(
        {
            "response": result.response,
            "sources": result.sources,
            "elapsed_ms": result.elapsed_ms,
        }
    )


# ==================== WEBHOOK WHATSAPP ====================

@app.get("/webhook/whatsapp")
def whatsapp_verify(request: Request):
    """Vérification du webhook par Meta (échange du challenge)."""
    params = request.query_params
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    if not expected:
        logger.warning("WHATSAPP_VERIFY_TOKEN non configuré — vérification refusée.")
        return PlainTextResponse("Webhook non configuré", status_code=403)

    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == expected:
        logger.info("Webhook WhatsApp vérifié par Meta.")
        return PlainTextResponse(params.get("hub.challenge", ""))

    logger.warning("Échec de vérification du webhook WhatsApp (token invalide).")
    return PlainTextResponse("Forbidden", status_code=403)


def _handle_whatsapp_message(from_number: str, text: str) -> None:
    """Traite un message WhatsApp en arrière-plan puis renvoie la réponse."""
    try:
        # Le thread_id LangGraph est un identifiant libre : le numéro suffit à
        # donner une conversation persistante à chaque contact.
        result = answer(text, session_id=f"whatsapp:{from_number}", with_sources=False)
        if send_message(from_number, result.response):
            logger.info(f"Réponse WhatsApp envoyée à {from_number} ({result.elapsed_ms} ms)")
        else:
            logger.error(
                f"Réponse générée en {result.elapsed_ms} ms mais non remise à {from_number}."
            )
    except Exception as exc:
        logger.error(f"Échec du traitement WhatsApp pour {from_number} : {exc}", exc_info=True)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    """Réception des messages WhatsApp.

    Répond 200 immédiatement et traite en arrière-plan : Meta impose un délai
    d'acquittement court alors qu'une réponse de l'agent prend plusieurs secondes.
    """
    raw_body = await request.body()

    if not verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        logger.warning("Signature WhatsApp invalide — requête rejetée.")
        return Response(status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    message = extract_incoming_message(payload)
    if message is None:
        # Notification de statut (envoyé / distribué / lu) — rien à faire.
        return Response(status_code=200)

    message_id, from_number, text = message

    if message_id in _seen_messages:
        logger.info(f"Message WhatsApp {message_id} déjà traité — ignoré.")
        return Response(status_code=200)
    _seen_messages[message_id] = None
    if len(_seen_messages) > _SEEN_MAX:
        _seen_messages.popitem(last=False)

    logger.info(f"Message WhatsApp reçu de {from_number} : {text[:80]}")
    background.add_task(_handle_whatsapp_message, from_number, text)
    return Response(status_code=200)

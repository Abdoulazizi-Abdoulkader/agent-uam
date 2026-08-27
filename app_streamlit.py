"""
Interface Streamlit — Agent Conversationnel UAM
Design moderne avec chat natif, écran d'accueil et questions suggérées
"""

import streamlit as st
import uuid
import json
import os
import time
from datetime import datetime
from pathlib import Path
import sys
from langchain_core.messages import HumanMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.append(str(Path(__file__).parent))

from agent_uam import (
    initialize_llm,
    LLMProvider,
    load_and_index_documents,
    create_agent_graph,
    _user_memory,
)
from tools import set_session_user_id
from multi_agents import create_multi_agent_graph
from export_utils import export_to_pdf
from app_config import get_config
from metrics import record_question, get_metrics_summary, get_top_questions

# ─── Configuration page ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Assistant UAM",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Variables ── */
:root {
    --green-dark:  #1B5E20;
    --green-mid:   #2E7D32;
    --green-light: #4CAF50;
    --gold:        #F9A825;
    --surface:     #FFFFFF;
    --bg:          #F4F6F8;
}

/* ── Header principal ── */
.uam-header {
    background: linear-gradient(135deg, var(--green-dark) 0%, var(--green-mid) 70%, #388E3C 100%);
    padding: 1.4rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    box-shadow: 0 4px 18px rgba(27,94,32,0.18);
}
.uam-header-text h1 {
    color: white;
    margin: 0 0 2px 0;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.5px;
}
.uam-header-text p {
    color: rgba(255,255,255,0.82);
    margin: 0;
    font-size: 0.88rem;
}
.uam-logo { font-size: 3.2rem; line-height: 1; }

/* ── Badge de statut ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 0.76rem;
    font-weight: 600;
    margin-top: 6px;
}
.badge-on  { background: rgba(255,255,255,0.18); color: #fff; border: 1px solid rgba(255,255,255,0.35); }
.badge-off { background: rgba(0,0,0,0.12);       color: rgba(255,255,255,0.7); border: 1px solid rgba(255,255,255,0.15); }

/* ── Cards de bienvenue ── */
.feat-card {
    background: white;
    border: 1px solid #E8EAED;
    border-radius: 12px;
    padding: 1.2rem 1rem;
    text-align: center;
    height: 100%;
    transition: transform .18s, box-shadow .18s;
}
.feat-card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.09); }
.feat-card .fi   { font-size: 2.1rem; }
.feat-card h4    { color: var(--green-dark); margin: .55rem 0 .3rem; font-size: .92rem; font-weight: 600; }
.feat-card p     { color: #6B7280; font-size: .8rem; margin: 0; line-height: 1.4; }

/* ── Boutons suggestions ── */
div[data-testid="stButton"] > button {
    border-radius: 20px;
    font-size: 0.83rem;
    padding: .35rem .9rem;
    transition: background .15s, color .15s;
}

/* ── Temps de réponse ── */
.rt { font-size: .72rem; color: #9CA3AF; margin-top: 2px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div { background: #FAFBFC; }
</style>
""", unsafe_allow_html=True)

# ─── Constantes ───────────────────────────────────────────────────────────────
OPENROUTER_MODELS = {
    "GPT-4o mini":                    "openai/gpt-4o-mini",
    "Claude Sonnet 3.7":              "anthropic/claude-3.7-sonnet",
    "Llama 3.3 70B":                  "meta-llama/llama-3.3-70b-instruct",
    "GPT-4o":                         "openai/gpt-4o",
    "Gemma 3 27B — GRATUIT":          "google/gemma-3-27b-it:free",
    "Llama 3.1 8B — GRATUIT":         "meta-llama/llama-3.1-8b-instruct:free",
    "Mistral 7B — GRATUIT":           "mistralai/mistral-7b-instruct:free",
    "DeepSeek R1 — GRATUIT":          "deepseek/deepseek-r1:free",
}

DEFAULT_MODEL = "openai/gpt-4o-mini"

FEATURES = [
    ("📋", "Facultés & Instituts",   "Toutes les structures de l'UAM et leurs filières"),
    ("📝", "Admissions",             "Conditions d'accès et procédures d'inscription"),
    ("💰", "Frais & Bourses",        "Frais de scolarité et aides financières"),
    ("🗓️", "Calendrier académique",  "Dates importantes et délais d'inscription"),
    ("🏠", "Vie étudiante",          "Logement, restauration et services campus"),
    ("📞", "Contacts & Services",    "Secrétariats et services administratifs"),
]

SUGGESTED = [
    "Quelles sont les facultés de l'UAM ?",
    "Comment s'inscrire à l'UAM ?",
    "Quels sont les frais de scolarité ?",
    "Quelles formations sont disponibles à la FAST ?",
    "Comment obtenir une attestation de scolarité ?",
    "Quelles sont les conditions d'admission en master ?",
]

# ─── Session state ─────────────────────────────────────────────────────────────
def _init():
    defaults = {
        "user_id":            str(uuid.uuid4()),
        "messages":           [],
        "agent_initialized":  False,
        "conversation_history": [],
        "agent_mode":         "simple",
        "current_provider":   "",
        "current_model":      "",
        "pending_question":   None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
app_config = get_config()
user_prefs = _user_memory.get_user_preferences(st.session_state.user_id)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 Agent UAM")
    st.caption("*Assistant virtuel universitaire*")
    st.divider()

    # ── Modèle ────────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Configuration")

    selected_provider = LLMProvider.OPENROUTER

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        st.caption(f"🔑 OpenRouter `…{api_key[-6:]}`")
    else:
        st.warning("⚠️ OPENROUTER_API_KEY manquante dans .env")

    env_model = app_config.llm.model_name or DEFAULT_MODEL
    default_model_name = next(
        (k for k, v in OPENROUTER_MODELS.items() if v == env_model),
        list(OPENROUTER_MODELS.keys())[0],
    )
    or_model_display = st.selectbox(
        "Modèle", list(OPENROUTER_MODELS.keys()),
        index=list(OPENROUTER_MODELS.keys()).index(default_model_name),
    )
    model_name = OPENROUTER_MODELS[or_model_display]
    custom = st.text_input(
        "Modèle personnalisé (optionnel)",
        placeholder="ex: mistralai/mistral-large",
    )
    if custom.strip():
        model_name = custom.strip()

    agent_mode_label = st.radio(
        "Mode d'agent",
        ["Simple", "Multi-Agents (par faculté)"],
        horizontal=True,
    )

    if st.button("🚀 Initialiser l'agent", type="primary", use_container_width=True):
        with st.spinner("Chargement des documents…"):
            try:
                vectorstore = load_and_index_documents(
                    app_config.documents_directory, selected_provider
                )
                final_model = model_name.strip() or DEFAULT_MODEL
                llm = initialize_llm(selected_provider, final_model)

                if "Multi-Agents" in agent_mode_label:
                    agent = create_multi_agent_graph(vectorstore, llm)
                    st.session_state.agent_mode = "multi"
                else:
                    agent = create_agent_graph(vectorstore, llm)
                    st.session_state.agent_mode = "simple"

                st.session_state.agent = agent
                st.session_state.agent_initialized = True
                st.session_state.vectorstore = vectorstore
                st.session_state.current_provider = "OpenRouter"
                st.session_state.current_model = final_model or model_name
                st.success("✅ Agent prêt !")

            except Exception as e:
                err = str(e)
                if "401" in err or "User not found" in err:
                    st.error("❌ Clé API invalide ou expirée.")
                    st.info("Allez sur **openrouter.ai → Keys** pour générer une nouvelle clé.")
                else:
                    st.error(f"❌ {e}")

    st.divider()

    # ── Statistiques ──────────────────────────────────────────────────────────
    st.markdown("### 📊 Statistiques")
    metrics = get_metrics_summary()
    c1, c2 = st.columns(2)
    c1.metric("Questions", metrics["total_questions"])
    c2.metric("Hors sujet", metrics["hors_sujet"])
    st.caption(f"⏱ Temps moyen : **{metrics['avg_response_time_ms']} ms**")

    top_q = get_top_questions(limit=3)
    if top_q:
        st.caption("🔥 Les plus posées")
        for item in top_q:
            q_short = item["question"][:42] + ("…" if len(item["question"]) > 42 else "")
            st.caption(f"• {q_short} `×{item['count']}`")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("### 📄 Exporter la conversation")
    has_conv = bool(st.session_state.conversation_history)

    export_data = {
        "user_id": st.session_state.user_id,
        "export_date": datetime.now().isoformat(),
        "conversations": st.session_state.conversation_history,
        "preferences": user_prefs,
    }
    st.download_button(
        "📥 Télécharger JSON",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"uam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
        disabled=not has_conv,
    )

    if st.button("📄 Générer PDF", use_container_width=True, disabled=not has_conv):
        try:
            pdf_path = export_to_pdf(
                st.session_state.conversation_history,
                st.session_state.user_id,
                user_prefs,
            )
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Télécharger PDF",
                    data=f.read(),
                    file_name=f"uam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"Erreur PDF: {e}")
            st.caption("→ `pip install reportlab`")

    st.divider()

    # ── Nouvelle conversation ─────────────────────────────────────────────────
    if st.button(
        "🗑️ Nouvelle conversation",
        use_container_width=True,
        disabled=not st.session_state.messages,
    ):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.rerun()

    st.divider()
    st.caption(f"Session : `{st.session_state.user_id[:8]}…`")

# ─── ZONE PRINCIPALE ──────────────────────────────────────────────────────────

# Header UAM
if st.session_state.agent_initialized:
    badge_html = (
        f'<span class="badge badge-on">🟢 {st.session_state.current_provider}'
        f' · {st.session_state.current_model}</span>'
    )
else:
    badge_html = '<span class="badge badge-off">⚪ Agent non initialisé</span>'

st.markdown(f"""
<div class="uam-header">
    <div class="uam-logo">🎓</div>
    <div class="uam-header-text">
        <h1>Assistant Virtuel UAM</h1>
        <p>Université Abdou Moumouni de Niamey — Niger</p>
        {badge_html}
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Écran de bienvenue ────────────────────────────────────────────────────────
if not st.session_state.agent_initialized:
    st.info(
        "👈 **Choisissez un provider et cliquez sur « Initialiser l'agent »** "
        "dans le panneau de gauche pour démarrer.",
        icon="ℹ️",
    )

    st.markdown("#### Ce que je peux faire pour vous")
    rows = [FEATURES[:3], FEATURES[3:]]
    for row in rows:
        cols = st.columns(3)
        for col, (icon, title, desc) in zip(cols, row):
            with col:
                st.markdown(f"""
                <div class="feat-card">
                    <div class="fi">{icon}</div>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("")

    st.stop()

# ─── Interface de chat ─────────────────────────────────────────────────────────

# Contrôle sources (discret)
show_sources = st.toggle("📚 Afficher les sources", value=False)

# Historique des messages
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🎓"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("elapsed_ms"):
            st.markdown(f'<div class="rt">⏱ {msg["elapsed_ms"]} ms</div>', unsafe_allow_html=True)
        if show_sources and msg.get("sources"):
            with st.expander(f"📚 Sources ({len(msg['sources'])})"):
                for src in msg["sources"]:
                    fname = Path(src["source"]).name
                    st.markdown(f"**📄 {fname}**")
                    st.caption(src["content"])

# Questions suggérées (uniquement quand la conversation est vide)
if not st.session_state.messages:
    st.markdown("#### 💡 Questions fréquentes — cliquez pour démarrer")
    cols = st.columns(3)
    for i, q in enumerate(SUGGESTED):
        with cols[i % 3]:
            if st.button(q, key=f"sq_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

# ─── Traitement de la question ─────────────────────────────────────────────────
# Récupérer la question : saisie manuelle OU suggestion cliquée
pending = st.session_state.get("pending_question")
if pending:
    st.session_state.pending_question = None  # effacer avant de traiter

user_input = st.chat_input("Posez votre question sur l'UAM…")
question = user_input or pending

if question:
    # ── Rate limiting ─────────────────────────────────────────────────────────
    _now = time.time()
    _window = _now - 60
    _times = [t for t in st.session_state.get("_request_times", []) if t > _window]
    if len(_times) >= app_config.rate_limit_per_minute:
        st.warning(
            f"⚠️ Limite atteinte ({app_config.rate_limit_per_minute} requêtes/min). "
            "Veuillez patienter avant d'envoyer une nouvelle question."
        )
        st.stop()
    _times.append(_now)
    st.session_state["_request_times"] = _times

    # Afficher message utilisateur
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)

    st.session_state.messages.append({
        "role": "user",
        "content": question,
        "timestamp": datetime.now().isoformat(),
    })

    # Générer et afficher la réponse
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Recherche en cours…"):
            try:
                start = time.perf_counter()
                run_cfg = {
                    "configurable": {"thread_id": st.session_state.user_id},
                    "recursion_limit": app_config.max_tool_iterations * 3 + 10,
                }

                if st.session_state.agent_mode == "multi":
                    state = {
                        "messages": [HumanMessage(content=question)],
                        "question": question,
                        "faculty": "",
                        "context": "",
                        "response": "",
                        "agent_used": "",
                    }
                else:
                    set_session_user_id(st.session_state.user_id)
                    state = {
                        "messages": [HumanMessage(content=question)],
                        "question": question,
                        "is_relevant": False,
                        "context": "",
                        "response": "",
                        "need_clarification": False,
                        "user_id": st.session_state.user_id,
                        "user_preferences": user_prefs,
                        "tool_iterations": 0,
                        # routing_hint volontairement absent : voir le
                        # commentaire de _prepare_run (api/agent_service.py) —
                        # même mécanisme, même checkpointer LangGraph, même
                        # raisonnement (BUG-14 / tâche 20).
                        "routing_context": "",
                        "user_profile": "",
                    }

                result = st.session_state.agent.invoke(state, run_cfg)
                elapsed_ms = int((time.perf_counter() - start) * 1000)

                # Extraire la réponse (ignorer les messages tool_calls)
                response_text = result.get("response", "")
                if not response_text:
                    for m in reversed(result.get("messages", [])):
                        if (
                            hasattr(m, "content")
                            and m.content
                            and not getattr(m, "tool_calls", None)
                        ):
                            response_text = m.content
                            break

                # Sources RAG
                sources = []
                if show_sources and st.session_state.get("vectorstore"):
                    try:
                        docs = st.session_state.vectorstore.similarity_search(
                            question, k=app_config.vectorstore.similarity_search_k
                        )
                        sources = [
                            {
                                "source": d.metadata.get("source", "document"),
                                "content": d.page_content[:400],
                            }
                            for d in docs
                        ]
                    except Exception:
                        pass

                # Afficher
                st.markdown(response_text)
                st.markdown(
                    f'<div class="rt">⏱ {elapsed_ms} ms</div>',
                    unsafe_allow_html=True,
                )
                if show_sources and sources:
                    with st.expander(f"📚 Sources ({len(sources)})"):
                        for src in sources:
                            fname = Path(src["source"]).name
                            st.markdown(f"**📄 {fname}**")
                            st.caption(src["content"])

                # Sauvegarder
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "elapsed_ms": elapsed_ms,
                    "sources": sources,
                    "timestamp": datetime.now().isoformat(),
                })
                st.session_state.conversation_history.append({
                    "question": question,
                    "response": response_text,
                    "timestamp": datetime.now().isoformat(),
                    "sources": sources,
                })

                # Métriques + mémoire
                record_question(
                    st.session_state.user_id, question,
                    result.get("is_relevant", True), elapsed_ms,
                )
                _user_memory.add_conversation(
                    st.session_state.user_id, question, response_text
                )

            except Exception as e:
                err = str(e)
                if "401" in err or "User not found" in err:
                    msg = "❌ Clé API expirée. Réinitialisez l'agent avec une clé valide."
                elif "Connection refused" in err:
                    msg = "❌ Service LLM injoignable. Vérifiez votre connexion ou redémarrez Ollama."
                else:
                    msg = f"❌ Erreur : {err}"
                st.error(msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": msg,
                    "timestamp": datetime.now().isoformat(),
                })

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#9CA3AF; font-size:.78rem'>"
    "Agent Conversationnel UAM · LangChain v1.0 + LangGraph v1.0 · 2025"
    "</div>",
    unsafe_allow_html=True,
)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains documentation and reference materials for a **Master's thesis (M2 Informatique, UAM Niamey)**: a conversational agent (chatbot) to help with administrative processes at Université Abdou Moumouni de Niamey, focusing on student enrollment.

The project uses **LangGraph** (stateful agent orchestration) on top of **LangChain** with a RAG pipeline backed by FAISS.

## Target Project Structure

The chatbot project (`chatbot-uam/`) follows this layout:

- `config/settings.py` — Centralized LLM provider configuration (Groq, OpenAI, Anthropic, Ollama) via `init_chat_model("provider:model")`
- `knowledge_base/builder.py` — FAISS vectorstore construction from UAM documents (PDF/TXT)
- `knowledge_base/documents_uam/` — Official UAM documents (inscriptions, formations, facultés)
- `tools/uam_tools.py` — LangChain `@tool` functions: `rechercher_informations_uam` (RAG search), `guide_processus_inscription`, `lister_facultes_uam`, `informations_frais_inscription`
- `agents/agent_principal.py` — Main LangGraph `StateGraph` with router → LLM agent → ToolNode (ReAct loop)
- `agents/supervisor.py` — Multi-agent supervisor (optional, advanced phase)
- `app_streamlit.py` — Streamlit web UI (port 8501)
- `main.py` — CLI entry point

## Architecture

The LangGraph graph flows: **START → Router** (filters off-topic questions) **→ LLM Agent** (with bound tools) **↔ ToolNode** (ReAct loop) **→ END**.

- **Short-term memory**: `InMemorySaver` keyed by `thread_id` (one UUID per session) — use `PostgresSaver` in production
- **Long-term memory**: `InMemoryStore` for user preferences — use `PostgresStore` in production
- **Embeddings**: `multilingual-e5-large` via `sentence-transformers`, stored in FAISS
- **LLM**: Default provider is Groq (`llama-3.3-70b-versatile`); configurable via `init_chat_model("provider:model")`
- **Context**: Passed as `UserContext(user_id=..., faculte=...)` at graph invocation

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env  # then edit .env with your keys

# Build the FAISS vectorstore (run once, or after adding documents)
python -c "from knowledge_base.builder import build_vectorstore; build_vectorstore()"

# Rebuild vectorstore (force)
python -c "from knowledge_base.builder import build_vectorstore; build_vectorstore(force_rebuild=True)"

# Run CLI chatbot
python main.py

# Run Streamlit web interface
streamlit run app_streamlit.py

# Run evaluation tests
python tests/evaluation.py
```

## Language and Domain

- All user-facing text, tool docstrings, and variable names are in **French**
- The chatbot is scoped to UAM administrative topics (inscriptions, facultés, formations, frais, contacts); off-topic questions are routed to a generic response
- The `@tool` docstrings are critical — the LLM reads them to decide which tool to invoke

## Key Patterns

- Tools are defined with `@tool` decorator and exported as `UAM_TOOLS` list in `tools/uam_tools.py`
- Tools are bound to the LLM via `llm.bind_tools(UAM_TOOLS)` and executed by LangGraph's `ToolNode`
- LLM provider switching uses `init_chat_model("provider:model")` — the unified LangChain 2025 API
- Conversation trimming uses `trim_messages()` for long conversations

"""
Harnais d'exécution du run gelé pour l'évaluation par paires (Option A).

Produit deux fichiers :
    responses_frozen.csv  — 74 réponses canoniques (question alignée avec sa réponse)
    grounding_log.json    — chunks RAG + scores pour chaque récupération

Usage :
    python run_grounding_capture.py
    python run_grounding_capture.py --dataset dataset_evaluation.csv
    python run_grounding_capture.py --limit 5   # test rapide sur 5 questions

Conditions de reproductibilité (exigées par le jury) :
    - temperature = 0 sur le LLM
    - exécution séquentielle (pas de parallélisme)
    - pip freeze > requirements.lock à lancer avant/après
"""

import os
import sys
import csv
import uuid
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.append(str(Path(__file__).parent))

# ── Imports projet ─────────────────────────────────────────────────────────────
from app_config import LLMProvider, get_config
from llm_utils import initialize_embeddings
from document_loader import load_and_index_documents
from agent_graph import create_agent_graph
from logger_config import get_logger
import grounding_capture

logger = get_logger(__name__)

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── Chargement des 74 questions pertinentes ────────────────────────────────────

def load_relevant_questions(dataset_path: str, limit: int = None):
    """Retourne les questions expected_relevant=true avec IDs Q01–Q74."""
    rows = []
    with open(dataset_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("expected_relevant", "").strip().lower() == "true":
                rows.append(row)
    if limit:
        rows = rows[:limit]
    return [
        {
            "question_id": f"Q{idx + 1:02d}",
            "question":    row["question"].strip(),
            "categorie":   row.get("category", "").strip(),
            "ground_truth": row.get("ground_truth", "").strip(),
        }
        for idx, row in enumerate(rows)
    ]


# ── Initialisation du LLM avec temperature=0 ─────────────────────────────────

def _init_llm_frozen(provider: LLMProvider, model_name: str = None):
    """Construit un LLM avec temperature=0 pour le run gelé."""
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY manquant dans .env")
    kwargs = {
        "api_key":   api_key,
        "base_url":  "https://openrouter.ai/api/v1",
        "model":     model_name or "meta-llama/llama-3.3-70b-instruct",
        "temperature": 0,
        "max_tokens":  1024,
        "default_headers": {
            "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://github.com/agent-uam"),
            "X-Title":      os.getenv("OPENROUTER_APP_NAME", "Agent UAM - Grounding Capture"),
        },
    }
    return ChatOpenAI(**kwargs)


# ── Exécution de l'agent sur une question ────────────────────────────────────

def run_agent_single(agent, question: str, config) -> str:
    """Invoque l'agent sur une question et retourne la réponse texte."""
    from langchain_core.messages import HumanMessage
    thread_id = str(uuid.uuid4())
    run_cfg = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": config.max_tool_iterations * 3 + 10,
    }
    state = {
        "messages":           [HumanMessage(content=question)],
        "question":           question,
        "is_relevant":        False,
        "context":            "",
        "response":           "",
        "need_clarification": False,
        "user_id":            thread_id,
        "user_preferences":   {},
        "tool_iterations":    0,
    }
    result = agent.invoke(state, run_cfg)

    # Extraire la réponse textuelle
    response_text = result.get("response", "")
    if not response_text:
        for m in reversed(result.get("messages", [])):
            if hasattr(m, "content") and m.content and not getattr(m, "tool_calls", None):
                response_text = m.content
                break
    return response_text


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run gelé : capture réponses + chunks RAG alignés (Option A)"
    )
    parser.add_argument("--dataset",  default="dataset_evaluation.csv")
    parser.add_argument("--limit",    type=int, default=None,
                        help="Limiter à N questions (test rapide)")
    parser.add_argument("--output-responses", default="responses_frozen.csv")
    parser.add_argument("--output-log",       default="grounding_log.json")
    parser.add_argument("--model", default=None,
                        help="Nom du modèle OpenRouter (défaut: llama-3.3-70b-instruct)")
    args = parser.parse_args()

    print(f"\n{BOLD}═══ Run gelé — Capture grounding (Option A) ═══{RESET}")
    print(f"   Dataset        : {args.dataset}")
    print(f"   Temperature    : 0 (reproductibilité)")
    print(f"   Sortie réponses: {args.output_responses}")
    print(f"   Sortie log     : {args.output_log}\n")

    # ── Chargement des questions ───────────────────────────────────────────
    questions = load_relevant_questions(args.dataset, args.limit)
    n = len(questions)
    print(f"{BOLD}► {n} questions pertinentes chargées{RESET}")

    # ── Initialisation ────────────────────────────────────────────────────
    print(f"\n{BOLD}► Initialisation (LLM temperature=0, vectorstore)…{RESET}")
    config     = get_config()
    llm        = _init_llm_frozen(LLMProvider.OPENROUTER, args.model)
    embeddings = initialize_embeddings(LLMProvider.OPENROUTER)
    vectorstore = load_and_index_documents(config.documents_directory, LLMProvider.OPENROUTER)
    agent      = create_agent_graph(vectorstore, llm)
    print(f"  Agent initialisé avec temperature=0")

    # ── Activation du mode grounding ─────────────────────────────────────
    grounding_capture.enable()
    print(f"  Mode grounding activé — cache LRU bypassed\n")

    # ── Run séquentiel ────────────────────────────────────────────────────
    print(f"{BOLD}► Exécution des {n} questions (séquentielle)…{RESET}\n")
    rows = []
    errors = 0

    for i, q in enumerate(questions, 1):
        qid      = q["question_id"]
        question = q["question"]
        categorie = q["categorie"]

        print(f"[{i:2}/{n}] {qid} | {question[:65]}{'…' if len(question) > 65 else ''}",
              end=" ", flush=True)

        grounding_capture.set_current_question(qid, question, categorie)

        t0 = time.perf_counter()
        try:
            response = run_agent_single(agent, question, config)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            print(f"{GREEN}✓{RESET} {elapsed_ms} ms")

            rows.append({
                "question_id":     qid,
                "categorie":       categorie,
                "question":        question,
                "reponse_chatbot": response,
                "ground_truth":    q["ground_truth"],
                "elapsed_ms":      elapsed_ms,
                "error":           "",
            })

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            print(f"{RED}✗ ERREUR : {e}{RESET}")
            logger.error(f"Erreur sur {qid} : {e}")
            errors += 1
            rows.append({
                "question_id":     qid,
                "categorie":       categorie,
                "question":        question,
                "reponse_chatbot": "",
                "ground_truth":    q["ground_truth"],
                "elapsed_ms":      elapsed_ms,
                "error":           str(e),
            })

    grounding_capture.disable()

    # ── Sauvegarde responses_frozen.csv ──────────────────────────────────
    print(f"\n{BOLD}► Sauvegarde…{RESET}")
    with open(args.output_responses, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["question_id", "categorie", "question",
                      "reponse_chatbot", "ground_truth", "elapsed_ms", "error"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {GREEN}✅ Réponses gelées → {args.output_responses}{RESET}")

    # ── Sauvegarde grounding_log.json ─────────────────────────────────────
    grounding_capture.dump(args.output_log)
    print(f"  {GREEN}✅ Log grounding   → {args.output_log}{RESET}")

    # ── Vérification de cohérence ─────────────────────────────────────────
    grounding_capture.verify(expected_count=n)

    # ── Résumé final ──────────────────────────────────────────────────────
    ok = n - errors
    print(f"{BOLD}► Résumé : {ok}/{n} questions réussies"
          f"{(' (' + str(errors) + ' erreurs)') if errors else ''}{RESET}")
    print(f"\n{GREEN}{BOLD}✅ Run gelé terminé !{RESET}")
    print(f"   Ces fichiers sont les entrées du classeur évaluateur Option A.")
    print(f"   NE PAS relancer ce script — les réponses sont maintenant canoniques.\n")


if __name__ == "__main__":
    main()

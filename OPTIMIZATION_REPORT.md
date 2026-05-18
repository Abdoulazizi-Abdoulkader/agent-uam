# Rapport d'optimisation des métriques — Agent UAM

> Branche : `feat/metrics-optimization` — 5 patches appliqués

---

## 1. Tableau récapitulatif avant / après

| Métrique | Avant | Cible | Impact attendu |
|---|---|---|---|
| RAGAS `answer_relevancy` | 0,454 | ≥ 0,70 | P1 + P2 : prompt resserré + max_tokens → réponses directes |
| RAGAS `faithfulness` | 0,667 | ≥ 0,70 | P3 : vrais contextes RAG fournis à RAGAS |
| Latence P90 | 11 564 ms | ≤ 10 000 ms | P4 : court-circuit ReAct à saturation |
| Longueur moyenne réponse | 174 mots | 60–120 mots | P1 + P2 : règles strictes + max_tokens=500 |
| Exactitude globale | 98,0 % | ≥ 95 % (maintien) | non touché |
| F1 routage | 0,989 | ≥ 0,95 (maintien) | non touché |

> Les métriques « après » seront renseignées après `python evaluate.py` complet.
> Lancer `run_comparison.sh` pour le tableau agent vs baseline.

---

## 2. Détail par patch

### PATCH 1 — Refonte du prompt système (`prompts.py`)

**Fichiers modifiés :** [prompts.py](prompts.py)

**Problème :** Le prompt imposait 5 étapes de réponse (salutation, réponse, sources,
proposition d'aide, clôture) et des exemples de formules de courtoisie. Résultat :
174 mots en moyenne, `answer_relevancy` = 0,454.

**Changement :** Remplacement de `_base_system_prompt()` par un prompt imposant
60–120 mots max, zéro salutation d'ouverture/clôture, accès direct à l'information
dès la première phrase. Les règles d'ancrage factuel sont maintenues.

**Périmètre :** `handle_special_case` n'utilise pas ce prompt — les cas FAREWELL,
THANKS, FRUSTRATION conservent leur ton chaleureux.

**Impact attendu :** Réduction immédiate de la longueur (~60 %) → hausse mécanique
de `answer_relevancy` (réponse plus ciblée par rapport à la question).

---

### PATCH 2 — Activer `max_tokens` (`llm_utils.py`)

**Fichiers modifiés :** [llm_utils.py](llm_utils.py), `.env`

**Problème :** `LLMConfig.max_tokens` lisait `UAM_LLM_MAX_TOKENS` depuis
l'environnement mais ne le transmettait jamais à `ChatOpenAI` — bug silencieux.

**Changement :** Ajout du paramètre conditionnel `max_tokens=config.llm.max_tokens`
via un dict `llm_kwargs`. Valeur recommandée : `UAM_LLM_MAX_TOKENS=500` (≈ 350 mots,
marge confortable au-dessus de la cible 120 mots).

**Impact attendu :** Plafonnement hard des réponses sans tronquage brutal. Réduit
aussi la latence (le modèle génère moins de tokens).

---

### PATCH 3 — Tracker des vrais contextes RAG (`context_tracker.py`, `tools.py`, `evaluate.py`)

**Fichiers modifiés :** [context_tracker.py](context_tracker.py) (nouveau),
[tools.py](tools.py), [evaluate.py](evaluate.py)

**Problème :** `evaluate.py` récupérait les contextes par un `similarity_search`
*a posteriori* sur la question brute, indépendant de l'agent. Or l'agent utilisait
des requêtes reformulées, des outils avec données codées en dur, et plusieurs itérations
ReAct. RAGAS comparait donc la réponse à des chunks étrangers → `faithfulness` biaisé.

**Changement :**
- `context_tracker.py` : buffer thread-safe avec `push_context()`, `flush_context()`,
  `reset()`.
- `tools.py` : ajout d'un helper `_rag_search()` qui wrap les 38 appels
  `similarity_search` et appelle automatiquement `push_context()`. Import unique
  `from context_tracker import push_context, push_text`.
- `evaluate.py` : `reset_context()` avant chaque invocation, `flush_context()` après
  pour récupérer les vrais contextes. Fallback FAISS si aucun outil instrumenté n'a
  été appelé (cas `handle_special_case`).

**Impact attendu :** `faithfulness` mesuré sur les vrais contextes utilisés → valeur
plus représentative et potentiellement plus haute (contextes spécialisés vs top-4 FAISS
générique).

---

### PATCH 4 — Court-circuit ReAct sur contexte saturé (`graph_nodes.py`)

**Fichiers modifiés :** [graph_nodes.py](graph_nodes.py)

**Problème :** `should_continue` ne regardait que `tool_calls`. Les catégories
`inscription_master_doctorat` et `profils_specialises` déclenchaient 2–3 itérations
ReAct inutiles après avoir collecté suffisamment de contexte → latence P90 = 11 564 ms.

**Changement :** Après ≥ 2 itérations, si le total des contenus `ToolMessage` dépasse
2 500 caractères (≈ 3–4 chunks de 600–800 car.), on force `return "end"`. Les requêtes
simples (0–1 outil) ne sont pas affectées. La limite stricte existante
(`max_tool_iterations`) est conservée.

**Seuil calibré :** 2 500 car. correspond à ~3 chunks FAISS de 800 car. — suffisant
pour répondre aux questions complexes sans itération supplémentaire.

**Impact attendu :** Réduction de P90 de ~15–25 % sur les catégories concernées, sans
régression d'exactitude (le contexte est déjà complet).

---

### PATCH 5 — Baseline RAG séquentielle (`baseline_rag.py`, `evaluate.py`, `run_comparison.sh`)

**Fichiers modifiés :** [baseline_rag.py](baseline_rag.py) (nouveau),
[evaluate.py](evaluate.py), [run_comparison.sh](run_comparison.sh) (nouveau)

**Problème :** Absence de baseline comparative — la contribution propre du graphe
LangGraph n'était pas démontrée empiriquement (Limite 3, §5.4 du mémoire).

**Changement :**
- `baseline_rag.py` : pipeline retrieve → generate sans graphe, sans ReAct, sans outils
  spécialisés. Prompt identique au Patch 1 pour assurer la comparabilité.
- `evaluate.py` : nouveau flag `--baseline` qui court-circuite `create_agent_graph` et
  utilise `run_baseline_query`. Le reste du pipeline (métriques, RAGAS) est identique.
- `run_comparison.sh` : enchaîne les deux évaluations et génère `COMPARISON_REPORT.md`
  avec un tableau côte à côte.

**Impact attendu :** Démonstration empirique que l'agent LangGraph surpasse la baseline
sur exactitude et faithfulness, au prix d'une latence plus élevée. Si ce n'est pas le
cas, c'est une découverte scientifique pertinente pour le mémoire.

---

## 3. Section baseline — tableau comparatif

> Générer avec : `./run_comparison.sh --no-ragas --limit 20` (test rapide)
> ou : `./run_comparison.sh` (évaluation complète avec RAGAS)

Voir [COMPARISON_REPORT.md](COMPARISON_REPORT.md) après exécution.

---

## 4. Limites résiduelles

| Limite | Cause | Recommandation |
|---|---|---|
| `answer_relevancy` < 0,70 après P1+P2 | Le modèle `gpt-4o-mini` peut ignorer partiellement les consignes de longueur | Tester `UAM_LLM_MAX_TOKENS=350` ou changer de modèle |
| `faithfulness` encore < 0,70 | Certains outils retournent du texte statique codé en dur non ancré aux documents | Instrumenter `push_text()` sur `calculate_fees` et `get_faculty_info` |
| Latence P90 > 10 000 ms | Réseau OpenRouter variable ; appels d'embeddings HuggingFace locaux | Activer le cache vectorstore persisté (`UAM_VECTORSTORE_DIR`) |
| Baseline `--baseline` marque toutes les questions `is_relevant=True` | La baseline n'implémente pas de routage hors-sujet | Ajouter un filtre `check_question_relevance` dans `run_baseline_query` si nécessaire |

---

## 5. Variables d'environnement recommandées pour la production

```env
# Provider
UAM_LLM_PROVIDER=openrouter
UAM_LLM_MODEL=openai/gpt-4o-mini

# Contrôle de la longueur (patch 2)
UAM_LLM_MAX_TOKENS=500

# RAG
UAM_SIMILARITY_K=8
UAM_CHUNK_SIZE=1000
UAM_VECTORSTORE_DIR=./vectorstore

# Limite de boucle (combiné avec court-circuit P4)
UAM_MAX_TOOL_ITERATIONS=3
```

---

## 6. Workflow Git

```
main
└── feat/metrics-optimization
    ├── refactor(prompts): resserrer le prompt système...      [Patch 1]
    ├── fix(llm): respecter max_tokens depuis la configuration [Patch 2]
    ├── feat(eval): tracker des contextes RAG...               [Patch 3]
    ├── perf(graph): court-circuit ReAct...                    [Patch 4]
    ├── feat(eval): baseline RAG séquentielle...               [Patch 5]
    └── docs: rapport d'optimisation des métriques             [ce commit]
```

# Rapport comparatif : LLM seul vs RAG séquentielle vs Agent LangGraph
> Généré le 09/06/2026 à 17:40

## Méthodologie

| Approche | Description |
|---|---|
| **LLM seul** | Génération directe à partir des connaissances du modèle, sans retrieval ni outils |
| **RAG séquentielle** | Retrieve top-4 documents → generate avec contexte, sans graphe ni outils spécialisés |
| **Agent LangGraph** | Graphe d'états + ReAct + ~47 outils @tool + routage + mémoire de session |

## Résultats comparatifs

### Classification pertinence / hors-sujet

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Exactitude | 0.8980 | 0.7551 | 0.9490 |
| Précision | 1.0000 | 0.7551 | 0.9481 |
| Rappel | 0.8649 | 1.0000 | 0.9865 |
| F1-Score | 0.9275 | 0.8605 | 0.9669 |

### Qualité des réponses (RAGAS)

> \* LLM seul : RAGAS non applicable — Faithfulness et Answer Relevancy mesurent l'ancrage
> dans un contexte récupéré ; sans retrieval, ces métriques sont vides de sens.

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Faithfulness | \* — | 0.5612 | 0.2808 |
| Answer Relevancy | \* — | 0.4547 | 0.5419 |

### Ancrage factuel (Keyword Recall)

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Recall moyen | 0.5180 | 0.2625 | 0.6428 |

### Performance système

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Latence moyenne (ms) | 2450.4000 | 1936.8000 | 4821.0000 |
| Latence P90 (ms) | 4089 | 3174 | 8546 |
| Longueur moy. réponse (mots) | 56.1000 | 32.3000 | 68.1000 |
| Taux d'erreur | 0.0000 | 0.0000 | 0.0000 |

## Interprétation

- **LLM seul → RAG séquentielle** : mesure la contribution du retrieval documentaire
- **RAG séquentielle → Agent LangGraph** : mesure la valeur ajoutée de l'orchestration agentique
  (routage intelligent, outils spécialisés, mémoire de session, gestion des profils utilisateur)

> LLM seul : génération sans document. RAG séquentielle : retrieve → generate. Agent : graphe LangGraph + ReAct + outils + mémoire.
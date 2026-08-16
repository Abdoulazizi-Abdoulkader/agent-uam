# Rapport comparatif : LLM seul vs RAG séquentielle vs Agent LangGraph
> Généré le 16/06/2026 à 13:53

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
| Exactitude | 0.9184 | 0.7551 | 0.9490 |
| Précision | 1.0000 | 0.7551 | 0.9481 |
| Rappel | 0.8919 | 1.0000 | 0.9865 |
| F1-Score | 0.9429 | 0.8605 | 0.9669 |

### Qualité des réponses (RAGAS)

> \* LLM seul : RAGAS non applicable — Faithfulness et Answer Relevancy mesurent l'ancrage
> dans un contexte récupéré ; sans retrieval, ces métriques sont vides de sens.

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Faithfulness | \* — | 0.4962 | 0.2788 |
| Answer Relevancy | \* — | 0.4450 | 0.6071 |

### Ancrage factuel (Keyword Recall)

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Recall moyen | 0.5251 | 0.2642 | 0.6496 |

### Performance système

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Latence moyenne (ms) | 1751.3000 | 1384.0000 | 3591.0000 |
| Latence P90 (ms) | 2307 | 2143 | 6366 |
| Longueur moy. réponse (mots) | 56.4000 | 32.0000 | 71.2000 |
| Taux d'erreur | 0.0000 | 0.0000 | 0.0000 |

## Interprétation

- **LLM seul → RAG séquentielle** : mesure la contribution du retrieval documentaire
- **RAG séquentielle → Agent LangGraph** : mesure la valeur ajoutée de l'orchestration agentique
  (routage intelligent, outils spécialisés, mémoire de session, gestion des profils utilisateur)

> LLM seul : génération sans document. RAG séquentielle : retrieve → generate. Agent : graphe LangGraph + ReAct + outils + mémoire.
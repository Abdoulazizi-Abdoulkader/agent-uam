# Rapport comparatif : LLM seul vs RAG séquentielle vs Agent LangGraph
> Généré le 21/05/2026 à 18:30

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
| Exactitude | 0.9184 | 0.7551 | 0.8673 |
| Précision | 1.0000 | 0.7551 | 0.8588 |
| Rappel | 0.8919 | 1.0000 | 0.9865 |
| F1-Score | 0.9429 | 0.8605 | 0.9182 |

### Qualité des réponses (RAGAS)

> \* LLM seul : RAGAS non applicable — Faithfulness et Answer Relevancy mesurent l'ancrage
> dans un contexte récupéré ; sans retrieval, ces métriques sont vides de sens.

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Faithfulness | \* — | 0.5033 | 0.2985 |
| Answer Relevancy | \* — | 0.4462 | 0.5071 |

### Ancrage factuel (Keyword Recall)

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Recall moyen | 0.5295 | 0.2659 | 0.5654 |

### Performance système

| Métrique | LLM seul | RAG séquentielle | Agent LangGraph |
|---|---|---|---|
| Latence moyenne (ms) | 2022.2000 | 1797.7000 | 4951.8000 |
| Latence P90 (ms) | 2765 | 2944 | 9169 |
| Longueur moy. réponse (mots) | 56.9000 | 32.9000 | 67.5000 |
| Taux d'erreur | 0.0000 | 0.0000 | 0.0000 |

## Interprétation

- **LLM seul → RAG séquentielle** : mesure la contribution du retrieval documentaire
- **RAG séquentielle → Agent LangGraph** : mesure la valeur ajoutée de l'orchestration agentique
  (routage intelligent, outils spécialisés, mémoire de session, gestion des profils utilisateur)

> LLM seul : génération sans document. RAG séquentielle : retrieve → generate. Agent : graphe LangGraph + ReAct + outils + mémoire.
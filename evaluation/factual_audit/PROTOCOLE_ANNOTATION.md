# Protocole d'annotation de la fidélité factuelle — Agent UAM

But : produire une mesure **réelle** de la fidélité factuelle des réponses (hypothèse H1),
distincte de l'exactitude de **routage** (`expected_relevant == actual_relevant`) que
`evaluate.py` calcule automatiquement et que le mémoire nommait improprement « exactitude ».

## 1. Périmètre

On annote les **74 questions UAM légitimes** (`expected_relevant = True`).
Les 24 questions hors-sujet ne sont pas annotées ici : leur « bonne réponse » est un refus,
déjà mesuré par la classification de routage (précision/rappel/F1).

> Recommandation jury : faire annoter par **deux évaluateurs indépendants** pour calculer
> un accord inter-annotateurs (Kappa de Cohen). Le script `compute_factual_accuracy.py`
> le fait automatiquement si on lui passe deux fichiers annotés.

## 2. Variable principale : `verdict_factuel`

Jugement porté sur la **correction factuelle** de la réponse, au regard de la colonne
`ground_truth` (réponse de référence) ET du corpus documentaire UAM. Quatre codes :

| Code | Signification | Règle de décision |
|------|---------------|-------------------|
| `C`  | **Correct** | Toutes les affirmations factuelles vérifiables sont exactes ; aucune invention. La réponse peut être plus courte que la référence. |
| `P`  | **Partiellement correct** | L'essentiel est exact mais il manque un élément factuel important de la référence, OU une affirmation **secondaire** est imprécise/non étayée. Aucune erreur factuelle grave. |
| `I`  | **Incorrect** | Au moins une affirmation factuelle **erronée** ou inventée (hallucination), OU contresens sur la procédure/le montant/la condition. |
| `NV` | **Non vérifiable** | Réponse de redirection sans contenu factuel à juger (« je n'ai pas cette information, contactez le service X »). Exclue du dénominateur d'exactitude. |

Principe directeur : on évalue la **factualité**, pas le style ni la complétude exhaustive.
Une réponse correcte mais brève reste `C`. Le doute factuel sérieux fait basculer en `I`.

## 3. Variables secondaires (optionnelles, échelle de Likert 1–5)

Pour refonder proprement le tableau qualitatif (mémoire §4.5, ex-« 4,4/5 mono-évaluateur ») :

- `exactitude` : informations correctes au regard des documents UAM (1 = très insuffisant, 5 = excellent)
- `completude` : couvre les éléments nécessaires
- `clarte` : structure, lisibilité, adaptation au public étudiant
- `utilite` : l'utilisateur peut agir concrètement

Laisser vide si on ne fait que l'audit factuel binaire.

## 4. Colonne `notes`

Justification courte obligatoire pour tout `P` ou `I` (ex : « invente des frais de 50 000 F non présents dans la référence »).
Indispensable pour la traçabilité et la réponse aux questions du jury.

## 5. Métriques produites (par `compute_factual_accuracy.py`)

- **Exactitude factuelle stricte** = `#C / (#C + #P + #I)` (les `NV` exclus)
- **Exactitude factuelle large** = `(#C + #P) / (#C + #P + #I)`
- Intervalle de confiance de Wilson à 95 % sur l'exactitude stricte
- Décomposition par catégorie
- Kappa de Cohen si deux fichiers annotés sont fournis

## 6. Mode opératoire

```bash
cd evaluation/factual_audit

# 1) Générer la feuille d'annotation (à partir des résultats agent)
python make_annotation_sheet.py \
    --results ../../evaluation_results/1352/results_agent.json \
    --out annotation_agent_eval1.csv --shuffle

# 2) Remplir la colonne verdict_factuel (C/P/I/NV) dans un tableur.
#    (Dupliquer le fichier pour un second annotateur : annotation_agent_eval2.csv)

# 3) Calculer l'exactitude factuelle réelle
python compute_factual_accuracy.py annotation_agent_eval1.csv
# ... ou avec accord inter-annotateurs :
python compute_factual_accuracy.py annotation_agent_eval1.csv annotation_agent_eval2.csv --latex
```

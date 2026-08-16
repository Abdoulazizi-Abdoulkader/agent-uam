# Message à envoyer aux évaluateurs

> Personnaliser les champs entre crochets. Envoyer **un fichier par évaluateur** —
> `annotation_agent_eval1.csv` au premier, `annotation_agent_eval2.csv` au second —
> accompagné de `PROTOCOLE_ANNOTATION.md`.

---

**Objet :** Évaluation de la fidélité factuelle de l'agent conversationnel UAM — 74 réponses à annoter

Bonjour [Prénom Nom],

Dans le cadre de mon mémoire de Master 2 en informatique à l'Université Abdou Moumouni,
j'ai développé un agent conversationnel qui répond aux questions des étudiants sur les
formalités administratives de l'UAM (inscription, formations, frais, facultés).

Pour valider ce travail, j'ai besoin d'une évaluation **humaine et indépendante** de la
justesse des réponses produites. Vous êtes deux évaluateurs à réaliser cet exercice
séparément, ce qui me permettra de calculer un accord inter-annotateurs (Kappa de Cohen)
et de donner une valeur scientifique à la mesure. Merci d'avance pour votre temps.

## Ce que je vous demande

Juger si chacune des **74 réponses** de l'agent est factuellement correcte, au regard de
la réponse de référence fournie dans le fichier. Comptez environ **1 h 30 à 2 h**.

Votre fichier : **`[annotation_agent_eval1.csv]`** (ci-joint).

Chaque ligne contient une question posée à l'agent, la réponse de référence
(`ground_truth`) et la réponse produite par l'agent (`response`).

## Comment remplir

Une seule colonne est **obligatoire** : `verdict_factuel`. Saisissez-y un code parmi
quatre :

| Code | Signification | Quand l'utiliser |
|------|---------------|------------------|
| `C` | **Correct** | Toutes les affirmations vérifiables sont exactes, aucune invention. Une réponse plus courte que la référence reste `C`. |
| `P` | **Partiellement correct** | L'essentiel est exact, mais il manque un élément important de la référence, ou une affirmation secondaire est imprécise. Aucune erreur grave. |
| `I` | **Incorrect** | Au moins une affirmation fausse ou inventée, ou un contresens sur une procédure, un montant, une condition. |
| `NV` | **Non vérifiable** | Simple redirection sans contenu factuel à juger (« je n'ai pas cette information, contactez le service X »). |

Deux principes :

- On juge la **factualité**, pas le style ni l'exhaustivité. Une réponse juste mais brève
  est `C`.
- **Un doute factuel sérieux fait basculer en `I`.** Ne mettez pas `P` par indulgence.

La colonne `notes` est **obligatoire pour tout `P` ou `I`** : une phrase suffit, par
exemple « annonce des frais de 50 000 F absents de la référence ». Ces justifications me
sont indispensables si le jury conteste une annotation.

Les colonnes `exactitude`, `completude`, `clarte` et `utilite` sont **facultatives**
(note de 1 à 5). Remplissez-les si vous en avez le temps ; laissez-les vides sinon, cela
ne bloque rien.

Ne modifiez pas les colonnes `id`, `category`, `expected_relevant`, `question`,
`ground_truth` et `response` : elles servent à recouper les deux évaluations.

## Deux précautions techniques

**À l'ouverture du fichier.** Les réponses de l'agent contiennent des sauts de ligne : le
fichier compte 560 lignes physiques pour 74 questions. Si votre tableur les interprète
mal, tout se décale.

- *LibreOffice Calc* (recommandé) : à l'import, cocher **Virgule** comme séparateur et
  **"** comme séparateur de texte.
- *Excel* : passer par **Données → À partir d'un fichier texte/CSV**, choisir l'encodage
  **UTF-8** et le séparateur **virgule**. N'ouvrez pas le fichier par double-clic.

**À l'enregistrement.** Conservez le format **CSV UTF-8** et le nom du fichier tel quel.
Dans Excel, choisir « CSV UTF-8 (délimité par des virgules) » — le « CSV » classique
détruit les accents.

## Important : travaillez seul

Ne comparez pas vos annotations avec celles de l'autre évaluateur avant de m'avoir rendu
votre fichier. Toute concertation invaliderait la mesure d'accord inter-annotateurs, qui
est précisément l'intérêt de la démarche. Les questions vous sont d'ailleurs présentées
dans un ordre différent pour chacun.

En revanche, si un cas vous paraît ambigu ou si une consigne n'est pas claire,
écrivez-moi : c'est à moi de trancher, pas à vous deux de vous accorder.

## Retour

Merci de me renvoyer le fichier complété avant le **[date]**, à cette adresse.

Je reste disponible pour toute question.

Bien cordialement,

**[Votre prénom et nom]**
Master 2 Informatique — Université Abdou Moumouni de Niamey
[téléphone / email]

*Pièces jointes : `[annotation_agent_eval1.csv]`, `PROTOCOLE_ANNOTATION.md`*

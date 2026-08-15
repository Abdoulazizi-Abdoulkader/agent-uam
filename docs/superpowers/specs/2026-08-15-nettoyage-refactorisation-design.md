# Nettoyage, refactorisation et complétion de l'agent UAM

**Date :** 2026-08-15
**Branche :** `feat/metrics-optimization`
**Statut :** spec validée, prête pour la rédaction du plan d'implémentation

## Objectif

Rendre le code du dépôt propre et maintenable sans altérer le comportement de
l'agent : supprimer le code mort, restructurer les modules devenus trop gros,
implémenter deux fonctionnalités manquantes et corriger les défauts détectés.

La contrainte dominante est la non-régression. Le projet sert de support à une
soutenance : un agent qui répond moins bien après nettoyage est un échec, même
si le code est plus beau.

## Périmètre

**Inclus** — le cœur de l'agent et ses interfaces :

`tools.py`, `graph_nodes.py`, `agent_graph.py`, `agent_state.py`, `tool_node.py`,
`llm_utils.py`, `prompts.py`, `document_loader.py`, `memory.py`, `app_config.py`,
`utils.py`, `uam_structures.py`, `agent_uam.py`, `chatbot.py`, `multi_agents.py`,
`database_connector.py`, `metrics.py`, `context_tracker.py`, `api/`, `web/`,
`app_streamlit.py`, `tests/`, `requirements.txt`, `CLAUDE.md`, `README.md`.

**Exclus (gelés)** — le volet évaluation, qui a produit les chiffres figurant
déjà dans le mémoire :

`evaluate.py`, `human_eval.py`, `baseline_rag.py`, `llm_only.py`,
`grounding_capture.py`, `run_grounding_capture.py`, `evaluation/` (à la seule
exception de la suppression de `evaluation/database/`, voir décision D3),
`setup_database.py` et `seed_database.py` tant que leur statut n'est pas établi
en phase 0.

**Hors sujet** — l'intégration WhatsApp. `api/whatsapp.py` n'est pas modifié.
La phase 6 produit une analyse de faisabilité écrite, sans code.

## Contraintes globales

Ces règles s'appliquent à toutes les phases sans exception.

1. **Comportement observable inchangé.** Toute modification qui altère ce que
   l'agent répond est un défaut, sauf si elle corrige un bug explicitement
   inscrit dans la liste de la phase 4.
2. **`get_tools()` retourne exactement 49 outils**, aux mêmes noms et signatures,
   dont 45 inconditionnels et 4 conditionnés à la disponibilité de la base.
   Après application de la décision D4, la variante SQLite en expose 48.
3. **Aucun test existant n'est supprimé ni affaibli.** Les 32 tests actuels
   doivent passer à la fin de chaque phase.
4. **Aucun appel LLM réel dans les tests.** Le LLM et le vectorstore FAISS sont
   remplacés par des doubles. La suite complète doit s'exécuter hors ligne en
   moins de 10 secondes.
5. **Un commit par phase, au minimum.** Chaque phase doit être annulable par un
   `git revert` unique.
6. **Aucun nœud du graphe ne retourne `{**state}`.** Le réducteur `add` sur
   `AgentState.messages` concatène au lieu de remplacer ; renvoyer l'état complet
   double l'historique à chaque passage. Un nœud ne retourne que les champs qu'il
   modifie. Cette règle est déjà documentée dans `CLAUDE.md` et doit le rester.
7. **Le volet évaluation reste exécutable.** Aucune signature importée par
   `evaluate.py`, `baseline_rag.py`, `llm_only.py` ou `run_grounding_capture.py`
   ne change. Ces modules importent `agent_graph`, `document_loader`,
   `llm_utils`, `app_config`, `context_tracker` et `tools` : leurs interfaces
   publiques sont gelées.

## État des lieux

Audit mené le 2026-08-15 sur 48 modules Python, 16 138 lignes.

| Constat | Mesure |
|---|---|
| Module le plus volumineux | `tools.py`, 2 222 lignes, 49 outils `@tool` |
| Doublon exact | `evaluation/database/` réplique `database/` : 2 scripts et 1 schéma SQL identiques au bit près, plus une base SQLite périmée |
| Imports inutilisés | ~40 réels sur 46 détectés par analyse AST, dont 9 dans `multi_agents.py` et 5 dans `database_connector.py` |
| Couverture de tests | 32 tests, ~2 % du code, limités à `utils`, `uam_structures` et le cœur de `tools` |
| Documentation fausse | `CLAUDE.md` renvoie à `audit_outils.md`, fichier inexistant |
| Scripts BDD au statut incertain | `setup_database.py` (864 l.) et `seed_database.py` (475 l.), aucun des deux importé |
| Outil inerte | `search_latest_news` est exposé au LLM mais retourne toujours `[]` sur SQLite |
| Dépendance manquante | `langgraph-checkpoint-sqlite` absent, alors que la persistance en dépend |
| Environnements | deux virtualenvs coexistaient ; `.venv` (incomplet, 11 dépendances manquantes) supprimé le 2026-08-15 |

Les deux bases `scolarite_uam.db` diffèrent : celle de `database/` (juin, 58
étudiants) porte les tables `frais_formations` et `statistiques_composantes` que
`database_connector.py` interroge ; celle de `evaluation/database/` (avril, 50
étudiants) ne les a pas.

## Décisions arrêtées

| Réf. | Décision | Motif |
|---|---|---|
| D1 | Organisation par risque croissant : audit, suppressions sûres, filet de tests, découpage, bugs, fonctionnalités, faisabilité | Chaque phase est un point d'arrêt valide si l'échéance se resserre |
| D2 | `tools.py` devient un package `tools/` de dix modules, avec `__init__.py` réexportant l'API publique | Aucun import appelant ne change ; le déplacement est mécanique donc vérifiable |
| D3 | `evaluation/database/` est supprimé intégralement ; `database/` est conservé | Doublon périmé, référencé nulle part dans le dépôt |
| D4 | `search_latest_news` cesse d'être exposé lorsque le backend est SQLite | Un outil incapable de retourner quoi que ce soit fait perdre un tour de boucle au LLM |
| D5 | `MemorySaver` remplacé par `SqliteSaver`, avec bascule par variable d'environnement | L'historique doit survivre au redémarrage ; la bascule permet des tests hors disque et un repli en démo |
| D6 | Tests de caractérisation ciblés, écrits avant chaque modification | Filet proportionné : on ne teste que ce qu'on s'apprête à toucher |
| D7 | Un comportement fautif constaté pendant l'écriture des tests n'est jamais figé en test vert | Sinon la refactorisation grave les bugs dans le marbre |
| D8 | WhatsApp : analyse de faisabilité écrite, aucun code | Décision explicite de reporter l'intégration |
| D9 | `.venv` supprimé, `venv` conservé comme unique environnement | `.venv` n'avait ni `fastapi` ni `uvicorn` : incapable de lancer le site |

## Architecture cible

### Le package `tools/`

```
tools/
  __init__.py        réexporte get_tools, set_vectorstore, set_session_user_id
                     et les 49 outils
  _vectorstore.py    état global FAISS, set_vectorstore / get_vectorstore
  recherche.py        1 outil  search_uam_knowledge
  conversation.py     5 outils detect_greeting, detect_user_profile,
                              detect_frustration_or_confusion,
                              check_question_relevance, get_agent_capabilities
  structures.py       3 outils get_faculty_info, get_structure_by_abbreviation,
                              list_all_structures
  scolarite.py       16 outils calculate_fees, search_formations,
                              search_admission_requirements,
                              search_required_documents,
                              search_registration_procedure,
                              search_registration_calendar, search_student_card,
                              search_transfer_equivalence,
                              search_housing_and_services, search_scholarships,
                              search_contacts_services,
                              search_international_equivalence,
                              search_late_reenrollment, search_internship_info,
                              search_double_degree,
                              generate_registration_checklist
  programmes.py      12 outils search_prerequisites, search_competences_requises,
                              search_cycles_et_duree, search_chronogramme,
                              search_coefficients, search_professeurs,
                              search_debouches, search_reglement_interieur,
                              search_organisation_corps_professoral,
                              search_organisation_corps_estudiantin,
                              search_reclamations, search_avantages_universite
  parcours.py         6 outils search_external_student_master,
                              search_phd_admission,
                              search_foreign_student_procedures,
                              search_recognition_prior_learning,
                              search_master_thesis_supervision,
                              search_academic_partnership
  base_donnees.py     4 outils search_student_record, search_statistics_uam,
                              search_latest_news, get_schedules_from_db
  preferences.py      2 outils save_user_preference, get_user_preferences
```

`get_tools()` reste dans `__init__.py` : c'est l'assemblage de la liste, pas un
outil. La répartition ci-dessus totalise 49 outils et sert de liste de référence
au test d'inventaire.

Les modules qui écrivent aujourd'hui `from tools import get_tools, set_vectorstore`
— `agent_graph.py`, `graph_nodes.py`, `agent_uam.py`, `app_streamlit.py`,
`api/agent_service.py`, `tests/test_tools_core.py` — restent inchangés.

### Persistance des sessions

`MemorySaver` n'est instancié qu'à un seul endroit, `agent_graph.py`. Le
remplacement s'y limite :

```python
checkpointer = _build_checkpointer(config)   # SqliteSaver ou MemorySaver
app = workflow.compile(checkpointer=checkpointer)
```

Nouvelle configuration dans `app_config.py` :

| Variable | Défaut | Effet |
|---|---|---|
| `UAM_CHECKPOINTER` | `sqlite` | `sqlite` persiste sur disque, `memory` conserve le comportement actuel |
| `UAM_CHECKPOINT_DB` | `./database/checkpoints.db` | Emplacement du fichier de checkpoints |

La connexion SQLite est ouverte avec `check_same_thread=False` : uvicorn tourne
en un seul worker mais sert les requêtes sur plusieurs threads, et le `ToolNode`
exécute les outils dans un pool de threads.

`requirements.txt` gagne `langgraph-checkpoint-sqlite`.

## Les sept phases

### Phase 0 — Base propre et audit

Commiter l'état actuel de la branche en commits cohérents, après avoir vérifié
que les 32 tests passent, de sorte que tout le travail ultérieur soit comparable
à un point de retour connu. Produire ensuite un rapport d'audit couvrant :

- l'inventaire du code mort réel, distinguant les scripts autonomes (points
  d'entrée légitimes) des définitions authentiquement inatteignables ;
- le statut de `setup_database.py` et `seed_database.py` : lequel est obsolète,
  preuve à l'appui ;
- l'analyse des temps de réponse à partir de `logs/` et `metrics.db`, avec la
  distribution observée et l'identification des causes de lenteur ;
- la liste des bugs constatés, chacun assorti de sa manifestation reproductible.

Cette liste de bugs devient l'entrée de la phase 4. Aucune correction en phase 0.

**Acceptation :** l'arbre de travail est propre, `git status` ne montre plus de
modification non commitée, et le rapport d'audit existe.

### Phase 1 — Suppressions prouvablement sûres

- Supprimer les ~40 imports inutilisés confirmés.
- Supprimer `evaluation/database/` (décision D3).
- Corriger `CLAUDE.md` : retirer la référence à `audit_outils.md`, mettre à jour
  la mention des deux virtualenvs si elle existe, refléter le nombre d'outils.
- Compléter `.env.example` et vérifier sa cohérence avec `app_config.py`.

Aucune modification de logique. Aucun test nouveau requis, mais les garde-fous
s'appliquent.

**Acceptation :** les 4 garde-fous passent, et `git diff` ne contient que des
suppressions de lignes et des corrections de documentation.

### Phase 2 — Filet de caractérisation

Écrire les tests figeant le comportement actuel des zones que les phases 3 à 5
modifieront :

| Cible | Nature du test |
|---|---|
| Inventaire des outils | `get_tools()` retourne 49 outils, noms et signatures conformes à la liste de référence |
| Outils déterministes | Appel direct sur `detect_greeting`, `detect_user_profile`, `check_question_relevance`, `detect_frustration_or_confusion`, `calculate_fees`, `get_faculty_info`, `get_structure_by_abbreviation`, `list_all_structures` |
| Routage | `route_and_store` produit le `routing_hint` attendu pour chacun des cas du tableau de `CLAUDE.md` |
| Compression d'historique | `_compress_history` retire les `ToolMessage` et les `AIMessage` porteurs de `tool_calls` des tours passés, et ne laisse jamais un appel sans son résultat |
| Contrat des nœuds | Aucun nœud ne renvoie l'état complet |
| Service | `answer(question, session_id)` isole les sessions, LLM remplacé par un double |
| Connecteur BDD | Les requêtes sur `database/scolarite_uam.db` retournent la forme attendue |

Application stricte de D7 : tout comportement jugé fautif part dans la liste de
la phase 4 au lieu d'être figé.

**Acceptation :** entre 80 et 120 tests au total dans `tests/`, les 32 existants
compris ; exécution complète sous 10 secondes, sans réseau ni clé d'API.

### Phase 3 — Découpage de `tools.py`

Créer le package `tools/` conforme à l'architecture cible. Déplacement de code
sans réécriture : le corps des fonctions n'est pas modifié.

**Acceptation :** les 4 garde-fous passent, `tools.py` n'existe plus, aucun
module appelant n'a été modifié, et le test d'inventaire de la phase 2 passe sans
avoir été amendé.

### Phase 4 — Correction des bugs

Traiter la liste établie en phase 0, dont la lenteur signalée par l'utilisateur.
Pour chaque bug : d'abord un test qui échoue et démontre le défaut, ensuite la
correction, enfin le test au vert.

**Acceptation :** chaque bug corrigé possède son test de non-régression ; les
bugs non corrigés sont documentés avec leur motif de report.

### Phase 5 — Fonctionnalités manquantes

- Persistance des sessions selon l'architecture cible : `SqliteSaver`,
  configuration `UAM_CHECKPOINTER` et `UAM_CHECKPOINT_DB`, dépendance ajoutée.
  Test démontrant qu'une conversation survit à la reconstruction du graphe.
- Application de D4 : `search_latest_news` retiré de la liste exposée lorsque le
  backend est SQLite, avec test d'inventaire adapté (48 outils dans ce cas).
- Vérification des trois autres outils conditionnels sur la base réelle, et
  correction s'ils ne retournent pas ce que leur docstring annonce.

**Acceptation :** les 4 garde-fous passent ; une conversation redémarre avec son
historique après relance du processus.

### Phase 6 — Faisabilité WhatsApp

Rédiger `WHATSAPP_FAISABILITE.md` : ce que `api/whatsapp.py` couvre déjà, les
prérequis côté Meta (compte business, numéro vérifié, token permanent — celui de
l'application expire en 24 h), le coût par conversation, les contraintes de
conformité liées aux données étudiantes, l'effort restant estimé, et l'apport de
la persistance des sessions pour ce canal.

**Acceptation :** le document existe et ne s'accompagne d'aucune modification de
code.

## Garde-fous

Vérifiés à la fin de chaque phase. Une phase n'est close que si les quatre
passent.

1. `venv/bin/python -m pytest tests/ -q` : intégralité au vert.
2. `get_tools()` retourne le nombre d'outils attendu, aux noms conformes.
3. Les six points d'entrée s'importent sans erreur : `api.main`, `app_streamlit`,
   `agent_uam`, `chatbot`, `evaluate`, `run_grounding_capture`.
4. Le site démarre via `./run_api.sh` et répond de façon pertinente aux trois
   questions témoins suivantes, posées sur `/api/chat` : « Quels sont les frais
   d'inscription en licence ? », « Que propose la FAST ? » et « Comment se
   réinscrire en retard ? ». Le critère est qu'aucune réponse ne soit vide, ne
   contienne de trace d'erreur, ni ne s'écarte du sujet de la question.

## Risques

| Risque | Parade |
|---|---|
| Le filet de caractérisation fige un bug au lieu de le signaler | Décision D7 : tout comportement suspect part en phase 4 plutôt qu'en test vert |
| Le découpage de `tools.py` égare un outil | Test d'inventaire écrit en phase 2, avant tout déplacement |
| `SqliteSaver` se comporte mal en environnement multithread | `check_same_thread=False`, test dédié, et repli immédiat par `UAM_CHECKPOINTER=memory` |
| Une suppression casse le volet évaluation gelé | Contrainte globale 7 : les interfaces publiques importées par ces modules ne changent pas ; garde-fou 3 les importe à chaque phase |
| L'échéance de soutenance arrive avant la fin | L'ordre par risque croissant garantit qu'un arrêt après n'importe quelle phase laisse le dépôt cohérent |

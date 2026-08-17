# Nettoyage et refactorisation de l'agent UAM — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supprimer le code mort, restructurer `tools.py` en package, corriger les défauts constatés et implémenter la persistance des sessions, sans altérer le comportement de l'agent.

**Architecture:** Sept phases par risque croissant. On commence par les suppressions prouvablement sûres, on installe un filet de tests de caractérisation, puis on refactorise et on corrige sous la protection de ce filet. Chaque phase est un commit annulable et un point d'arrêt valide.

**Tech Stack:** Python 3.12, LangGraph 1.0.5, LangChain, FAISS, FastAPI, SQLite, pytest 9.0.3. Environnement unique : `venv/`.

**Spec:** [docs/superpowers/specs/2026-08-15-nettoyage-refactorisation-design.md](../specs/2026-08-15-nettoyage-refactorisation-design.md)

## Global Constraints

Ces règles s'appliquent à toutes les tâches sans exception. Les exigences de chaque tâche les incluent implicitement.

1. **Comportement observable inchangé.** Toute modification qui altère ce que l'agent répond est un défaut, sauf si elle corrige un bug explicitement inscrit dans la liste de la phase 4 (tâche 2).
2. **`get_tools()` retourne exactement 49 outils**, aux mêmes noms et signatures, dont 45 inconditionnels et 4 conditionnés à la disponibilité de la base. Après la tâche 14, la variante SQLite en expose 48.
3. **Aucun test existant n'est supprimé ni affaibli.** Les 32 tests actuels doivent passer à la fin de chaque tâche.
4. **Aucun appel LLM réel dans les tests.** Le LLM et le vectorstore FAISS sont remplacés par des doubles. La suite complète doit s'exécuter hors ligne en moins de 10 secondes.
5. **Un commit par tâche, au minimum.** Chaque tâche doit être annulable par un `git revert` unique.
6. **Aucun nœud du graphe ne retourne `{**state}`.** Le réducteur `add` sur `AgentState.messages` concatène au lieu de remplacer ; renvoyer l'état complet double l'historique à chaque passage. Un nœud ne retourne que les champs qu'il modifie.
7. **Le volet évaluation reste exécutable.** Aucune signature importée par `evaluate.py`, `baseline_rag.py`, `llm_only.py` ou `run_grounding_capture.py` ne change. Ces modules importent `agent_graph`, `document_loader`, `llm_utils`, `app_config`, `context_tracker` et `tools` : leurs interfaces publiques sont gelées.

   **Rectification du 2026-08-17 :** cette contrainte affirmait que l'alias `_truncate_history` ([graph_nodes.py:147](../../../graph_nodes.py#L147)) était importé ailleurs et devait survivre. C'est faux, et le commentaire du code qui l'accompagne l'est aussi (« evaluate.py et les tests importent encore ce nom »). Vérification : `git grep -n "_truncate_history" -- '*.py'` ne retourne que sa propre définition. C'est du code mort, au même titre que les trois fonctions supprimées en tâche 3 — et le test écrit en tâche 8 pour en garantir la survie verrouillait donc du code mort dans un chantier dont l'objet est d'en supprimer.
8. **Commande de test unique :** `venv/bin/python -m pytest tests/ -q`. Ne jamais utiliser `.venv` (supprimé le 2026-08-15) ni `python` nu.
9. **Échéance : 2026-08-31.** Si la phase 2 n'est pas close au 2026-08-24, appliquer la règle d'arbitrage de la section « Échéance et arbitrage » du spec.

## Structure des fichiers

**Créés :**

| Fichier | Responsabilité |
|---|---|
| `docs/superpowers/audit/2026-08-16-audit.md` | Rapport d'audit : code mort, statut des scripts BDD, analyse des lenteurs, liste des bugs |
| `tools/__init__.py` | Assemblage de `get_tools()` et réexport de l'API publique |
| `tools/_vectorstore.py` | État global FAISS, verrou, `set_vectorstore` / `get_vectorstore` |
| `tools/_session.py` | `ContextVar` du `user_id` de session, `set_session_user_id` / `get_session_user_id` |
| `tools/_rag.py` | Helper `_rag_response` partagé par les modules d'outils |
| `tools/_db.py` | Import conditionnel de `database_connector`, drapeau `_db_available` |
| `tools/recherche.py` | 1 outil de recherche sémantique |
| `tools/conversation.py` | 5 outils de détection conversationnelle |
| `tools/structures.py` | 3 outils sur les structures UAM |
| `tools/scolarite.py` | 16 outils frais, inscription, services |
| `tools/programmes.py` | 12 outils filières et corps universitaire |
| `tools/parcours.py` | 6 outils master, doctorat, étranger, VAE |
| `tools/base_donnees.py` | 4 outils conditionnés à la base |
| `tools/preferences.py` | 2 outils de mémoire utilisateur |
| `tests/test_inventaire_outils.py` | Garde-fou du découpage : noms et cardinalité des outils |
| `tests/test_outils_deterministes.py` | Caractérisation des outils sans dépendance externe |
| `tests/test_routage.py` | Caractérisation de `route_and_store` |
| `tests/test_historique.py` | Caractérisation de `_compress_history` et contrat des nœuds |
| `tests/test_agent_service.py` | Caractérisation de `answer()` et isolation des sessions |
| `tests/test_database_connector.py` | Caractérisation du connecteur sur base réelle |
| `tests/test_persistance.py` | Survie de l'historique à la reconstruction du graphe |
| `WHATSAPP_FAISABILITE.md` | Analyse de faisabilité du canal WhatsApp |

**Modifiés :** `graph_nodes.py`, `agent_graph.py`, `app_config.py`, `database_connector.py`, `multi_agents.py`, `api/main.py`, `api/site_data.py`, `api/whatsapp.py`, `export_utils.py`, `requirements.txt`, `CLAUDE.md`, `.env.example`.

**Supprimés :** `tools.py` (devient le package), `evaluation/database/` (dossier entier).

---

## Phase 0 — Base propre et audit

### Task 1: Base git propre

**Files:**
- Modify: aucun fichier de code — cette tâche ne fait que committer l'existant

**Interfaces:**
- Consumes: rien
- Produces: un arbre de travail propre, servant de point de retour à toutes les tâches suivantes

- [ ] **Step 1: Vérifier que la suite passe AVANT de committer**

```bash
cd /home/aaaky/Bureau/UAM/App/agent-uam
venv/bin/python -m pytest tests/ -q
```

Attendu : `32 passed`. Si un test échoue, ne rien committer et signaler l'échec — l'état de départ doit être sain, sinon le point de retour ne vaut rien.

- [ ] **Step 2: Inspecter ce qui est en attente**

```bash
git status --short
git diff --stat
```

Attendu : 15 fichiers modifiés (~931 lignes), les dossiers non suivis `api/`, `web/`, `evaluation/factual_audit/`, les fichiers `.env.example`, `WHATSAPP.md`, `run_api.sh`, et des suppressions déjà indexées (`grounding_log.json`, `responses_frozen.csv`, `vectorstore/`).

- [ ] **Step 3: Committer par lots cohérents**

```bash
git add api/ web/ run_api.sh WHATSAPP.md .env.example
git commit -m "feat(web): site institutionnel, API de chat et canal WhatsApp"

git add tools.py graph_nodes.py tool_node.py llm_utils.py app_config.py chatbot.py
git commit -m "refactor(agent): améliorations du cœur conversationnel"

git add database_connector.py seed_database.py
git commit -m "feat(db): connecteur scolarité et peuplement de la base"

git add evaluate.py evaluation/factual_audit/
git commit -m "feat(eval): audit factuel et évolutions de l'évaluation"

git add -A
git commit -m "chore: documentation, dépendances et artefacts d'exécution"
```

Note : `git add -A` du dernier lot inclut les suppressions déjà indexées de `grounding_log.json`, `responses_frozen.csv` et `vectorstore/` — c'est voulu, ces artefacts sont régénérables et `.gitignore` les couvre.

- [ ] **Step 4: Vérifier que l'arbre est propre et que la suite passe toujours**

```bash
git status --short
venv/bin/python -m pytest tests/ -q
```

Attendu : `git status --short` ne retourne rien, et `32 passed`.

---

### Task 2: Rapport d'audit

**Files:**
- Create: `docs/superpowers/audit/2026-08-16-audit.md`

**Interfaces:**
- Consumes: l'arbre propre de la tâche 1
- Produces: `docs/superpowers/audit/2026-08-16-audit.md`, dont la section « Bugs constatés » est l'entrée obligatoire de la tâche 12, et la section « Statut des scripts BDD » celle de la tâche 4

Aucune correction dans cette tâche. On constate, on prouve, on écrit.

- [ ] **Step 1: Inventorier les définitions inatteignables**

Écrire le script d'analyse dans le scratchpad (pas dans le dépôt) :

```python
# audit_mort.py — définitions de module jamais référencées ailleurs
import ast, subprocess
from collections import defaultdict
from pathlib import Path

root = Path("/home/aaaky/Bureau/UAM/App/agent-uam")
files = subprocess.run(["git", "ls-files", "*.py"], cwd=root,
                       capture_output=True, text=True).stdout.split()
trees, sources = {}, {}
for f in files:
    src = (root / f).read_text(encoding="utf-8")
    sources[f], trees[f] = src, ast.parse(src)

occurrences = defaultdict(int)
for tree in trees.values():
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            occurrences[node.id] += 1
        elif isinstance(node, ast.Attribute):
            occurrences[node.attr] += 1
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                occurrences[a.name] += 1

all_src = "\n".join(sources.values())
for f, tree in sorted(trees.items()):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            n = node.name
            if n.startswith("_") or n.startswith("test_"):
                continue
            if occurrences[n] == 0 and f'"{n}"' not in all_src and f"'{n}'" not in all_src:
                print(f"{f}:{node.lineno}: {n}")
```

Exécuter : `venv/bin/python <chemin_scratchpad>/audit_mort.py`

**Écarter les faux positifs** avant de conclure — une définition peut être atteinte sans être nommée : routes FastAPI (décorateur `@app.get`), classes de test découvertes par pytest, fonctions appelées uniquement depuis le `__main__` de leur propre module, outils `@tool` invoqués par le LLM via `get_tools()`. Chaque entrée retenue doit être justifiée dans le rapport.

- [ ] **Step 2: Trancher le statut de `setup_database.py` et `seed_database.py`**

```bash
grep -rn "setup_database\|seed_database" --include="*.py" --include="*.md" --include="*.sh" . | grep -v "/venv/" | grep -v "__pycache__"
git log --oneline -5 -- setup_database.py
git log --oneline -5 -- seed_database.py
venv/bin/python -c "
import ast
for f in ('setup_database.py', 'seed_database.py'):
    t = ast.parse(open(f).read())
    noms = [n.name for n in t.body if isinstance(n, ast.FunctionDef)]
    print(f, '->', noms)
"
```

Comparer les tables que chacun crée ou peuple au schéma réel de `database/scolarite_uam.db` :

```bash
venv/bin/python -c "
import sqlite3
c = sqlite3.connect('database/scolarite_uam.db')
for (t,) in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\"):
    print(t, c.execute(f'SELECT COUNT(*) FROM \\\"{t}\\\"').fetchone()[0])
"
```

Conclure lequel produit la base actuellement utilisée. La conclusion doit être étayée : dates de commit, tables couvertes, cohérence avec les 58 étudiants et les tables `frais_formations` et `statistiques_composantes` présentes en base.

- [ ] **Step 3: Analyser les temps de réponse**

```bash
ls -la logs/
venv/bin/python -c "
import sqlite3
c = sqlite3.connect('metrics.db')
for (t,) in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
    print('TABLE', t)
    cols = [d[1] for d in c.execute(f'PRAGMA table_info(\\\"{t}\\\")')]
    print('  colonnes:', cols)
    print('  lignes:', c.execute(f'SELECT COUNT(*) FROM \\\"{t}\\\"').fetchone()[0])
"
```

Puis extraire la distribution des durées (médiane, P90, maximum) depuis la colonne de temps de réponse de `metrics.db`, et compter dans `logs/` les occurrences de saturation de boucle d'outils :

```bash
grep -rc "max_tool_iterations\|itération\|Limite" logs/*.log 2>/dev/null | head
grep -rn "Troncature de l'historique\|Historique allégé" logs/*.log 2>/dev/null | tail -20
```

- [ ] **Step 4: Rédiger le rapport**

Créer `docs/superpowers/audit/2026-08-16-audit.md` avec exactement ces cinq sections :

1. **Code mort avéré** — un tableau `fichier:ligne | symbole | preuve de non-atteignabilité`.
2. **Faux positifs écartés** — même format, avec le motif de l'écart. Cette section évite qu'une tâche ultérieure resupprime à tort.
3. **Statut des scripts BDD** — lequel de `setup_database.py` / `seed_database.py` est obsolète, avec les preuves du step 2, et la recommandation (supprimer ou conserver).
4. **Temps de réponse** — médiane, P90, maximum observés ; nombre de saturations de boucle d'outils ; causes identifiées.
5. **Bugs constatés** — un tableau `identifiant | manifestation reproductible | fichier:ligne suspecté | gravité`. Chaque bug doit être reproductible : sans procédure de reproduction, il ne figure pas dans la liste. Y inscrire d'office le bug déjà connu : `BUG-01 | search_latest_news est exposé au LLM mais retourne toujours [] sur SQLite, ce qui consomme un tour de boucle | database_connector.py:534 | moyenne`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/audit/2026-08-16-audit.md
git commit -m "docs(audit): inventaire du code mort, des lenteurs et des bugs"
```

---

## Phase 1 — Suppressions prouvablement sûres

### Task 3: Suppression des imports inutilisés

**Files:**
- Modify: `api/main.py:17`, `app_streamlit.py:33`, `database_connector.py:6,9,10,11,76`, `export_utils.py:8,9,13,14,15`, `multi_agents.py:1,3,6,7`, `metrics.py`, `tools.py:30,92`, `evaluate.py:24`, `baseline_rag.py:6`, `run_grounding_capture.py:26`, `seed_database.py:17`, `human_eval.py:11,12,14,18`, `tests/test_uam_structures.py:7`

**Interfaces:**
- Consumes: rien
- Produces: rien de nouveau — seules des lignes disparaissent

- [ ] **Step 1: Régénérer la liste des imports inutilisés**

Écrire dans le scratchpad :

```python
# audit_imports.py
import ast, subprocess
from pathlib import Path

root = Path("/home/aaaky/Bureau/UAM/App/agent-uam")
files = subprocess.run(["git", "ls-files", "*.py"], cwd=root,
                       capture_output=True, text=True).stdout.split()

def noms_utilises(tree):
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used.add(n.id)
    return used

for f in files:
    src = (root / f).read_text(encoding="utf-8")
    tree = ast.parse(src)
    used = noms_utilises(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                local = (a.asname or a.name).split(".")[0]
                if local not in used and f'"{local}"' not in src and f"'{local}'" not in src:
                    print(f"{f}:{node.lineno}: import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.names and node.names[0].name == "*":
                continue
            if node.module == "__future__":
                continue
            for a in node.names:
                local = a.asname or a.name
                if local not in used and f'"{local}"' not in src and f"'{local}'" not in src:
                    print(f"{f}:{node.lineno}: from {node.module} import {local}")
```

Exécuter : `venv/bin/python <chemin_scratchpad>/audit_imports.py`

Attendu : environ 40 lignes. Les imports `from __future__ import annotations` sont exclus par le script — ils ne sont jamais « utilisés » comme noms mais restent nécessaires.

- [ ] **Step 2: Supprimer les imports listés**

Retirer chaque ligne signalée. Deux cas exigent la prudence :

- `database_connector.py:76` — `from mysql.connector import Error` est à l'intérieur d'un bloc conditionnel de chargement de pilote. Vérifier qu'`Error` n'est pas capturé plus bas dans un `except Error:` avant de le retirer : `grep -n "Error" database_connector.py`.
- `tools.py:92` — `from database_connector import query_database` fait partie du bloc `try/except ImportError` qui fixe `_db_available`. Ne retirer que le nom `query_database` de la liste importée, jamais le bloc.

- [ ] **Step 3: Vérifier qu'aucun module n'est cassé**

```bash
venv/bin/python -c "
import importlib
for m in ('api.main','app_streamlit','agent_uam','chatbot','evaluate','run_grounding_capture','tools','database_connector','multi_agents','export_utils','human_eval','metrics','baseline_rag','seed_database'):
    importlib.import_module(m); print('ok', m)
"
venv/bin/python -m pytest tests/ -q
```

Attendu : `ok` pour les 14 modules, puis `32 passed`.

- [ ] **Step 4: Vérifier que le diff ne contient que des suppressions**

```bash
git diff --numstat
```

Attendu : la colonne des lignes ajoutées est à `0` pour tous les fichiers. Une ligne ajoutée signale une modification de logique, interdite dans cette tâche.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: suppression des imports inutilisés"
```

---

### Task 4: Suppression du doublon BDD et correction de la documentation

**Files:**
- Delete: `evaluation/database/` (dossier entier : `outil_requete_scolarite.py`, `simulation_scolarite.py`, `schema_scolarite_uam.sql`, `scolarite_uam.db`)
- Modify: `CLAUDE.md`, `.env.example`

**Interfaces:**
- Consumes: la section « Statut des scripts BDD » du rapport d'audit (tâche 2)
- Produces: rien

- [ ] **Step 1: Confirmer qu'aucune référence ne subsiste**

```bash
grep -rn "evaluation/database\|evaluation\.database" --include="*.py" --include="*.md" --include="*.sh" --include="*.json" . | grep -v "/venv/" | grep -v "__pycache__"
```

Attendu : aucune sortie. **Si une référence apparaît, ne pas supprimer** : signaler et s'arrêter là pour cette tâche.

- [ ] **Step 2: Supprimer le dossier**

```bash
git rm -r evaluation/database/
```

- [ ] **Step 3: Corriger `CLAUDE.md`**

Trois corrections exactes :

1. Retirer la mention de `audit_outils.md` dans la ligne décrivant `tools.py` — ce fichier n'existe pas. La ligne devient :
   `tools.py — 49 outils @tool pour recherche sémantique FAISS, infos facultés, frais, etc. (45 toujours actifs + 4 conditionnels à la base de données)`
2. Dans le tableau des variables d'environnement, corriger le défaut de `UAM_LLM_PROVIDER` : il est documenté `llama_groq` alors que [app_config.py:65](../../../app_config.py#L65) lit `os.getenv("UAM_LLM_PROVIDER", "openrouter")`. Mettre `openrouter`.
3. Ajouter une ligne à la section des commandes principales, pour que l'environnement à utiliser ne soit plus ambigu :
   `venv/bin/python -m pytest tests/ -q   # Lancer la suite de tests`

- [ ] **Step 4: Compléter `.env.example`**

Vérifier que chaque variable lue par `app_config.py` y figure :

```bash
grep -oE 'os\.getenv\("([A-Z_]+)"' app_config.py | grep -oE '[A-Z_]+' | sort -u > /tmp/lues.txt
grep -oE "^[A-Z_]+" .env.example | sort -u > /tmp/documentees.txt
diff /tmp/lues.txt /tmp/documentees.txt
```

Ajouter dans `.env.example` toute variable lue mais non documentée, avec un commentaire d'une ligne indiquant son rôle et son défaut.

- [ ] **Step 5: Traiter le script BDD obsolète**

Lire la section 3 du rapport d'audit et appliquer sa recommandation.

Si elle conclut qu'un des deux scripts est obsolète, le supprimer :

```bash
git rm <script_obsolete>.py
grep -rn "<script_obsolete>" --include="*.py" --include="*.md" --include="*.sh" . | grep -v "/venv/" | grep -v "__pycache__"
```

La commande `grep` doit ne rien retourner. Si elle retourne une référence — notamment dans `README.md`, `setup.sh` ou `CLAUDE.md` — mettre à jour cette référence vers le script conservé dans le même commit.

Si le rapport conclut que les deux sont utiles ou que la preuve est insuffisante, **ne rien supprimer** : ajouter à chacun un en-tête d'une ligne précisant son rôle et sa relation à l'autre, pour que la question ne se repose pas.

- [ ] **Step 6: Vérifier et committer**

```bash
venv/bin/python -m pytest tests/ -q
venv/bin/python -c "import evaluate, agent_uam, api.main; print('imports ok')"
git add -A
git commit -m "chore: suppression du doublon evaluation/database et correction de la documentation"
```

Attendu : `32 passed` puis `imports ok`.

---

## Phase 2 — Filet de caractérisation

### Task 5: Test d'inventaire des outils

C'est le garde-fou du découpage de la tâche 11. Il doit être écrit maintenant, sur `tools.py` monolithique, et passer **sans modification** après le découpage.

**Files:**
- Create: `tests/test_inventaire_outils.py`

**Interfaces:**
- Consumes: `tools.get_tools()`, `tools._db_available`
- Produces: `NOMS_OUTILS_INCONDITIONNELS` (frozenset de 45 noms) et `NOMS_OUTILS_BASE` (frozenset de 4 noms), définis dans `tests/test_inventaire_outils.py` et réutilisés par la tâche 14

- [ ] **Step 1: Écrire le test d'inventaire**

```python
# tests/test_inventaire_outils.py
"""Inventaire des outils exposés au LLM.

Ce test est le garde-fou du découpage de tools.py en package : il doit passer
à l'identique avant et après, sans qu'une seule ligne en soit modifiée.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

NOMS_OUTILS_INCONDITIONNELS = frozenset({
    "detect_greeting", "detect_user_profile", "detect_frustration_or_confusion",
    "get_agent_capabilities", "check_question_relevance",
    "search_uam_knowledge", "get_faculty_info", "get_structure_by_abbreviation",
    "list_all_structures",
    "search_formations", "search_prerequisites", "search_competences_requises",
    "search_cycles_et_duree", "search_chronogramme", "search_coefficients",
    "search_debouches", "search_avantages_universite",
    "search_admission_requirements", "search_required_documents",
    "search_registration_procedure", "search_registration_calendar",
    "search_late_reenrollment", "generate_registration_checklist", "calculate_fees",
    "search_external_student_master", "search_phd_admission",
    "search_foreign_student_procedures", "search_recognition_prior_learning",
    "search_master_thesis_supervision", "search_academic_partnership",
    "search_international_equivalence", "search_transfer_equivalence",
    "search_student_card", "search_internship_info", "search_double_degree",
    "search_reclamations",
    "search_housing_and_services", "search_scholarships", "search_contacts_services",
    "search_professeurs", "search_organisation_corps_professoral",
    "search_organisation_corps_estudiantin", "search_reglement_interieur",
    "save_user_preference", "get_user_preferences",
})

NOMS_OUTILS_BASE = frozenset({
    "search_latest_news", "get_schedules_from_db",
    "search_student_record", "search_statistics_uam",
})


class TestInventaireOutils:

    def test_quarante_cinq_outils_inconditionnels(self):
        assert len(NOMS_OUTILS_INCONDITIONNELS) == 45

    def test_quatre_outils_conditionnels(self):
        assert len(NOMS_OUTILS_BASE) == 4

    def test_aucun_chevauchement_entre_les_deux_groupes(self):
        assert not (NOMS_OUTILS_INCONDITIONNELS & NOMS_OUTILS_BASE)

    def test_tous_les_outils_exposes_quand_la_base_est_disponible(self):
        import tools
        with patch.object(tools, "_db_available", True):
            noms = {t.name for t in tools.get_tools()}
        assert noms == NOMS_OUTILS_INCONDITIONNELS | NOMS_OUTILS_BASE
        assert len(noms) == 49

    def test_seuls_les_inconditionnels_quand_la_base_est_absente(self):
        import tools
        with patch.object(tools, "_db_available", False):
            noms = {t.name for t in tools.get_tools()}
        assert noms == NOMS_OUTILS_INCONDITIONNELS
        assert len(noms) == 45

    def test_aucun_doublon_dans_la_liste(self):
        import tools
        with patch.object(tools, "_db_available", True):
            noms = [t.name for t in tools.get_tools()]
        assert len(noms) == len(set(noms))

    def test_chaque_outil_a_une_description_non_vide(self):
        import tools
        with patch.object(tools, "_db_available", True):
            for t in tools.get_tools():
                assert t.description and t.description.strip(), f"{t.name} sans description"
```

- [ ] **Step 2: Lancer et corriger la liste de référence si elle diverge**

```bash
venv/bin/python -m pytest tests/test_inventaire_outils.py -v
```

Si un test de cardinalité échoue, **ne pas modifier `tools.py`** : la liste ci-dessus est une hypothèse issue de l'audit, et c'est elle qu'il faut corriger pour refléter la réalité. Afficher la vérité pour trancher :

```bash
venv/bin/python -c "
import tools
from unittest.mock import patch
with patch.object(tools, '_db_available', True):
    noms = sorted(t.name for t in tools.get_tools())
print(len(noms)); [print(' ', n) for n in noms]
"
```

- [ ] **Step 3: Vérifier la suite complète**

```bash
venv/bin/python -m pytest tests/ -q
```

Attendu : `39 passed` (32 existants + 7 nouveaux).

Ne pas créer de `tests/conftest.py` : chaque fichier de test construit ses propres doubles au plus près de son usage, et les fichiers existants font déjà leur propre `sys.path.insert`. Un conftest de fixtures partagées n'aurait aucun consommateur.

- [ ] **Step 4: Commit**

```bash
git add tests/test_inventaire_outils.py
git commit -m "test: inventaire des outils, garde-fou du découpage de tools.py"
```

---

### Task 6: Caractérisation des outils déterministes

**Files:**
- Create: `tests/test_outils_deterministes.py`

**Interfaces:**
- Consumes: les outils `detect_greeting`, `detect_user_profile`, `check_question_relevance`, `detect_frustration_or_confusion`, `calculate_fees`, `get_faculty_info`, `get_structure_by_abbreviation`, `list_all_structures` de `tools`
- Produces: rien

Ces outils sont des fonctions à base d'expressions régulières et de dictionnaires : aucun appel réseau, aucun LLM. On les appelle via `.func(...)`, comme le fait [graph_nodes.py:199](../../../graph_nodes.py#L199), pour contourner la validation Pydantic.

- [ ] **Step 1: Observer le comportement actuel avant d'écrire quoi que ce soit**

```bash
venv/bin/python -c "
from tools import detect_greeting, detect_user_profile, check_question_relevance, detect_frustration_or_confusion
cas = ['Bonjour', 'Au revoir', 'Merci beaucoup', 'Bonjour, quels sont les frais ?',
       'Je ne comprends rien', 'Quelle est la recette du couscous ?',
       'Je veux faire un master venant d une autre universite',
       'Je veux faire une these', 'Je suis etranger et je veux etudier a l UAM',
       'Quels sont les frais d inscription en licence ?']
for c in cas:
    print(repr(c))
    print('   greeting  :', detect_greeting.func(message=c))
    print('   profil    :', detect_user_profile.func(message=c))
    print('   pertinence:', check_question_relevance.func(question=c))
    print('   sentiment :', detect_frustration_or_confusion.func(message=c))
"
```

**Consigner la sortie réelle.** Les assertions du step 2 doivent refléter ce qui sort, pas ce qu'on espère. Si une sortie paraît fautive — par exemple une question UAM classée `HORS_SUJET` — **ne pas l'écrire en test vert** : l'inscrire comme bug dans `docs/superpowers/audit/2026-08-16-audit.md`, section 5, et l'omettre du fichier de test.

- [ ] **Step 2: Écrire les tests de caractérisation**

```python
# tests/test_outils_deterministes.py
"""Caractérisation des outils sans dépendance externe.

Ces tests figent le comportement ACTUEL, pas le comportement idéal. Un
comportement jugé fautif ne figure pas ici : il part dans la liste des bugs.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDetectGreeting:

    @pytest.mark.parametrize("message,attendu", [
        ("Bonjour", "GREETING"),
        ("Salut", "GREETING"),
        ("Au revoir", "FAREWELL"),
        ("Merci beaucoup", "THANKS"),
    ])
    def test_categories_principales(self, message, attendu):
        from tools import detect_greeting
        assert detect_greeting.func(message=message) == attendu

    def test_question_sans_salutation(self):
        from tools import detect_greeting
        resultat = detect_greeting.func(message="Quels sont les frais d'inscription ?")
        assert resultat not in ("GREETING", "FAREWELL", "THANKS")


class TestDetectUserProfile:

    @pytest.mark.parametrize("message,attendu", [
        ("Je viens d'une autre université et je veux faire un master", "CANDIDAT_MASTER"),
        ("Je souhaite faire une thèse de doctorat", "CANDIDAT_DOCTORAT"),
    ])
    def test_profils_speciaux(self, message, attendu):
        from tools import detect_user_profile
        assert detect_user_profile.func(message=message) == attendu

    def test_message_neutre_donne_inconnu(self):
        from tools import detect_user_profile
        assert detect_user_profile.func(message="Bonjour") == "INCONNU"


class TestCheckQuestionRelevance:

    def test_question_uam_pertinente(self):
        from tools import check_question_relevance
        assert check_question_relevance.func(
            question="Quels sont les frais d'inscription en licence à l'UAM ?"
        ) == "PERTINENT"

    def test_question_hors_sujet(self):
        from tools import check_question_relevance
        assert check_question_relevance.func(
            question="Quelle est la recette du couscous ?"
        ) == "HORS_SUJET"


class TestStructures:

    def test_abreviation_connue(self):
        from tools import get_structure_by_abbreviation
        resultat = get_structure_by_abbreviation.func(abbreviation="FAST")
        assert "FAST" in resultat or "Sciences" in resultat

    def test_abreviation_inconnue_ne_leve_pas(self):
        from tools import get_structure_by_abbreviation
        resultat = get_structure_by_abbreviation.func(abbreviation="ZZZZ")
        assert isinstance(resultat, str) and resultat

    def test_liste_des_structures_non_vide(self):
        from tools import list_all_structures
        resultat = list_all_structures.func()
        assert "FAST" in resultat

    def test_info_faculte(self):
        from tools import get_faculty_info
        resultat = get_faculty_info.func(faculty_name="FAST")
        assert isinstance(resultat, str) and len(resultat) > 20


class TestCalculateFees:

    def test_licence_retourne_un_montant(self):
        from tools import calculate_fees
        resultat = calculate_fees.func(level="licence")
        assert isinstance(resultat, str) and resultat.strip()

    def test_niveau_inconnu_ne_leve_pas(self):
        from tools import calculate_fees
        resultat = calculate_fees.func(level="niveau_inexistant")
        assert isinstance(resultat, str) and resultat.strip()
```

- [ ] **Step 3: Lancer et ajuster aux sorties réelles**

```bash
venv/bin/python -m pytest tests/test_outils_deterministes.py -v
```

Pour tout échec : ajuster l'assertion à la sortie réelle observée au step 1, **jamais le code source**. Si l'écart révèle un comportement fautif, supprimer le test concerné et inscrire le bug dans le rapport d'audit.

- [ ] **Step 4: Vérifier la suite complète et le temps d'exécution**

```bash
venv/bin/python -m pytest tests/ -q --durations=5
```

Attendu : tout au vert, exécution totale sous 10 secondes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_outils_deterministes.py docs/superpowers/audit/2026-08-16-audit.md
git commit -m "test: caractérisation des outils déterministes"
```

---

### Task 7: Caractérisation du routage

**Files:**
- Create: `tests/test_routage.py`

**Interfaces:**
- Consumes: `graph_nodes.route_and_store(state) -> dict`
- Produces: rien

`route_and_store` retourne **uniquement** `{"routing_hint", "routing_context", "user_profile"}` — jamais l'état complet (contrainte globale 6). Les tests le vérifient explicitement.

- [ ] **Step 1: Écrire les tests**

```python
# tests/test_routage.py
"""Caractérisation de route_and_store — le nœud d'entrée du graphe."""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _etat(question: str) -> dict:
    """État minimal accepté par route_and_store."""
    return {"messages": [HumanMessage(content=question)]}


class TestContratDeRetour:

    def test_ne_retourne_que_les_trois_champs_modifies(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quels sont les frais d'inscription ?"))
        assert set(resultat.keys()) == {"routing_hint", "routing_context", "user_profile"}

    def test_ne_reexpedie_jamais_les_messages(self):
        """Renvoyer messages le ferait passer dans le réducteur `add`, qui
        concatène : l'historique doublerait à chaque tour."""
        from graph_nodes import route_and_store
        assert "messages" not in route_and_store(_etat("Bonjour"))


class TestRoutage:

    def test_abreviation_seule_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("FAST"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "DIRECT_STRUCTURE:FAST"

    def test_adieu_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Au revoir"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "FAREWELL"

    def test_remerciement_va_en_cas_special(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Merci beaucoup"))
        assert resultat["routing_hint"] == "handle_special_case"
        assert resultat["routing_context"] == "THANKS"

    def test_salutation_simple_va_a_l_agent(self):
        from graph_nodes import route_and_store
        assert route_and_store(_etat("Bonjour"))["routing_hint"] == "agent"

    def test_question_uam_va_a_l_agent(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quels sont les frais d'inscription en licence ?"))
        assert resultat["routing_hint"] == "agent"

    def test_question_hors_sujet_est_rejetee(self):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat("Quelle est la recette du couscous ?"))
        assert resultat["routing_hint"] == "reject_query"

    def test_etat_sans_message_est_rejete(self):
        from graph_nodes import route_and_store
        assert route_and_store({"messages": []})["routing_hint"] == "reject_query"

    def test_question_vide_est_rejetee(self):
        from graph_nodes import route_and_store
        assert route_and_store(_etat("   "))["routing_hint"] == "reject_query"

    @pytest.mark.parametrize("question,profil", [
        ("Je viens d'une autre université et je veux faire un master", "CANDIDAT_MASTER"),
        ("Je souhaite faire une thèse de doctorat à l'UAM", "CANDIDAT_DOCTORAT"),
    ])
    def test_profils_speciaux_sont_memorises(self, question, profil):
        from graph_nodes import route_and_store
        resultat = route_and_store(_etat(question))
        assert resultat["user_profile"] == profil
        assert resultat["routing_hint"] == "agent"

    def test_exception_interne_retombe_sur_un_rejet(self):
        """Un message sans attribut content ne doit pas faire remonter d'exception."""
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [object()]})
        assert resultat["routing_hint"] in ("reject_query", "agent")
```

- [ ] **Step 2: Lancer et ajuster aux sorties réelles**

```bash
venv/bin/python -m pytest tests/test_routage.py -v
```

Même règle qu'à la tâche 6 : on ajuste les assertions, jamais le code. Les tests `TestContratDeRetour` font exception — s'ils échouent, c'est un bug grave (l'explosion d'historique documentée dans `CLAUDE.md`) : l'inscrire immédiatement dans le rapport d'audit avec la gravité `critique`.

- [ ] **Step 3: Vérifier la suite complète**

```bash
venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_routage.py
git commit -m "test: caractérisation du routage conversationnel"
```

---

### Task 8: Caractérisation de l'historique et du contrat des nœuds

**Files:**
- Create: `tests/test_historique.py`

**Interfaces:**
- Consumes: `graph_nodes._compress_history(messages, max_size)`, `graph_nodes._truncate_history`, `graph_nodes.should_continue`
- Produces: rien

- [ ] **Step 1: Écrire les tests**

```python
# tests/test_historique.py
"""Caractérisation de la compression d'historique.

Le correctif d'origine visait une explosion mesurée en session réelle :
1 → 2 → 4 → … → 83 608 messages. Ces tests en sont la sentinelle.
"""
import ast
import os
import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _ai_avec_appel(nom: str = "search_uam_knowledge") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": nom, "args": {"query": "x"}, "id": "call_1"}],
    )


class TestCompressHistory:

    def test_historique_court_est_inchange(self):
        from graph_nodes import _compress_history
        messages = [HumanMessage(content="Bonjour"), AIMessage(content="Salut")]
        assert _compress_history(messages) == messages

    def test_les_tool_messages_des_tours_passes_sont_retires(self):
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat volumineux", tool_call_id="call_1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
        ]
        resultat = _compress_history(messages)
        assert not any(isinstance(m, ToolMessage) for m in resultat)

    def test_les_ai_porteurs_d_appels_partent_avec_leurs_resultats(self):
        """L'API refuse un message annonçant des tool_calls sans ses résultats."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat", tool_call_id="call_1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
        ]
        resultat = _compress_history(messages)
        assert not any(getattr(m, "tool_calls", None) for m in resultat)

    def test_le_tour_courant_est_intact(self):
        """Pendant la boucle ReAct, le LLM doit voir les résultats qu'il vient
        d'obtenir : tout ce qui suit le dernier message utilisateur est préservé."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Question 1"),
            AIMessage(content="Réponse 1"),
            HumanMessage(content="Question 2"),
            _ai_avec_appel(),
            ToolMessage(content="Résultat du tour courant", tool_call_id="call_1"),
        ]
        resultat = _compress_history(messages)
        assert any(isinstance(m, ToolMessage) for m in resultat)
        assert resultat[-1].content == "Résultat du tour courant"

    def test_troncature_respecte_la_taille_maximale(self):
        from graph_nodes import _compress_history
        messages = [HumanMessage(content=f"Q{i}") for i in range(50)]
        assert len(_compress_history(messages, max_size=10)) <= 10

    def test_aucun_tool_message_orphelin_apres_compression(self):
        """Un ToolMessage sans l'AIMessage qui l'a demandé provoque une 400."""
        from graph_nodes import _compress_history
        messages = [
            HumanMessage(content="Q1"), _ai_avec_appel(),
            ToolMessage(content="R1", tool_call_id="call_1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"), _ai_avec_appel(),
            ToolMessage(content="R2", tool_call_id="call_1"),
            AIMessage(content="A2"),
            HumanMessage(content="Q3"),
        ]
        resultat = _compress_history(messages, max_size=5)
        for i, m in enumerate(resultat):
            if isinstance(m, ToolMessage):
                precedents = resultat[:i]
                assert any(getattr(p, "tool_calls", None) for p in precedents), \
                    "ToolMessage orphelin : l'API rejettera la requête"

    def test_liste_vide(self):
        from graph_nodes import _compress_history
        assert _compress_history([]) == []


class TestAliasHistorique:

    def test_truncate_history_reste_disponible(self):
        """evaluate.py importe encore ce nom : le retirer casserait le volet
        évaluation, gelé par la contrainte globale 7."""
        from graph_nodes import _compress_history, _truncate_history
        messages = [HumanMessage(content="Q"), AIMessage(content="R")]
        assert _truncate_history(messages) == _compress_history(messages)


class TestContratDesNoeuds:

    def test_aucun_noeud_ne_retourne_l_etat_complet(self):
        """Détecte `return {**state, ...}` — la cause de l'explosion d'historique."""
        chemin = os.path.join(os.path.dirname(__file__), "..", "graph_nodes.py")
        arbre = ast.parse(open(chemin, encoding="utf-8").read())

        fautifs = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Return) and isinstance(noeud.value, ast.Dict):
                # une clé None correspond à un dépaquetage **quelque_chose
                if any(cle is None for cle in noeud.value.keys):
                    fautifs.append(noeud.lineno)
        assert not fautifs, f"Dépaquetage d'état interdit aux lignes {fautifs}"
```

- [ ] **Step 2: Lancer**

```bash
venv/bin/python -m pytest tests/test_historique.py -v
```

Un échec sur `test_aucun_tool_message_orphelin_apres_compression` ou sur `TestContratDesNoeuds` est un bug de gravité `critique` : l'inscrire au rapport d'audit et **ne pas ajuster le test pour le faire passer**.

- [ ] **Step 3: Vérifier la suite complète**

```bash
venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_historique.py
git commit -m "test: caractérisation de la compression d'historique et du contrat des nœuds"
```

---

### Task 9: Caractérisation du service d'API

**Files:**
- Create: `tests/test_agent_service.py`

**Interfaces:**
- Consumes: `api.agent_service.answer(question, session_id)`, `api.agent_service.get_agent()`
- Produces: rien

Le service construit l'agent une seule fois via un singleton, ce qui charge le modèle d'embeddings (~1 Go) et l'index FAISS. Les tests doivent **remplacer ce singleton**, jamais le déclencher.

- [ ] **Step 1: Repérer le nom exact du singleton avant d'écrire**

```bash
grep -n "def get_agent\|_agent\b\|_agent =\|global _agent" api/agent_service.py | head -20
```

Adapter les noms patchés du step 2 à ce que révèle cette commande.

- [ ] **Step 2: Écrire les tests**

```python
# tests/test_agent_service.py
"""Caractérisation de la couche de service partagée.

Aucun test ne construit le vrai agent : cela chargerait le modèle
d'embeddings HuggingFace et l'index FAISS.
"""
import os
import sys
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _faux_graphe(reponse: str = "Réponse de test."):
    """Graphe LangGraph factice : invoke() retourne un état terminé."""
    graphe = MagicMock()
    graphe.invoke.return_value = {
        "messages": [AIMessage(content=reponse)],
        "is_relevant": True,
    }
    return graphe


class TestAnswer:

    def test_retourne_une_reponse_textuelle(self):
        import api.agent_service as service
        with patch.object(service, "get_agent", return_value=_faux_graphe()):
            resultat = service.answer("Quels sont les frais ?", session_id="s1")
        texte = resultat if isinstance(resultat, str) else resultat.get("response", "")
        assert isinstance(texte, str) and texte.strip()

    def test_le_session_id_devient_le_thread_id(self):
        """La persistance LangGraph repose entièrement sur ce passage."""
        import api.agent_service as service
        graphe = _faux_graphe()
        with patch.object(service, "get_agent", return_value=graphe):
            service.answer("Bonjour", session_id="session-abc")
        _, kwargs = graphe.invoke.call_args
        config = kwargs.get("config") or {}
        assert config.get("configurable", {}).get("thread_id") == "session-abc"

    def test_deux_sessions_restent_distinctes(self):
        import api.agent_service as service
        graphe = _faux_graphe()
        with patch.object(service, "get_agent", return_value=graphe):
            service.answer("Bonjour", session_id="session-1")
            service.answer("Bonjour", session_id="session-2")
        threads = [
            (kwargs.get("config") or {}).get("configurable", {}).get("thread_id")
            for _, kwargs in graphe.invoke.call_args_list
        ]
        assert threads == ["session-1", "session-2"]

    def test_une_erreur_du_graphe_ne_remonte_pas_brute(self):
        import api.agent_service as service
        graphe = MagicMock()
        graphe.invoke.side_effect = RuntimeError("panne simulée")
        with patch.object(service, "get_agent", return_value=graphe):
            try:
                resultat = service.answer("Bonjour", session_id="s-erreur")
            except RuntimeError:
                raise AssertionError("l'erreur brute atteint l'appelant")
        texte = resultat if isinstance(resultat, str) else resultat.get("response", "")
        assert isinstance(texte, str)
```

- [ ] **Step 3: Lancer et adapter à la signature réelle**

```bash
venv/bin/python -m pytest tests/test_agent_service.py -v
```

`answer()` peut retourner une chaîne ou un dictionnaire : les tests acceptent les deux formes, mais si l'exécution révèle une troisième forme, adapter les assertions à la réalité. Si `answer()` laisse remonter une exception brute, c'est un bug — l'inscrire au rapport et retirer le test correspondant.

- [ ] **Step 4: Vérifier la suite et le temps**

```bash
venv/bin/python -m pytest tests/ -q --durations=5
```

Attendu : sous 10 secondes. Si le temps explose, un test construit le vrai agent : corriger le patch.

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_service.py
git commit -m "test: caractérisation du service d'API et de l'isolation des sessions"
```

---

### Task 10: Caractérisation du connecteur de base

**Files:**
- Create: `tests/test_database_connector.py`

**Interfaces:**
- Consumes: `database_connector.is_database_available()`, `search_formations_db`, `search_students_db`, `search_fees_db`, `get_official_stats_db`, `search_news_announcements_db`
- Produces: rien

Ces tests lisent la vraie base `database/scolarite_uam.db` — en lecture seule. Ils n'écrivent jamais.

- [ ] **Step 1: Écrire les tests**

```python
# tests/test_database_connector.py
"""Caractérisation du connecteur scolarité, en lecture seule sur la base réelle."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CHEMIN_BASE = os.path.join(os.path.dirname(__file__), "..", "database", "scolarite_uam.db")

pytestmark = pytest.mark.skipif(
    not os.path.exists(CHEMIN_BASE),
    reason="database/scolarite_uam.db absente",
)


class TestDisponibilite:

    def test_la_base_est_declaree_disponible(self):
        from database_connector import is_database_available
        assert is_database_available() is True


class TestRequetes:

    def test_les_formations_reviennent_sous_forme_de_liste(self):
        from database_connector import search_formations_db
        resultat = search_formations_db()
        assert isinstance(resultat, list)
        if resultat:
            assert isinstance(resultat[0], dict)

    def test_les_statistiques_officielles_sont_lisibles(self):
        """La table statistiques_composantes n'existe que dans la base racine."""
        from database_connector import get_official_stats_db
        resultat = get_official_stats_db()
        assert isinstance(resultat, list)

    def test_les_frais_reviennent_sous_forme_de_liste(self):
        from database_connector import search_fees_db
        assert isinstance(search_fees_db(), list)

    def test_un_matricule_inexistant_retourne_une_liste_vide(self):
        from database_connector import search_students_db
        assert search_students_db(matricule="MATRICULE_INEXISTANT_XYZ") == []


class TestActualites:

    def test_les_actualites_retournent_une_liste_vide_sur_sqlite(self):
        """Caractérisation de BUG-01 : la table announcements n'existe pas en
        SQLite, l'outil ne peut donc rien retourner. La tâche 14 cessera de
        l'exposer au LLM ; ce test restera valide, seul l'inventaire changera."""
        from database_connector import search_news_announcements_db
        assert search_news_announcements_db() == []
```

- [ ] **Step 2: Lancer**

```bash
venv/bin/python -m pytest tests/test_database_connector.py -v
```

- [ ] **Step 3: Vérifier la suite et compter les tests**

```bash
venv/bin/python -m pytest tests/ -q --durations=5
```

Attendu : entre 80 et 120 tests au total, sous 10 secondes. Si le compte est inférieur à 80, ajouter des cas de caractérisation aux fichiers des tâches 6 à 10 sur les zones les moins couvertes — en respectant la règle : jamais figer un comportement fautif.

- [ ] **Step 4: Commit**

```bash
git add tests/test_database_connector.py
git commit -m "test: caractérisation du connecteur de base scolarité"
```

---

## Phase 3 — Découpage de `tools.py`

### Task 11: Création du package `tools/`

**Files:**
- Create: `tools/__init__.py`, `tools/_vectorstore.py`, `tools/_session.py`, `tools/_rag.py`, `tools/_db.py`, `tools/recherche.py`, `tools/conversation.py`, `tools/structures.py`, `tools/scolarite.py`, `tools/programmes.py`, `tools/parcours.py`, `tools/base_donnees.py`, `tools/preferences.py`
- Delete: `tools.py`

**Interfaces:**
- Consumes: le test d'inventaire de la tâche 5, qui doit passer sans être modifié
- Produces: le package `tools`, dont l'API publique est identique à celle de `tools.py` : `get_tools()`, `set_vectorstore(vectorstore)`, `set_session_user_id(user_id)`, `get_session_user_id()`, `_rag_response(query, message_si_vide)`, `_vectorstore`, `_db_available`, et les 49 outils

**Déplacement pur.** Le corps des fonctions n'est pas modifié : ni renommage, ni reformulation de docstring, ni « amélioration » au passage. Toute retouche de logique est un défaut.

- [ ] **Step 1: Enregistrer l'empreinte de référence AVANT de toucher à quoi que ce soit**

```bash
venv/bin/python -c "
import hashlib, inspect, tools
from unittest.mock import patch
with patch.object(tools, '_db_available', True):
    outils = sorted(tools.get_tools(), key=lambda t: t.name)
for t in outils:
    corps = inspect.getsource(t.func)
    print(t.name, hashlib.md5(corps.encode()).hexdigest())
" > /tmp/empreinte_avant.txt
wc -l /tmp/empreinte_avant.txt
```

Attendu : 49 lignes. Ce fichier est la preuve que le déplacement n'a rien altéré.

- [ ] **Step 2: Créer les modules d'infrastructure**

```python
# tools/_vectorstore.py
"""État global du vectorstore FAISS, partagé par les modules d'outils."""
import threading

from langchain_community.vectorstores import FAISS
from langsmith import traceable

from logger_config import get_logger

logger = get_logger(__name__)

_vectorstore = None
_vectorstore_lock = threading.Lock()


@traceable
def set_vectorstore(vectorstore: FAISS):
    """Définit le vectorstore global pour les outils (thread-safe)"""
    global _vectorstore
    with _vectorstore_lock:
        _vectorstore = vectorstore


def get_vectorstore():
    """Retourne le vectorstore global courant."""
    return _vectorstore
```

```python
# tools/_session.py
"""Identifiant de session propagé aux outils.

Un ContextVar et non un threading.local : le ToolNode exécute les outils dans
un pool de threads, qui héritent du contexte mais pas du stockage par thread.
"""
import contextvars

_session_user_id: contextvars.ContextVar = contextvars.ContextVar(
    "session_user_id", default="default_user"
)


def set_session_user_id(user_id: str) -> None:
    """Associe un user_id à la session courante."""
    _session_user_id.set(user_id)


def get_session_user_id() -> str:
    """Retourne le user_id de la session courante."""
    return _session_user_id.get()
```

Reprendre le corps exact de ces fonctions depuis `tools.py` lignes 61-88 et 114 et suivantes. Créer de même `tools/_db.py` en y déplaçant **à l'identique** le bloc `try/except` des lignes 90-110 de `tools.py`, qui importe `database_connector` et fixe `_db_available`, puis `tools/_rag.py` en y déplaçant `_rag_response`.

- [ ] **Step 3: Déplacer les outils, domaine par domaine**

Un module à la fois, dans cet ordre : `recherche.py`, `conversation.py`, `structures.py`, `preferences.py`, `parcours.py`, `programmes.py`, `scolarite.py`, `base_donnees.py`.

Pour chacun : couper les fonctions concernées de `tools.py`, les coller dans le nouveau module, ajouter en tête les imports dont elles ont besoin (`from langchain_core.tools import tool`, `from ._rag import _rag_response`, `from ._db import _db_available`, etc.). La répartition exacte figure dans la section « Architecture cible » du spec.

Après **chaque** module déplacé :

```bash
venv/bin/python -c "import tools; print(len(tools.get_tools()))"
```

- [ ] **Step 4: Écrire `tools/__init__.py`**

```python
# tools/__init__.py
"""Outils exposés au LLM, regroupés par domaine.

L'API publique est identique à celle de l'ancien module tools.py : les modules
appelants continuent d'écrire `from tools import get_tools, set_vectorstore`.
"""
from ._db import _db_available
from ._rag import _rag_response
from ._session import get_session_user_id, set_session_user_id
from ._vectorstore import _vectorstore, get_vectorstore, set_vectorstore

from .base_donnees import (
    get_schedules_from_db, search_latest_news, search_statistics_uam,
    search_student_record,
)
from .conversation import (
    check_question_relevance, detect_frustration_or_confusion, detect_greeting,
    detect_user_profile, get_agent_capabilities,
)
from .parcours import (
    search_academic_partnership, search_external_student_master,
    search_foreign_student_procedures, search_master_thesis_supervision,
    search_phd_admission, search_recognition_prior_learning,
)
from .preferences import get_user_preferences, save_user_preference
from .programmes import (
    search_avantages_universite, search_chronogramme, search_coefficients,
    search_competences_requises, search_cycles_et_duree, search_debouches,
    search_organisation_corps_estudiantin, search_organisation_corps_professoral,
    search_prerequisites, search_professeurs, search_reclamations,
    search_reglement_interieur,
)
from .recherche import search_uam_knowledge
from .scolarite import (
    calculate_fees, generate_registration_checklist,
    search_admission_requirements, search_contacts_services, search_double_degree,
    search_formations, search_housing_and_services, search_international_equivalence,
    search_internship_info, search_late_reenrollment, search_registration_calendar,
    search_registration_procedure, search_required_documents, search_scholarships,
    search_student_card, search_transfer_equivalence,
)
from .structures import (
    get_faculty_info, get_structure_by_abbreviation, list_all_structures,
)


def get_tools():
    """Retourne la liste des outils disponibles pour l'agent"""
    outils = [
        # Détection et profiling conversationnel
        detect_greeting, detect_user_profile, detect_frustration_or_confusion,
        get_agent_capabilities, check_question_relevance,

        # Recherche générale
        search_uam_knowledge, get_faculty_info, get_structure_by_abbreviation,
        list_all_structures,

        # Formations et filières
        search_formations, search_prerequisites, search_competences_requises,
        search_cycles_et_duree, search_chronogramme, search_coefficients,
        search_debouches, search_avantages_universite,

        # Admission et inscription
        search_admission_requirements, search_required_documents,
        search_registration_procedure, search_registration_calendar,
        search_late_reenrollment, generate_registration_checklist, calculate_fees,

        # Étudiants externes / étrangers / master / doctorat
        search_external_student_master, search_phd_admission,
        search_foreign_student_procedures, search_recognition_prior_learning,
        search_master_thesis_supervision, search_academic_partnership,
        search_international_equivalence, search_transfer_equivalence,

        # Documents et démarches
        search_student_card, search_internship_info, search_double_degree,
        search_reclamations,

        # Services et vie étudiante
        search_housing_and_services, search_scholarships, search_contacts_services,

        # Corps universitaire
        search_professeurs, search_organisation_corps_professoral,
        search_organisation_corps_estudiantin, search_reglement_interieur,

        # Mémoire utilisateur
        save_user_preference, get_user_preferences,
    ]

    # Ajouter les outils de base de données si disponible
    if _db_available:
        outils.extend([
            search_latest_news, get_schedules_from_db,
            search_student_record, search_statistics_uam,
        ])

    return outils
```

**Le style d'import du drapeau est imposé, il n'est pas un détail.** Écrire
`from ._db import _db_available` en tête de `tools/__init__.py`, et lire le nom nu
`_db_available` dans `get_tools()`. Toute autre forme casse le garde-fou de la
tâche 5.

Pourquoi : `from ._db import _db_available` lie le nom dans le namespace du module
importateur — or `tools/__init__.py` **est** le module `tools`, donc cette liaison
est littéralement `tools.__dict__["_db_available"]`. Le `patch.object(tools,
"_db_available", ...)` du test d'inventaire modifie cette entrée précise, et
`get_tools()`, définie dans ce même module, résout le nom nu contre ce même
namespace à l'appel. Le test continue donc de fonctionner sans modification —
vérifié empiriquement en revue de la tâche 5, sur un paquet factice reproduisant
cette structure : les 7 tests passent inchangés.

La forme concurrente `from . import _db` avec `_db._db_available` dans `get_tools()`
fait échouer 4 tests sur 7 avec `AttributeError: module 'tools' does not have the
attribute '_db_available'`. L'échec est bruyant, donc impossible à manquer.

**Si ce cas se produit, la correction est de changer l'import, jamais le test.**
Le fichier `tests/test_inventaire_outils.py` ne doit pas être modifié par cette
tâche : c'est lui qui atteste que le découpage n'a rien égaré, et un garde-fou
qu'on ajuste pour qu'il passe ne prouve plus rien. Une modification de ce fichier
dans cette tâche est un défaut Critical.

**Ne pas affaiblir `test_seuls_les_inconditionnels_quand_la_base_est_absente`.**
La revue de la tâche 5 a établi que ce test est le seul des sept à détecter qu'un
outil aurait changé de lot — inconditionnel devenu conditionnel, ou l'inverse.
Son jumeau `test_tous_les_outils_exposes_quand_la_base_est_disponible` est
structurellement aveugle à cette erreur, puisqu'il compte 49 outils quelle que
soit la branche qui les a fournis.

- [ ] **Step 5: Supprimer `tools.py` et vérifier l'équivalence**

```bash
git rm tools.py
venv/bin/python -c "
import hashlib, inspect, tools
from unittest.mock import patch
with patch.object(tools, '_db_available', True):
    outils = sorted(tools.get_tools(), key=lambda t: t.name)
for t in outils:
    corps = inspect.getsource(t.func)
    print(t.name, hashlib.md5(corps.encode()).hexdigest())
" > /tmp/empreinte_apres.txt
diff /tmp/empreinte_avant.txt /tmp/empreinte_apres.txt && echo "IDENTIQUE"
```

Attendu : `IDENTIQUE`. Toute divergence signale qu'un corps de fonction a été modifié pendant le déplacement — la corriger avant d'aller plus loin.

- [ ] **Step 6: Vérifier que rien d'autre n'a bougé**

```bash
venv/bin/python -m pytest tests/ -q
venv/bin/python -c "
import importlib
for m in ('agent_graph','graph_nodes','agent_uam','app_streamlit','api.agent_service','chatbot','evaluate','run_grounding_capture'):
    importlib.import_module(m); print('ok', m)
"
git diff --stat HEAD -- agent_graph.py graph_nodes.py agent_uam.py app_streamlit.py api/agent_service.py
```

Attendu : suite au vert, `ok` pour les 8 modules, et **aucune modification** des fichiers appelants — c'est la preuve que le découpage est transparent.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(tools): découpage de tools.py en package par domaine"
```

---

## Phase 4 — Correction des bugs

### Task 12: Correction des bugs inventoriés

**Files:**
- Modify: dépend du rapport d'audit — les fichiers désignés par la colonne `fichier:ligne suspecté` de la section 5
- Test: un fichier `tests/test_bug_<identifiant>.py` par bug, ou un ajout au fichier de test du module concerné

**Interfaces:**
- Consumes: la section 5 « Bugs constatés » de `docs/superpowers/audit/2026-08-16-audit.md`
- Produces: un test de non-régression par bug corrigé

Le contenu de cette tâche est déterminé par l'audit : le plan ne peut pas inventer des bugs qu'on n'a pas encore observés. Ce qui est fixé, c'est le **protocole**, identique pour chacun.

- [ ] **Step 1: Ordonner les bugs**

Lire la section 5 du rapport et trier par gravité décroissante (`critique`, puis `haute`, `moyenne`, `basse`). Traiter dans cet ordre.

Deux bugs sont **exclus** de cette tâche, car traités ailleurs :

- `BUG-01` (`search_latest_news` inerte sur SQLite) relève de la tâche 14, avec les autres décisions sur les outils conditionnels.
- `BUG-03` (questions sur les frais rejetées) relève de la **tâche 17**, remontée en priorité avant le découpage de `tools.py`. Vérifier son état dans le rapport avant de commencer : s'il y est marqué `corrigé`, ne rien reprendre.

Tout bug déjà marqué `corrigé` dans la section 5 est hors périmètre, quelle que soit sa gravité.

- [ ] **Step 2: Pour chaque bug — écrire le test qui échoue**

Le test reproduit la manifestation décrite dans le rapport. Exemple de forme attendue, pour un bug de saturation de boucle d'outils :

```python
# tests/test_bug_02.py
"""BUG-02 : la boucle d'outils atteint sa limite sans produire de réponse.

Manifestation consignée dans docs/superpowers/audit/2026-08-16-audit.md.
"""
import os
import sys

from langchain_core.messages import AIMessage, HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_saturation_de_boucle_produit_une_reponse_utilisable():
    from graph_nodes import should_continue

    etat = {
        "messages": [HumanMessage(content="Question"), AIMessage(content="")],
        "tool_iterations": 5,
    }
    assert should_continue(etat) == "end", (
        "à la limite d'itérations, le graphe doit terminer et non rappeler les outils"
    )
```

- [ ] **Step 3: Exécuter le test et vérifier qu'il ÉCHOUE**

```bash
venv/bin/python -m pytest tests/test_bug_<identifiant>.py -v
```

Attendu : `FAILED`. **Un test qui passe du premier coup ne démontre rien** : soit le bug n'existe pas et il faut le retirer du rapport avec la mention « non reproductible », soit le test ne reproduit pas la bonne situation et il faut le réécrire.

- [ ] **Step 4: Corriger, au plus près**

Modifier le minimum nécessaire pour faire passer le test. Ne pas en profiter pour réorganiser le module alentour : cette tâche corrige, elle ne refactorise pas.

- [ ] **Step 5: Vérifier que le test passe et que rien d'autre ne casse**

```bash
venv/bin/python -m pytest tests/test_bug_<identifiant>.py -v
venv/bin/python -m pytest tests/ -q
```

Attendu : le test cible au vert, et l'intégralité de la suite au vert. Si un test de caractérisation des tâches 5 à 10 casse, c'est que la correction change un comportement figé : arbitrer explicitement — soit la correction est juste et le test de caractérisation figeait le bug (le mettre à jour en le justifiant dans le message de commit), soit la correction va trop loin.

- [ ] **Step 6: Commit, un par bug**

```bash
git add tests/test_bug_<identifiant>.py <fichiers modifiés>
git commit -m "fix: <identifiant> — <manifestation en une ligne>"
```

- [ ] **Step 7: Clore la tâche**

Ajouter au rapport d'audit une colonne `état` renseignée pour chaque bug : `corrigé` (avec le hash du commit), `non reproductible`, ou `reporté` (avec le motif). Aucun bug ne reste sans état.

```bash
git add docs/superpowers/audit/2026-08-16-audit.md
git commit -m "docs(audit): état de traitement des bugs inventoriés"
```

---

## Phase 5 — Fonctionnalités manquantes

### Task 13: Persistance des sessions

**Files:**
- Modify: `agent_graph.py`, `app_config.py`, `requirements.txt`, `.env.example`, `CLAUDE.md`
- Test: `tests/test_persistance.py`

**Interfaces:**
- Consumes: `app_config.get_config()`
- Produces: `AppConfig.checkpointer` (str, `"sqlite"` ou `"memory"`) et `AppConfig.checkpoint_db` (str, chemin), lus par `agent_graph.create_agent_graph`

- [ ] **Step 1: Installer la dépendance**

```bash
venv/bin/pip install langgraph-checkpoint-sqlite
venv/bin/python -c "from langgraph.checkpoint.sqlite import SqliteSaver; print('ok')"
```

Ajouter à `requirements.txt`, sous la ligne `langgraph>=1.0.5` :

```text
langgraph-checkpoint-sqlite>=2.0.0
```

- [ ] **Step 2: Écrire le test de persistance, qui doit échouer**

```python
# tests/test_persistance.py
"""Le checkpointer doit survivre à la reconstruction du graphe."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestConfigurationCheckpointer:

    def test_sqlite_par_defaut(self, monkeypatch):
        monkeypatch.delenv("UAM_CHECKPOINTER", raising=False)
        from app_config import AppConfig
        assert AppConfig.from_env().checkpointer == "sqlite"

    def test_bascule_en_memoire(self, monkeypatch):
        monkeypatch.setenv("UAM_CHECKPOINTER", "memory")
        from app_config import AppConfig
        assert AppConfig.from_env().checkpointer == "memory"

    def test_chemin_par_defaut(self, monkeypatch):
        monkeypatch.delenv("UAM_CHECKPOINT_DB", raising=False)
        from app_config import AppConfig
        assert AppConfig.from_env().checkpoint_db == "./database/checkpoints.db"


class TestSurvieDeLHistorique:

    def test_une_conversation_survit_a_la_reconstruction(self, tmp_path):
        """Cœur de la fonctionnalité : deux graphes successifs pointant sur le
        même fichier doivent partager l'historique du même thread_id."""
        from langgraph.checkpoint.sqlite import SqliteSaver

        chemin = str(tmp_path / "checkpoints.db")
        config = {"configurable": {"thread_id": "session-test"}}

        with SqliteSaver.from_conn_string(chemin) as saver:
            saver.put(
                config,
                {"messages": ["Bonjour"]},
                {"source": "input", "step": 0},
                {},
            )

        with SqliteSaver.from_conn_string(chemin) as saver:
            recupere = saver.get(config)

        assert recupere is not None, "l'historique n'a pas survécu"

    def test_deux_threads_ne_se_melangent_pas(self, tmp_path):
        from langgraph.checkpoint.sqlite import SqliteSaver

        chemin = str(tmp_path / "checkpoints.db")
        with SqliteSaver.from_conn_string(chemin) as saver:
            saver.put(
                {"configurable": {"thread_id": "t1"}},
                {"messages": ["A"]}, {"source": "input", "step": 0}, {},
            )
            assert saver.get({"configurable": {"thread_id": "t2"}}) is None
```

```bash
venv/bin/python -m pytest tests/test_persistance.py -v
```

Attendu : les trois tests de `TestConfigurationCheckpointer` échouent (`AttributeError: checkpointer`).

- [ ] **Step 3: Ajouter la configuration**

Dans `app_config.py`, classe `AppConfig` — ajouter les deux champs et leur lecture dans `from_env()`, sur le modèle exact des champs existants :

```python
    checkpointer: str = "sqlite"
    checkpoint_db: str = "./database/checkpoints.db"
```

```python
            checkpointer=os.getenv("UAM_CHECKPOINTER", "sqlite"),
            checkpoint_db=os.getenv("UAM_CHECKPOINT_DB", "./database/checkpoints.db"),
```

Ajouter aussi les deux clés au dictionnaire retourné par `to_dict()`, comme les autres champs.

- [ ] **Step 4: Brancher le checkpointer dans le graphe**

Dans `agent_graph.py`, remplacer l'import et l'instanciation :

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from app_config import get_config
```

```python
def _build_checkpointer():
    """Construit le checkpointer selon la configuration.

    En SQLite, la connexion doit accepter l'usage multi-thread : uvicorn sert
    les requêtes sur plusieurs threads et le ToolNode exécute les outils dans
    un pool de threads.
    """
    config = get_config()
    if config.checkpointer == "memory":
        return MemorySaver()

    import sqlite3
    from pathlib import Path

    chemin = Path(config.checkpoint_db)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(str(chemin), check_same_thread=False)
    return SqliteSaver(connexion)
```

Puis, à la fin de `create_agent_graph`, remplacer les deux lignes `memory = MemorySaver()` / `app = workflow.compile(checkpointer=memory)` par :

```python
    app = workflow.compile(checkpointer=_build_checkpointer())
```

- [ ] **Step 5: Vérifier**

```bash
venv/bin/python -m pytest tests/test_persistance.py -v
venv/bin/python -m pytest tests/ -q
```

Attendu : tout au vert.

- [ ] **Step 6: Vérifier de bout en bout, sur le vrai service**

```bash
./run_api.sh 8010 &
sleep 45
curl -s -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"question":"Je m appelle Amadou et je veux etudier en licence","session_id":"persistance-1"}' | head -c 400
echo
kill %1; sleep 3
./run_api.sh 8010 &
sleep 45
curl -s -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"question":"Quel est mon prenom ?","session_id":"persistance-1"}' | head -c 400
echo
kill %1
ls -la database/checkpoints.db
```

Attendu : la seconde réponse, **après redémarrage du processus**, mentionne « Amadou ». Le fichier `database/checkpoints.db` existe.

- [ ] **Step 7: Documenter et committer**

Ajouter à `.env.example` :

```text
# Persistance des sessions : "sqlite" (défaut, survit au redémarrage) ou "memory"
UAM_CHECKPOINTER=sqlite
UAM_CHECKPOINT_DB=./database/checkpoints.db
```

Ajouter les deux variables au tableau de `CLAUDE.md`, et y corriger la phrase affirmant que « `MemorySaver` étant en mémoire, redémarrer le processus efface l'historique conversationnel — à remplacer par un `SqliteSaver` pour un service durable » : c'est désormais fait.

Ajouter `database/checkpoints.db` à `.gitignore`.

```bash
git add -A
git commit -m "feat(agent): persistance des sessions par SqliteSaver"
```

---

### Task 14: Outils conditionnés à la base

**Files:**
- Modify: `tools/__init__.py`, `tests/test_inventaire_outils.py`
- Test: `tests/test_inventaire_outils.py`, `tests/test_database_connector.py`

**Interfaces:**
- Consumes: `NOMS_OUTILS_INCONDITIONNELS` et `NOMS_OUTILS_BASE` de la tâche 5 ; `database_connector.is_database_available()`
- Produces: `NOMS_OUTILS_BASE_SQLITE` (frozenset de 3 noms), utilisé par le test d'inventaire

- [ ] **Step 1: Vérifier les trois autres outils conditionnels sur la base réelle**

```bash
venv/bin/python -c "
from tools import search_student_record, search_statistics_uam, get_schedules_from_db
import sqlite3
c = sqlite3.connect('database/scolarite_uam.db')
mat = c.execute('SELECT matricule FROM etudiants LIMIT 1').fetchone()
print('matricule test:', mat)
print('--- search_student_record ---')
print(search_student_record.func(matricule=mat[0])[:300] if mat else 'aucun étudiant')
print('--- search_statistics_uam ---')
print(search_statistics_uam.func()[:300])
print('--- get_schedules_from_db ---')
print(get_schedules_from_db.func()[:300])
"
```

Pour chacun : la sortie correspond-elle à ce que promet sa docstring ? Tout écart est un bug — le traiter dans cette tâche, selon le protocole de la tâche 12 (test rouge, correction, vert).

- [ ] **Step 2: Écrire le test d'inventaire attendu, qui doit échouer**

Ajouter à `tests/test_inventaire_outils.py` :

```python
NOMS_OUTILS_BASE_SQLITE = frozenset({
    "get_schedules_from_db", "search_student_record", "search_statistics_uam",
})


class TestOutilsSqlite:
    """search_latest_news ne peut rien retourner sur SQLite : la table
    announcements n'existe pas (database_connector.py:534). L'exposer au LLM
    lui fait perdre un tour de boucle pour un résultat systématiquement vide."""

    def test_search_latest_news_absent_en_sqlite(self):
        import tools
        from unittest.mock import patch
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", False):
            noms = {t.name for t in tools.get_tools()}
        assert "search_latest_news" not in noms
        assert len(noms) == 48

    def test_les_trois_autres_restent_exposes(self):
        import tools
        from unittest.mock import patch
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", False):
            noms = {t.name for t in tools.get_tools()}
        assert NOMS_OUTILS_BASE_SQLITE <= noms

    def test_search_latest_news_expose_si_le_backend_le_supporte(self):
        import tools
        from unittest.mock import patch
        with patch.object(tools, "_db_available", True), \
             patch.object(tools, "_db_backend_supporte_actualites", True):
            noms = {t.name for t in tools.get_tools()}
        assert "search_latest_news" in noms
        assert len(noms) == 49
```

```bash
venv/bin/python -m pytest tests/test_inventaire_outils.py -v
```

Attendu : les trois nouveaux tests échouent (`AttributeError: _db_backend_supporte_actualites`).

- [ ] **Step 3: Implémenter le drapeau**

Dans `tools/_db.py`, après la détermination de `_db_available` :

```python
# La table `announcements` n'existe que sur les backends documentaires
# (MongoDB). En SQLite, search_news_announcements_db retourne toujours [] :
# exposer l'outil ferait perdre un tour de boucle au LLM pour rien.
_db_backend_supporte_actualites = bool(_db_available) and (
    (os.getenv("UAM_DB_TYPE") or "").lower() == "mongodb"
)
```

Ajouter `import os` en tête du module s'il n'y est pas.

Dans `tools/__init__.py`, importer le drapeau et scinder l'extension conditionnelle :

```python
from ._db import _db_available, _db_backend_supporte_actualites
```

```python
    if _db_available:
        outils.extend([
            get_schedules_from_db, search_student_record, search_statistics_uam,
        ])
        if _db_backend_supporte_actualites:
            outils.append(search_latest_news)
```

- [ ] **Step 4: Vérifier**

```bash
venv/bin/python -m pytest tests/test_inventaire_outils.py -v
venv/bin/python -m pytest tests/ -q
venv/bin/python -c "
import tools
print('outils exposés en configuration réelle :', len(tools.get_tools()))
print('search_latest_news exposé :', any(t.name=='search_latest_news' for t in tools.get_tools()))
"
```

Attendu : suite au vert ; en configuration réelle (SQLite), 48 outils et `search_latest_news exposé : False`.

- [ ] **Step 5: Mettre à jour la documentation et committer**

Dans `CLAUDE.md`, remplacer la mention « 49 outils (45 toujours actifs + 4 conditionnels) » par : « 49 outils au total : 45 toujours actifs, 3 conditionnés à la base de données, et `search_latest_news` réservé aux backends documentaires ».

Marquer `BUG-01` comme `corrigé` dans le rapport d'audit.

```bash
git add -A
git commit -m "fix(tools): ne plus exposer search_latest_news sur un backend SQLite"
```

---

## Phase 6 — Faisabilité WhatsApp

### Task 15: Analyse de faisabilité

**Files:**
- Create: `WHATSAPP_FAISABILITE.md`

**Interfaces:**
- Consumes: `api/whatsapp.py`, `WHATSAPP.md`, la tâche 13 pour la section sur la persistance
- Produces: rien

**Aucune modification de code.** `api/whatsapp.py` n'est pas touché.

- [ ] **Step 1: Inventorier ce qui existe déjà**

```bash
grep -n "^def \|^async def " api/whatsapp.py
grep -n "whatsapp" api/main.py
grep -oE "^WHATSAPP_[A-Z_]+" .env.example
grep -c "" WHATSAPP.md
```

- [ ] **Step 2: Rédiger le document**

Créer `WHATSAPP_FAISABILITE.md` avec exactement ces six sections :

1. **Ce qui est déjà en place** — les fonctions de `api/whatsapp.py` (vérification de signature, extraction du message, formatage, envoi), les routes de `api/main.py`, et les quatre variables d'environnement attendues. Citer les lignes.
2. **Ce qui manque côté Meta** — compte WhatsApp Business, numéro vérifié, application Meta configurée, et surtout le token permanent : celui de l'application expire en 24 heures, ce qui interdit une démonstration planifiée sans renouvellement.
3. **Ce qui manque côté infrastructure** — le webhook exige une URL publique en HTTPS. Décrire l'option tunnel (ngrok ou équivalent) pour une démonstration, et ses points de défaillance le jour J.
4. **Apport de la persistance des sessions** — depuis la tâche 13, le `thread_id` `whatsapp:<numéro>` survit au redémarrage du serveur. C'est ce qui rend le canal réellement praticable : une conversation WhatsApp s'étale sur des heures ou des jours, là où une session web dure quelques minutes.
5. **Coût et conformité** — modèle de facturation par conversation de l'API Cloud, et les questions de protection des données que soulève le traitement de numéros de téléphone et de matricules d'étudiants.
6. **Verdict et effort restant** — faisable ou non, avec une estimation en jours-homme et la liste ordonnée de ce qu'il faudrait faire.

- [ ] **Step 3: Vérifier qu'aucun code n'a bougé**

```bash
git status --short
```

Attendu : un seul fichier, `WHATSAPP_FAISABILITE.md`.

- [ ] **Step 4: Commit**

```bash
git add WHATSAPP_FAISABILITE.md
git commit -m "docs: analyse de faisabilité du canal WhatsApp"
```

---

### Task 16: Branchement des métriques système

Tâche ajoutée le 2026-08-16, après la tâche 2. L'audit a établi que `record_system_metrics` et `get_latest_system_metrics` (`metrics.py:123,144`) sont mortes : la table `metrics_system` contient 0 ligne quand `metrics_questions` en contient 72. L'utilisateur a choisi de les **brancher** plutôt que de les supprimer — les mesures CPU et mémoire alimenteront le chapitre évaluation de son mémoire.

**Ordonnancement :** à exécuter après la tâche 13 (persistance), dont elle est indépendante. Elle ne touche ni `tools/` ni `graph_nodes.py`, donc elle n'entre en conflit avec aucune autre tâche.

**Files:**
- Modify: `metrics.py`, `api/agent_service.py`, `api/main.py`
- Test: `tests/test_metrics_systeme.py`

**Interfaces:**
- Consumes: `metrics.record_question(user_id, question, is_relevant, response_time_ms)` — le point d'appel existant dans `api/agent_service.py::_record`
- Produces: `metrics.record_system_metrics()` appelée à chaque question traitée ; `metrics.get_latest_system_metrics() -> Optional[Dict[str, float]]` retournant désormais aussi la clé `process_memory_mb`

**Pourquoi une colonne de plus.** `psutil.virtual_memory()` mesure la RAM de la machine entière, ce qui ne dit rien de l'agent. Pour un mémoire, la grandeur qui compte est la mémoire résidente du processus — le modèle d'embeddings HuggingFace pèse à lui seul environ 1 Go. La table étant vide, l'ajout de colonne est sans risque de migration.

- [ ] **Step 1: Écrire le test, qui doit échouer**

```python
# tests/test_metrics_systeme.py
"""Les métriques système doivent être réellement collectées."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def base_metrics(tmp_path, monkeypatch):
    """Isole metrics.py sur une base jetable."""
    import app_config
    import metrics

    monkeypatch.setenv("UAM_METRICS_DB", str(tmp_path / "metrics_test.db"))
    app_config.reset_for_tests() if hasattr(app_config, "reset_for_tests") else None
    monkeypatch.setattr(metrics, "_conn", None)
    monkeypatch.setattr(app_config, "_config", None)
    return metrics


class TestCollecteSysteme:

    def test_la_table_porte_la_memoire_du_processus(self, base_metrics):
        conn = base_metrics._get_connection()
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(metrics_system)")}
        assert "process_memory_mb" in colonnes

    def test_un_enregistrement_cree_une_ligne(self, base_metrics):
        base_metrics.record_system_metrics()
        conn = base_metrics._get_connection()
        assert conn.execute("SELECT COUNT(*) FROM metrics_system").fetchone()[0] == 1

    def test_la_memoire_du_processus_est_plausible(self, base_metrics):
        """Le processus pytest occupe forcément plus de 1 Mo et moins de 100 Go."""
        base_metrics.record_system_metrics()
        derniere = base_metrics.get_latest_system_metrics()
        assert derniere is not None
        assert 1.0 < derniere["process_memory_mb"] < 100_000.0

    def test_les_quatre_grandeurs_sont_retournees(self, base_metrics):
        base_metrics.record_system_metrics()
        derniere = base_metrics.get_latest_system_metrics()
        assert set(derniere) == {
            "cpu_percent", "memory_percent", "memory_used_mb", "process_memory_mb",
        }

    def test_aucune_ligne_donne_none(self, base_metrics):
        assert base_metrics.get_latest_system_metrics() is None
```

- [ ] **Step 2: Vérifier que le test échoue**

```bash
venv/bin/python -m pytest tests/test_metrics_systeme.py -v
```

Attendu : échecs sur `process_memory_mb` absent de la table et du dictionnaire retourné.

- [ ] **Step 3: Ajouter la colonne et mesurer le processus**

Dans `metrics.py`, à la fin de `_ensure_tables`, après le `CREATE TABLE IF NOT EXISTS metrics_system` :

```python
    # Colonne ajoutée après coup : les bases existantes ne l'ont pas.
    colonnes = {row[1] for row in cursor.execute("PRAGMA table_info(metrics_system)")}
    if "process_memory_mb" not in colonnes:
        cursor.execute("ALTER TABLE metrics_system ADD COLUMN process_memory_mb REAL")
```

Puis remplacer le corps de `record_system_metrics` :

```python
def record_system_metrics() -> None:
    """Enregistre l'utilisation CPU et mémoire, machine et processus.

    `memory_used_mb` mesure la machine entière ; `process_memory_mb` mesure la
    mémoire résidente de ce processus — la seule grandeur qui dise ce que coûte
    l'agent lui-même, modèle d'embeddings compris.
    """
    try:
        import psutil
    except ImportError:
        return

    processus = psutil.Process()
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    rss_mb = processus.memory_info().rss / (1024 * 1024)

    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO metrics_system
        (cpu_percent, memory_percent, memory_used_mb, process_memory_mb, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (cpu, mem.percent, mem.used / (1024 * 1024), rss_mb, datetime.now().isoformat())
    )
    conn.commit()
```

Et dans `get_latest_system_metrics`, ajouter la colonne au `SELECT` et à la valeur retournée :

```python
        cursor.execute(
            "SELECT cpu_percent, memory_percent, memory_used_mb, process_memory_mb "
            "FROM metrics_system ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return {
                "cpu_percent": round(row["cpu_percent"], 1),
                "memory_percent": round(row["memory_percent"], 1),
                "memory_used_mb": round(row["memory_used_mb"], 1),
                "process_memory_mb": round(row["process_memory_mb"] or 0.0, 1),
            }
```

- [ ] **Step 4: Vérifier que le test passe**

```bash
venv/bin/python -m pytest tests/test_metrics_systeme.py -v
```

Attendu : 5 tests au vert. Note : le premier appel à `psutil.cpu_percent(interval=None)` retourne toujours `0.0` faute de mesure de référence — c'est normal et sans conséquence, les appels suivants sont significatifs. Ne pas ajouter d'`interval` non nul : cela bloquerait le thread pendant la mesure.

- [ ] **Step 5: Appeler la collecte à chaque question**

Dans `api/agent_service.py`, fonction `_record`, ajouter l'appel à côté de `record_question`, dans le même bloc protégé :

```python
        record_question(session_id, question, is_relevant, elapsed_ms)
        record_system_metrics()
```

Compléter l'import existant depuis `metrics` pour y inclure `record_system_metrics`.

- [ ] **Step 6: Exposer les mesures sur /health**

Dans `api/main.py`, la route `health` : ajouter les dernières métriques système à la réponse, sans faire échouer la route si elles sont absentes.

```python
    from metrics import get_latest_system_metrics
    systeme = get_latest_system_metrics()
    # ... ajouter au dictionnaire de réponse : "systeme": systeme
```

Ce branchement fait cesser la mort de `get_latest_system_metrics`, qui était l'autre moitié du problème.

- [ ] **Step 7: Vérifier de bout en bout**

```bash
venv/bin/python -m pytest tests/ -q
./run_api.sh 8010 &
sleep 45
curl -s -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"question":"Quels sont les frais en licence ?","session_id":"metrics-1"}' > /dev/null
curl -s localhost:8010/health
echo
kill %1
venv/bin/python -c "
import sqlite3
c = sqlite3.connect('metrics.db')
print('lignes metrics_system :', c.execute('SELECT COUNT(*) FROM metrics_system').fetchone()[0])
for r in c.execute('SELECT cpu_percent, memory_used_mb, process_memory_mb FROM metrics_system ORDER BY id DESC LIMIT 3'):
    print('  ', r)
"
```

Attendu : `/health` retourne les mesures, `metrics_system` n'est plus vide, et `process_memory_mb` est de l'ordre du gigaoctet une fois le modèle d'embeddings chargé.

- [ ] **Step 8: Commit**

```bash
git add metrics.py api/agent_service.py api/main.py tests/test_metrics_systeme.py
git commit -m "feat(metrics): collecte effective des métriques système, mémoire du processus comprise"
```

---

### Task 17: Correction de BUG-03 — questions sur les frais rejetées

Tâche ajoutée le 2026-08-17, remontée depuis la phase 4 sur décision de l'utilisateur. `check_question_relevance` ne reconnaît que la phrase exacte « frais d'inscription » (`tools.py:435`, `education_phrases`) ; le mot « frais » est absent de `keywords_uam` (`tools.py:373-385`). Conséquence mesurée sur le routage réel :

```text
reject_query   <- Quels sont les frais ?
reject_query   <- Quel est le montant des frais ?
reject_query   <- Je veux connaitre les frais
agent          <- Quels sont les frais d'inscription ?
agent          <- Combien coûte une inscription ?
```

L'agent refuse de répondre à la question la plus courante d'un candidat, sur le canal web qui servira à la soutenance. C'est le défaut le plus visible identifié par l'audit.

**Ordonnancement :** indépendante des autres tâches. Elle touche `tools.py`, qui sera déplacé en tâche 11 — l'exécuter avant évite un conflit et fait bénéficier le correctif du garde-fou d'inventaire.

**Files:**
- Modify: `tools.py` (fonction `check_question_relevance`)
- Modify: `docs/superpowers/audit/2026-08-16-audit.md` (marquer BUG-03 corrigé)
- Test: `tests/test_bug_03_frais.py`

**Interfaces:**
- Consumes: `tools.check_question_relevance(question) -> str` retournant `"PERTINENT"` ou `"HORS_SUJET"`
- Produces: aucune interface nouvelle — seul le comportement de classification change

**Le piège à éviter.** `keywords_uam` teste l'appartenance par sous-chaîne (`if kw in question_lower`, `tools.py:387-389`). Ajouter `"frais"` à cette liste ferait classer `PERTINENT` des phrases comme « il fait frais ce matin » ou « j'aime les produits frais » — en français, « frais » est aussi un adjectif. La correction doit donc porter sur des expressions, pas sur le mot nu.

### Périmètre élargi le 2026-08-17 — BUG-04 découvert en cours de tâche

Le premier implémenteur s'est arrêté au contrôle rouge, comme le brief l'exigeait : `test_adjectif_frais_reste_hors_sujet["Il fait frais ce matin"]` échouait **avant toute correction**. Diagnostic : la même recherche par sous-chaîne fait matcher l'abréviation `"fa"` (Faculté d'Agronomie) à l'intérieur du mot « fait ».

Mesure de l'ampleur :

```text
PERTINENT    <- Il fait frais ce matin
PERTINENT    <- Il fait beau aujourd hui
PERTINENT    <- Je suis fatigue
PERTINENT    <- Je pense que c est une bonne idee
PERTINENT    <- Comment fabriquer du savon ?
PERTINENT    <- Le facteur est passe
PERTINENT    <- Ma famille habite a Zinder
PERTINENT    <- Comment faire une omelette ?
PERTINENT    <- Je voudrais un renseignement
HORS_SUJET   <- Quelle est la recette du couscous ?
HORS_SUJET   <- Qui a gagne le match hier ?
HORS_SUJET   <- Quel est le prix du carburant ?
```

Huit phrases hors sujet sur douze passent le filtre : `"fa"` matche dans *fait, faire, famille, fatigué, fabriquer, facteur*, et `"ens"` (École Normale Supérieure) dans *pense, renseignement*. Le nœud `reject_query` est donc largement contourné, alors que le rejet poli du hors-sujet est une fonctionnalité annoncée de l'agent.

Ce défaut est inscrit comme **BUG-04**, gravité haute. Il doit être corrigé dans cette même tâche : le test de non-faux-positif de BUG-03 ne peut pas passer tant qu'il subsiste, et les deux défauts vivent dans la même fonction.

**La correction ne consiste pas à appliquer `\b` à toute la liste.** Les mots-clés longs doivent continuer de matcher leurs formes fléchies : `"inscription"` doit reconnaître « inscriptions », ce qu'une limite de mot en fin empêcherait. Il faut séparer les deux familles :

```python
    # Abréviations : recherche en mot entier. Testées par sous-chaîne, « fa »
    # matcherait « fait », « ens » matcherait « pense » — voir BUG-04.
    abreviations_uam = [
        "uam", "fast", "flsh", "fseg", "fsjp", "fa", "fss", "ens",
        "ed-svt", "ed-lashs", "ed-set", "irsh", "irem", "iri",
    ]
    for abbr in abreviations_uam:
        if re.search(rf"\b{re.escape(abbr)}\b", question_lower):
            return "PERTINENT"

    # Mots-clés porteurs de sens : sous-chaîne, pour couvrir les formes fléchies.
    keywords_uam = [
        "abdou moumouni",
        "faculté", "école", "institut", "formation", "filière",
        "inscription", "admission", "diplôme", "attestation", "relevé",
        "scolarité", "étudiant", "licence", "master", "doctorat", "thèse",
        "cours", "horaire", "service", "recteur", "doyen",
        "réinscription", "réinscrire", "préinscription", "dossier", "pièces",
        "calendrier", "date limite",
        "carte étudiant", "bourse", "logement", "cité universitaire",
        "orientation", "restauration", "bibliothèque",
    ]
```

Vérifier que `re` est importé dans `tools.py` — il l'est déjà, `external_patterns` s'en sert.

**Tests supplémentaires à ajouter** dans `tests/test_bug_03_frais.py`, classe dédiée :

```python
class TestBug04AbreviationsEnMotEntier:
    """« fa » et « ens » ne doivent plus matcher à l'intérieur d'un mot."""

    @pytest.mark.parametrize("question", [
        "Il fait beau aujourd'hui",
        "Je suis fatigué",
        "Comment fabriquer du savon ?",
        "Le facteur est passé",
        "Ma famille habite à Zinder",
        "Comment faire une omelette ?",
        "Je pense que c'est une bonne idée",
        "Je voudrais un renseignement",
    ])
    def test_mots_contenant_fa_ou_ens_restent_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        "Que propose la FA ?",
        "Quelles filières à la FAST ?",
        "Comment intégrer l'ENS ?",
        "Je veux m'inscrire à l'UAM",
        "Quelles formations à l'IRI ?",
    ])
    def test_les_abreviations_restent_reconnues(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"
```

Le second groupe est le garde-fou de la correction : resserrer la reconnaissance ne doit pas faire perdre les vrais usages des abréviations. Il doit passer avant comme après.

- [ ] **Step 1: Écrire les tests, qui doivent échouer**

```python
# tests/test_bug_03_frais.py
"""BUG-03 : les questions sur les frais sont rejetées comme hors sujet.

Seule la phrase exacte « frais d'inscription » était reconnue. Les formulations
naturelles — « quels sont les frais ? », « le montant des frais » — partaient en
reject_query, et l'agent répondait qu'il ne traite que les questions UAM.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestQuestionsSurLesFrais:
    """Les formulations naturelles doivent être reconnues comme pertinentes."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais ?",
        "Quel est le montant des frais ?",
        "Je veux connaitre les frais",
        "Les frais sont de combien ?",
        "Combien coûtent les frais ?",
        "Quels sont les frais de scolarité ?",
        "Je voudrais connaître les frais universitaires",
    ])
    def test_formulations_naturelles_sont_pertinentes(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"

    @pytest.mark.parametrize("question", [
        "Quels sont les frais d'inscription ?",
        "Combien coûte une inscription ?",
    ])
    def test_les_formulations_deja_reconnues_le_restent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestPasDeFauxPositifs:
    """« frais » est aussi un adjectif : ces phrases ne parlent pas de l'UAM."""

    @pytest.mark.parametrize("question", [
        "Il fait frais ce matin",
        "J'aime les produits frais du marché",
        "Où trouver du poisson frais à Niamey ?",
    ])
    def test_adjectif_frais_reste_hors_sujet(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"


class TestRoutageDeBoutEnBout:
    """Le routage est ce que l'utilisateur subit réellement."""

    @pytest.mark.parametrize("question", [
        "Quels sont les frais ?",
        "Quel est le montant des frais ?",
        "Je veux connaitre les frais",
    ])
    def test_les_questions_sur_les_frais_atteignent_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"

    def test_une_question_hors_sujet_reste_rejetee(self):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content="Il fait frais ce matin")]})
        assert resultat["routing_hint"] == "reject_query"
```

- [ ] **Step 2: Vérifier que les tests échouent pour la bonne raison**

```bash
venv/bin/python -m pytest tests/test_bug_03_frais.py -v
```

Attendu : les sept cas de `test_formulations_naturelles_sont_pertinentes` et les trois de `test_les_questions_sur_les_frais_atteignent_l_agent` échouent. Les classes `TestPasDeFauxPositifs` et `test_les_formulations_deja_reconnues_le_restent` doivent **passer dès maintenant** — elles décrivent le comportement à préserver. Si l'une d'elles échoue déjà, arrêter et le signaler : le diagnostic serait à revoir.

- [ ] **Step 3: Corriger**

Dans `tools.py`, fonction `check_question_relevance`, compléter `education_phrases` (`tools.py:433-437`) avec les expressions qui ne créent pas de faux positif :

```python
    education_phrases = [
        "comment s'inscrire", "quelles formations", "quel diplôme",
        "pièces à fournir", "conditions d'admission", "frais d'inscription",
        "comment candidater", "dépôt de dossier",
        # BUG-03 : « frais » seul est ambigu en français (adjectif), on cible
        # donc les tournures où il est un nom désignant un coût.
        "les frais", "des frais", "frais de scolarité", "frais universitaires",
        "frais de formation", "frais de dossier",
    ]
```

Ne pas ajouter `"frais"` à `keywords_uam` : cette liste teste l'appartenance par sous-chaîne et classerait « il fait frais » comme pertinent.

- [ ] **Step 4: Vérifier que tout passe**

```bash
venv/bin/python -m pytest tests/test_bug_03_frais.py -v
venv/bin/python -m pytest tests/ -q
```

Attendu : les 16 tests du fichier au vert, et la suite complète au vert sans avertissement. Si un test de caractérisation de la tâche 6 casse, c'est qu'il figeait ce bug — vérifier lequel et le signaler plutôt que de l'ajuster en silence.

- [ ] **Step 5: Vérifier qu'aucune régression de classement n'apparaît**

```bash
venv/bin/python -c "
from tools import check_question_relevance
cas_pertinents = [
    'Quels sont les frais ?', 'Quel est le montant des frais ?',
    'Je veux connaitre les frais', 'Quels sont les frais de scolarité ?',
    \"Quels sont les frais d'inscription ?\", 'Comment se réinscrire ?',
    'Que propose la FAST ?',
]
cas_hors_sujet = [
    'Il fait frais ce matin', \"J'aime les produits frais\",
    'Quelle est la recette du couscous ?', 'Qui a gagné le match hier ?',
]
for q in cas_pertinents:
    r = check_question_relevance.func(question=q)
    print(('OK ' if r == 'PERTINENT' else 'KO '), r, '<-', q)
for q in cas_hors_sujet:
    r = check_question_relevance.func(question=q)
    print(('OK ' if r == 'HORS_SUJET' else 'KO '), r, '<-', q)
"
```

Attendu : `OK` sur les onze lignes. Tout `KO` doit être expliqué dans le rapport.

- [ ] **Step 6: Marquer le bug corrigé**

Dans `docs/superpowers/audit/2026-08-16-audit.md`, passer l'état de BUG-03 à `corrigé` en citant le hash du commit, sans supprimer sa description ni sa reproduction — le rapport garde la mémoire du défaut.

- [ ] **Step 7: Commit**

```bash
git add tools.py tests/test_bug_03_frais.py docs/superpowers/audit/2026-08-16-audit.md
git commit -m "fix(tools): reconnaître les questions sur les frais sans la mention inscription"
```

---

### Task 18: Correction de BUG-05 — questions sans accents rejetées

Tâche ajoutée le 2026-08-17, après la tâche 17. Les mots-clés de `keywords_uam` sont accentués et la comparaison est littérale : une question tapée sans accents ne les reconnaît pas.

| Avec accents | Sans accents |
|---|---|
| « Comment se réinscrire ? » → `PERTINENT` | « Comment se reinscrire ? » → `HORS_SUJET` |
| « Quelles sont les filières ? » → `PERTINENT` | « Quelles sont les filieres ? » → `HORS_SUJET` |
| « Où est la faculté ? » → `PERTINENT` | « Ou est la faculte ? » → `HORS_SUJET` |
| « Quel diplôme obtient-on ? » → `PERTINENT` | « Quel diplome obtient-on ? » → `HORS_SUJET` |
| « Comment obtenir mon relevé ? » → `PERTINENT` | « Comment obtenir mon releve ? » → `HORS_SUJET` |

Le défaut est antérieur à la tâche 17, mais il était masqué : « faculte » contient `"fa"`, donc le faux positif de BUG-04 servait de rattrapage involontaire. Le corriger l'a mis au jour.

L'enjeu est réel : la saisie sans accents est courante sur téléphone et sur clavier QWERTY, répandu au Niger. Un visiteur qui écrit « Ou est la faculte ? » est aujourd'hui éconduit.

**Ordonnancement :** après la tâche 17, dont elle dépend (même fonction). Avant la tâche 11, pour que `tools.py` soit stabilisé avant son découpage.

**Files:**
- Modify: `tools.py` (fonction `check_question_relevance` et un helper de module)
- Modify: `docs/superpowers/audit/2026-08-16-audit.md`
- Test: `tests/test_bug_05_accents.py`

**Interfaces:**
- Consumes: `tools.check_question_relevance(question) -> str`
- Produces: `tools._sans_accents(texte: str) -> str`, helper privé de module réutilisable par d'autres détecteurs

- [ ] **Step 1: Écrire les tests, qui doivent échouer**

```python
# tests/test_bug_05_accents.py
"""BUG-05 : les questions tapées sans accents sont rejetées.

Les mots-clés de keywords_uam sont accentués et la comparaison est littérale.
La saisie sans accents est courante sur téléphone et clavier QWERTY.
"""
import os
import sys

import pytest
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PAIRES = [
    ("Comment se réinscrire ?", "Comment se reinscrire ?"),
    ("Quelles sont les filières ?", "Quelles sont les filieres ?"),
    ("Où est la faculté ?", "Ou est la faculte ?"),
    ("Quel diplôme obtient-on ?", "Quel diplome obtient-on ?"),
    ("Comment obtenir mon relevé de notes ?", "Comment obtenir mon releve de notes ?"),
    ("Quelle est la procédure de préinscription ?", "Quelle est la procedure de preinscription ?"),
    ("Y a-t-il une cité universitaire ?", "Y a-t-il une cite universitaire ?"),
]


class TestInsensibiliteAuxAccents:

    @pytest.mark.parametrize("avec,sans", PAIRES)
    def test_les_deux_formes_sont_classees_pareil(self, avec, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == \
               check_question_relevance.func(question=avec)

    @pytest.mark.parametrize("_,sans", PAIRES)
    def test_la_forme_sans_accents_est_pertinente(self, _, sans):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=sans) == "PERTINENT"


class TestPasDeRegression:
    """La normalisation ne doit pas rouvrir les faux positifs de BUG-03 et BUG-04."""

    @pytest.mark.parametrize("question", [
        "Il fait frais ce matin",
        "Comment faire une omelette ?",
        "Ma famille habite à Zinder",
        "Je pense que c'est une bonne idée",
        "Le facteur est passé",
        "Quelle est la recette du couscous ?",
    ])
    def test_les_phrases_hors_sujet_le_restent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "HORS_SUJET"

    @pytest.mark.parametrize("question", [
        "Que propose la FA ?",
        "Comment intégrer l'ENS ?",
        "Quels sont les frais ?",
        "Quelles filières à la FAST ?",
    ])
    def test_les_acquis_des_taches_precedentes_tiennent(self, question):
        from tools import check_question_relevance
        assert check_question_relevance.func(question=question) == "PERTINENT"


class TestHelperSansAccents:

    @pytest.mark.parametrize("entree,attendu", [
        ("réinscrire", "reinscrire"),
        ("filière", "filiere"),
        ("diplôme", "diplome"),
        ("où", "ou"),
        ("cité universitaire", "cite universitaire"),
        ("sans accent", "sans accent"),
        ("", ""),
    ])
    def test_normalisation(self, entree, attendu):
        from tools import _sans_accents
        assert _sans_accents(entree) == attendu

    def test_la_casse_n_est_pas_modifiee(self):
        """Le helper normalise les accents, pas la casse : les deux
        responsabilités restent séparées."""
        from tools import _sans_accents
        assert _sans_accents("FACULTÉ") == "FACULTE"


class TestRoutage:

    @pytest.mark.parametrize("question", [
        "Ou est la faculte ?",
        "Comment se reinscrire ?",
        "Quelles sont les filieres ?",
    ])
    def test_les_questions_sans_accents_atteignent_l_agent(self, question):
        from graph_nodes import route_and_store
        resultat = route_and_store({"messages": [HumanMessage(content=question)]})
        assert resultat["routing_hint"] == "agent"
```

- [ ] **Step 2: Vérifier que les tests échouent pour la bonne raison**

```bash
venv/bin/python -m pytest tests/test_bug_05_accents.py -v
```

Attendu : `TestHelperSansAccents` échoue à l'import (`_sans_accents` n'existe pas), `TestInsensibiliteAuxAccents` et `TestRoutage` échouent sur la classification. `TestPasDeRegression` doit **passer dès maintenant** : ce sont les acquis des tâches 17 et précédentes. S'il échoue déjà, s'arrêter et le signaler.

- [ ] **Step 3: Ajouter le helper de normalisation**

Dans `tools.py`, au niveau du module, près des autres helpers privés :

```python
def _sans_accents(texte: str) -> str:
    """Retire les signes diacritiques, sans toucher à la casse.

    La saisie sans accents est courante sur téléphone et sur clavier QWERTY :
    « Ou est la faculte ? » doit être comprise comme « Où est la faculté ? ».
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")
```

Ajouter `import unicodedata` en tête de `tools.py` s'il n'y figure pas.

- [ ] **Step 4: Appliquer la normalisation dans `check_question_relevance`**

Normaliser **les deux côtés** de la comparaison : la question et les mots-clés. Normaliser seulement la question ne suffirait pas, puisque les mots-clés sont eux-mêmes accentués.

Dans `check_question_relevance`, après le passage en minuscules, ajouter la variante normalisée, puis l'utiliser pour la boucle sur `keywords_uam` :

```python
    question_sans_accents = _sans_accents(question_lower)

    # ... la boucle sur abreviations_uam reste sur question_lower : les
    # abréviations ne portent pas d'accent.

    for kw in keywords_uam:
        if _sans_accents(kw) in question_sans_accents:
            return "PERTINENT"
```

Appliquer le même traitement à `education_phrases`, qui contient « frais de scolarité ».

Ne pas normaliser `external_patterns` : ces expressions régulières gèrent déjà leurs variantes accentuées explicitement (`capacit[eé]`), et les modifier sans nécessité risquerait de casser leur logique.

- [ ] **Step 5: Vérifier**

```bash
venv/bin/python -m pytest tests/test_bug_05_accents.py -v
venv/bin/python -m pytest tests/ -q
```

Attendu : le fichier au vert, la suite complète au vert, sans avertissement.

- [ ] **Step 6: Contrôle de non-régression étendu**

```bash
venv/bin/python -c "
from tools import check_question_relevance as c
pertinents = [
    'Quels sont les frais ?', 'Ou est la faculte ?', 'Comment se reinscrire ?',
    'Quelles sont les filieres ?', 'Quel diplome obtient-on ?',
    'Que propose la FA ?', \"Comment integrer l'ENS ?\",
    'Quelles filieres a la FAST ?', 'Je veux des informations sur les inscriptions',
    'Quelles formations proposez-vous ?',
]
hors_sujet = [
    'Il fait frais ce matin', 'Comment faire une omelette ?',
    'Ma famille habite a Zinder', 'Je pense que c est une bonne idee',
    'Le facteur est passe', 'Quelle est la recette du couscous ?',
    'Qui a gagne le match hier ?', 'Quel est le prix du carburant ?',
]
ko = 0
for q in pertinents:
    r = c.func(question=q)
    if r != 'PERTINENT': ko += 1; print('KO', r, '<-', q)
for q in hors_sujet:
    r = c.func(question=q)
    if r != 'HORS_SUJET': ko += 1; print('KO', r, '<-', q)
print('echecs :', ko, '/', len(pertinents) + len(hors_sujet))
"
```

Attendu : `echecs : 0 / 18`. Tout écart doit être expliqué dans le rapport.

- [ ] **Step 7: Marquer le bug corrigé**

Inscrire BUG-05 en section 5 du rapport d'audit, gravité **haute**, avec le tableau de comparaison ci-dessus comme reproduction, puis le marquer corrigé dans un commit distinct citant le hash du correctif.

- [ ] **Step 8: Commit**

```bash
git add tools.py tests/test_bug_05_accents.py
git commit -m "fix(tools): reconnaître les questions tapées sans accents"
git add docs/superpowers/audit/2026-08-16-audit.md
git commit -m "docs(audit): inscrit BUG-05 et le marque corrigé"
```

---

## Vérification finale

À exécuter après la tâche 15, avant de clore le chantier.

- [ ] **Garde-fou 1 — la suite de tests**

```bash
venv/bin/python -m pytest tests/ -q --durations=10
```

Attendu : tout au vert, entre 80 et 120 tests, sous 10 secondes.

- [ ] **Garde-fou 2 — l'inventaire des outils**

```bash
venv/bin/python -c "
import tools
outils = tools.get_tools()
print(len(outils), 'outils exposés')
print('sans doublon :', len({t.name for t in outils}) == len(outils))
"
```

Attendu : 48 outils en configuration SQLite, sans doublon.

- [ ] **Garde-fou 3 — les points d'entrée**

```bash
venv/bin/python -c "
import importlib
for m in ('api.main','app_streamlit','agent_uam','chatbot','evaluate','run_grounding_capture'):
    importlib.import_module(m); print('ok', m)
"
```

- [ ] **Garde-fou 4 — le site répond**

```bash
./run_api.sh 8010 &
sleep 45
for q in "Quels sont les frais d inscription en licence ?" "Que propose la FAST ?" "Comment se reinscrire en retard ?"; do
  echo "--- $q"
  curl -s -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
    -d "{\"question\":\"$q\",\"session_id\":\"final-$RANDOM\"}" | head -c 500
  echo
done
kill %1
```

Attendu : trois réponses non vides, sans trace d'erreur, chacune traitant du sujet demandé.

# Analyse de faisabilité — canal WhatsApp

Date : 2026-08-26. Portée : évaluer si le canal WhatsApp amorcé dans `api/whatsapp.py`
peut être mis en service, et à quel coût — sans modifier aucun fichier `.py`. Toutes les
affirmations sur le code ci-dessous ont été vérifiées par lecture directe des fichiers
cités, à la ligne indiquée, le jour de rédaction de ce document. Les affirmations sur la
plateforme Meta (comportement du token, de la vérification d'entreprise, de la
facturation…) sont signalées explicitement comme telles : soit elles reprennent un fait
déjà documenté dans ce dépôt (`WHATSAPP.md`), soit elles renvoient explicitement à une
vérification à faire auprès de Meta au moment de la décision.

---

## 1. Ce qui est déjà en place

### `api/whatsapp.py` — six fonctions, aucune inachevée

| Fonction | Lignes | Rôle |
|---|---|---|
| `is_configured()` | 28-30 | Vrai si `WHATSAPP_ACCESS_TOKEN` et `WHATSAPP_PHONE_NUMBER_ID` sont présents. |
| `verify_signature()` | 33-46 | Valide l'en-tête `X-Hub-Signature-256` (HMAC-SHA256 avec `WHATSAPP_APP_SECRET`). |
| `extract_incoming_message()` | 49-73 | Extrait `(message_id, numéro, texte)` d'un webhook Meta ; retourne `None` pour tout ce qui n'est pas un message texte entrant (notifications de statut). |
| `to_whatsapp_format()` | 76-87 | Convertit le markdown du LLM (`**gras**`, titres, liens, puces) au format WhatsApp. |
| `split_message()` | 90-110 | Découpe un texte au-delà de `MAX_MESSAGE_LENGTH` (4000 caractères, ligne 25) sur les sauts de paragraphe. |
| `send_message()` | 113-148 | Envoie via l'API Graph de Meta (`GRAPH_API_VERSION = "v21.0"`, ligne 23), `httpx` importé localement (ligne 126). |

### `api/main.py` — routes branchées

- Import des fonctions ci-dessus : lignes 36-41.
- `GET /webhook/whatsapp` (`whatsapp_verify`, lignes 146-161) : répond au challenge de
  vérification Meta ; renvoie `403 "Webhook non configuré"` si `WHATSAPP_VERIFY_TOKEN`
  est absent (ligne 152-154).
- `POST /webhook/whatsapp` (`whatsapp_webhook`, lignes 180-214) : vérifie la signature
  (ligne 189), déduplique sur `message_id` via `_seen_messages` (lignes 51-54, 205-210 —
  jusqu'à 500 identifiants gardés, contre les webhooks rejoués par Meta), puis traite en
  tâche de fond (`background.add_task`, ligne 213) via `_handle_whatsapp_message`
  (lignes 164-177), qui appelle `answer(..., session_id=f"whatsapp:{from_number}")`
  (ligne 169) et renvoie la réponse par `send_message`.
- `GET /health` expose `"whatsapp": whatsapp_is_configured()` (ligne 87).

### Quatre variables d'environnement attendues

`.env.example` lignes 56-59 : `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET` — toutes vides dans `.env.example`
(valeurs à renseigner). Constat sur ce dépôt local : le `.env` de la machine où ce
document est rédigé ne contient aucune de ces quatre variables (`grep -c "^WHATSAPP_"
.env` → `0`) — cohérent avec l'énoncé de la tâche : le canal n'a jamais été mis en
service, ni même configuré localement.

Le code du canal est donc complet et cohérent : rien à écrire pour faire fonctionner un
échange simple. Ce qui manque est entièrement de la configuration (côté Meta et côté
infrastructure) — sections 2 et 3.

---

## 2. Ce qui manque côté Meta

Constat de repo : les quatre variables ci-dessus sont vides — aucune démarche Meta n'a
laissé de trace dans ce dépôt (pas de token, pas d'identifiant de numéro). Ce qui suit
reprend les étapes déjà documentées dans `WHATSAPP.md` (fichier existant du dépôt,
sections 1 et 2, lignes 13-34) ; je ne les ai pas revérifiées moi-même contre la console
Meta au moment de la rédaction — à reconfirmer à la mise en œuvre, l'interface et les
règles de Meta évoluant sans préavis pour ce dépôt.

Restent à faire, côté Meta, avant toute démonstration :
1. Créer une application Meta de type Entreprise et y ajouter le produit WhatsApp.
2. Obtenir un numéro de test (gratuit, pas de vérification d'entreprise nécessaire pour
   une démo) et y ajouter les numéros destinataires autorisés (`WHATSAPP.md` limite à 5).
3. Relever `Phone number ID`, le token d'accès temporaire, et l'App secret.

**Prérequis bloquant, distinct de la simple configuration (SEC-02).** `verify_signature()`
(`api/whatsapp.py:33-46`) contient ce repli, vérifié directement dans le code :

```python
app_secret = os.getenv("WHATSAPP_APP_SECRET")
if not app_secret:
    return True
```

Sans `WHATSAPP_APP_SECRET` défini, la fonction accepte **toute requête POST** sur
`/webhook/whatsapp`, signature absente ou falsifiée, sans distinction (lignes 38-40 :
le retour `True` intervient avant même de lire l'en-tête de signature). C'est inerte
aujourd'hui : le canal n'est pas exposé publiquement. Mais c'est précisément la
configuration qui change ce fait — le jour où une URL publique répond sur cette route
(section 3), n'importe qui peut poster un payload JSON qui se fera passer pour un message
WhatsApp entrant, et le faire traiter par l'agent (réponse générée, éventuellement
renvoyée si `send_message` est aussi configuré). **`WHATSAPP_APP_SECRET` doit donc être
défini avant — pas après — que l'URL du webhook devienne joignable depuis l'extérieur,**
y compris pour une démonstration via tunnel (section 3). Ce n'est pas un changement de
code : c'est une variable d'environnement à ne jamais omettre dans la checklist de mise
en route, et `WHATSAPP.md` (étape 2, ligne 33) la liste déjà — le risque n'est pas
qu'elle soit inconnue, mais qu'elle soit oubliée un jour de configuration pressée.

**Le token permanent.** `WHATSAPP.md` (lignes 20, 24-25) documente que le token relevé à
l'étape « API Setup » de la console Meta est temporaire et expire au bout de 24 heures.
C'est un fait déjà consigné dans ce dépôt, que je n'ai pas revérifié contre la
documentation Meta actuelle — à reconfirmer à la mise en œuvre. Tel quel, il interdit
une démonstration planifiée à l'avance sans regénération le jour même : programmer une
soutenance une semaine après avoir récupéré le token expose à un canal mort au moment
voulu. Un token permanent (obtenu via un « System User » côté Meta Business, avec
vérification d'entreprise) lève cette contrainte, mais n'est pas nécessaire pour une
démonstration ponctuelle si le token est régénéré le matin même — c'est l'option que
`WHATSAPP.md` recommande déjà (ligne 24-25, 98).

---

## 3. Ce qui manque côté infrastructure

Le webhook Meta exige une URL **publique en HTTPS** pour recevoir les appels `GET`
(vérification) et `POST` (messages) — contrainte de la plateforme Meta, non vérifiée par
moi de première main, mais cohérente avec le fait que `whatsapp_verify` et
`whatsapp_webhook` (`api/main.py:146-214`) sont de simples routes FastAPI locales sans
aucune préparation TLS ni exposition réseau dans le code : rien dans ce dépôt ne sert
HTTPS ni n'ouvre de port public, `./run_api.sh` lance uvicorn en local (`http://localhost:8000`,
`run_api.sh:5`).

**Option tunnel, pour une démonstration.** `WHATSAPP.md` (lignes 36-45) décrit
`cloudflared tunnel --url http://localhost:8000` ou `ngrok http 8000` comme solution
sans hébergement dédié : le tunnel expose le serveur local sous une URL HTTPS publique
temporaire, à recoller dans la configuration du webhook Meta (étape 4, lignes 47-57).

**Points de défaillance le jour J**, déjà identifiés dans `WHATSAPP.md`
(section « Le jour de la soutenance », lignes 96-102), et cohérents avec la nature d'un
tunnel gratuit :
- L'URL du tunnel **change à chaque redémarrage** (`WHATSAPP.md` ligne 44) : un tunnel
  relancé entre la configuration et la démonstration invalide la déclaration faite chez
  Meta, sans erreur visible avant l'envoi d'un message réel.
- Le réseau de la salle de soutenance (Wi-Fi filtré, proxy d'établissement, bande
  passante partagée) est hors du contrôle du projet et peut bloquer le tunnel sortant ou
  ralentir les requêtes entrantes de Meta.
- Un service de tunnel gratuit peut imposer des limites de débit ou une latence
  variable, qui s'ajoutent à celle de l'appel LLM lui-même.
- `WHATSAPP.md` recommande en conséquence d'enregistrer à l'avance une **capture vidéo de
  secours de 30 secondes** de l'échange fonctionnel — recommandation que je reprends
  telle quelle, elle est déjà la bonne réponse à un risque qu'aucune configuration ne
  supprime complètement.

---

## 4. Apport de la persistance des sessions

Le `thread_id` utilisé pour chaque contact WhatsApp est `f"whatsapp:{from_number}"`
(`api/main.py:169`) — un identifiant stable par numéro de téléphone, indépendant du
processus serveur.

Depuis la tâche 13, le checkpointer par défaut est `SqliteSaver`
(`app_config.py:123`, `checkpointer: str = "sqlite"` ; construit dans
`agent_graph.py:_build_checkpointer()`, lignes 19-65, avec repli sur `MemorySaver` si le
fichier SQLite est inaccessible, lignes 44-65). Le rapport de la tâche 13 documente une
vérification de bout en bout : un premier processus serveur reçoit un message sur
`thread_id="persistance-1"`, est tué, un second processus (PID différent) est relancé, et
l'inspection directe de `database/checkpoints.db` via `SqliteSaver.get_tuple()` montre les
9 messages de la conversation intacts, y compris le tout premier — jamais présent en
mémoire du second processus, donc nécessairement relu depuis le fichier
(`.superpowers/sdd/2026-08-16-nettoyage-refactorisation/task-13-report.md`, section
« Essai de bout en bout »). C'est ce qui rend le canal réellement praticable : une
conversation WhatsApp s'étale sur des heures ou des jours (l'utilisateur revient poser une
question de suivi le lendemain), là où une session web dure quelques minutes et où
`MemorySaver` suffisait. `WHATSAPP.md` (lignes 106-109, section « Pour aller en
production ») affirme encore que le checkpointer est en mémoire et qu'un redémarrage
efface tout — cette phrase est **obsolète depuis la tâche 13** : je ne l'ai pas corrigée
(hors périmètre de cette tâche, `WHATSAPP.md` n'est pas dans les fichiers à modifier),
mais un lecteur qui s'y fierait tirerait une conclusion aujourd'hui fausse.

**Mais cet historique conservé ne sert à rien si l'utilisateur interroge la conversation
elle-même.** Une mesure faite pendant ce chantier (rapport d'audit
`docs/superpowers/audit/2026-08-16-audit.md`, entrée BUG-10) établit que 12 formulations
courantes de rappel de contexte (« Quel est mon prénom ? », « Tu te souviens de moi ? »…),
testées hors ligne directement contre `route_and_store`, sont **12 fois sur 12** routées
vers `reject_query` plutôt que vers l'agent. J'ai vérifié moi-même le mécanisme en cause :
`route_and_store` ne lit que le dernier message de l'état
(`last_message = state["messages"][-1]`, `graph_nodes.py:166`) et le transmet à
`check_question_relevance` (`tools/conversation.py:145`), une cascade de règles lexicales
sans accès à l'historique — une question sur la conversation elle-même ne contient par
nature aucun mot-clé UAM et part donc en `reject_query`
(`graph_nodes.py:230`), qui renvoie un texte statique codé en dur sans jamais appeler le
LLM (`graph_nodes.py:441-463`). Le rapport de la tâche 13 documente une reproduction en
conditions réelles au même effet : après redémarrage du serveur, « Quel est mon prénom ? »
reçoit une réponse générique hors sujet en 57 ms (bien trop rapide pour un appel LLM, qui a
pris 2278 ms et 7013 ms ailleurs dans le même essai) ; en forçant le routage vers l'agent
par l'ajout d'un mot-clé UAM, le LLM refuse quand même de restituer le prénom donné plus
tôt dans la même conversation, invoquant son garde-fou anti-hallucination
(`prompts.py:31-39`, « ANCRAGE FACTUEL (NON NÉGOCIABLE) » — interdit toute affirmation
sur un nom propre non issu d'un appel d'outil, y compris un nom propre donné par
l'utilisateur lui-même).

**Les deux faits doivent se lire ensemble** : l'historique est bien conservé et transmis
au modèle d'un redémarrage à l'autre (persistance réelle, prouvée par inspection directe
du fichier SQLite) — mais toute question qui porte sur cette conversation plutôt que sur
l'UAM échoue, pour deux raisons indépendantes et non corrigées à ce jour. Présenter l'une
sans l'autre donnerait une image fausse : la persistance ne rend pas aujourd'hui possible
la démonstration « l'agent se souvient de moi », alors qu'elle rend bien possible une
conversation UAM étalée sur plusieurs jours sans perte du contexte métier (formations déjà
évoquées, documents déjà cités par les outils, etc., tant que la question suivante
contient elle-même un mot-clé UAM).

---

## 5. Coût et conformité

**Coût.** L'API Cloud de WhatsApp Business facture selon un modèle par conversation
(fenêtres de 24 heures, catégories de conversation différenciées — service, marketing,
utilitaire…). Je ne dispose d'aucune source fiable et à jour pour donner un montant : les
tarifs varient par pays, par catégorie de conversation, et ont changé plusieurs fois dans
l'historique du produit. Donner un chiffre ici serait un chiffre inventé — **les montants
doivent être vérifiés directement auprès de Meta (Meta Business Suite / documentation
développeur) au moment de la décision**, pas déduits de ce document. Pour une
démonstration isolée avec un numéro de test et quelques messages, le volume est de toute
façon négligeable face à l'incertitude du chiffre lui-même.

**Conformité.** Le canal WhatsApp fait transiter des numéros de téléphone réels (donnée
personnelle) vers l'agent, et l'agent peut, sur demande, interroger un dossier étudiant
par matricule. Aucune mention de RGPD, de consentement ou de politique de confidentialité
n'existe dans le code applicatif de ce dépôt (recherche textuelle sur ces termes,
`*.py`/`*.md`/`*.html`, hors documents de planification internes : aucune occurrence
pertinente).

**SEC-01 — une faille qui change de nature avec le canal.** `search_student_record`
(`tools/base_donnees.py:34-177` — signature, docstring et gardes en 34-70, code qui produit
effectivement les paiements, les résultats et les crédits ECTS en 115-169) retourne, à
partir du seul matricule et sans aucune authentification, le statut d'inscription, les
paiements, les résultats et les crédits ECTS d'un étudiant (vérifié en lisant la fonction
en entier : aucun jeton, cookie ou identifiant de session n'est exigé — le paramètre
`matricule` suffit). Tant que l'agent n'est joignable qu'en local, avec 58 étudiants
simulés, c'est théorique. Sur un canal WhatsApp public,
n'importe qui peut écrire au numéro de l'université : il suffit de connaître ou deviner un
matricule au format documenté (`UAM` + 6 chiffres) pour obtenir le dossier scolaire d'un
tiers. La même faille change donc de nature : d'un risque de laboratoire à un risque
concret sur des données nominatives réelles, dès que de vraies données étudiantes
remplacent la simulation. Fait aggravant, trouvé en vérifiant le texte que l'agent renvoie
lui-même quand on lui demande ce qu'il sait faire (`get_agent_capabilities()`,
`tools/conversation.py:433-485`) : la réponse contient explicitement, ligne 483,
« Je ne peux pas accéder à vos données personnelles (notes, inscription individuelle) » —
une affirmation que `search_student_record` contredit directement. L'agent se présente
donc à l'utilisateur comme n'ayant pas cet accès, alors qu'il l'a. **Avant toute mise en
service de ce canal avec de vraies données étudiantes, cette faille doit être traitée** —
authentification, second facteur, ou restriction explicite du canal WhatsApp à des
questions non nominatives — ce n'est pas un arbitrage technique de ce document, mais une
décision produit qui revient à l'auteur.

---

## 6. Verdict et effort restant

**Verdict en deux temps**, parce que la réponse diffère selon l'objectif :

**Démonstration ponctuelle (soutenance), avec le numéro de test Meta et des données
simulées : faisable en l'état, sans écrire une ligne de code.** Tout le code nécessaire
existe et est cohérent (section 1). Ce qui reste est de la configuration pure : compte
Meta, `.env`, tunnel, déclaration du webhook — exactement le parcours déjà écrit dans
`WHATSAPP.md`, que ce document lui-même estime à une vingtaine de minutes (`WHATSAPP.md`
ligne 8) ; je n'ai pas rejoué ce parcours moi-même (aucune exécution de code dans cette
tâche), donc je ne peux confirmer ce chiffre de première main. J'ajoute une marge pour les
aléas (création de compte, dérive du tunnel, essais manqués) et j'estime la charge réelle
à **environ une demi-journée-homme**, à condition explicite de définir
`WHATSAPP_APP_SECRET` avant d'exposer le tunnel (SEC-02, section 2) et de préparer la
vidéo de secours (section 3).

**Mise en service durable, avec de vraies données étudiantes : non recommandé en l'état.**
Le blocage n'est pas technique au sens où le canal ne fonctionnerait pas — il fonctionnerait —
mais au sens où il exposerait, sans changement supplémentaire, un dossier scolaire nominatif
à quiconque écrit au numéro (SEC-01), sur la base d'un code qui affirme lui-même le
contraire à l'utilisateur. Liste ordonnée de ce qu'il faudrait faire, du plus bloquant au
plus différable :

1. **Toujours définir `WHATSAPP_APP_SECRET`** avant toute exposition publique du webhook
   (SEC-02). Effort : nul en développement — c'est une discipline de configuration, déjà
   documentée (`WHATSAPP.md` ligne 33), pas un correctif de code.
2. **Concevoir et implémenter une protection pour `search_student_record`** (SEC-01) :
   authentification, second facteur transmis par un canal distinct, ou restriction du
   canal WhatsApp aux questions non nominatives. Estimation **3 à 5 jours-hommes** —
   extrapolation : aucun mécanisme de ce type n'existe dans le dépôt, l'audit
   (`docs/superpowers/audit/2026-08-16-audit.md`, entrée SEC-01) qualifie lui-même le
   correctif de hors périmètre d'un simple round de correction, sans le chiffrer ; je pars
   d'un mécanisme minimal (code à usage unique envoyé par un canal déjà maîtrisé, ou
   filtrage des questions nominatives dans l'outil) plutôt que d'une authentification
   complète, ce qui reste à valider avec l'auteur.
3. **Rédiger une note de conformité** couvrant le traitement des numéros de téléphone et
   des matricules (aucune trace de ce travail dans le dépôt à ce jour). Estimation
   **1 à 2 jours-hommes** — extrapolation, fondée sur la taille du périmètre de données
   concerné (deux catégories : identité/téléphone, dossier scolaire), pas sur un
   précédent du projet.
4. **Obtenir un numéro WhatsApp Business vérifié et un token permanent côté Meta.**
   Démarche externe (vérification d'entreprise Meta), dont le délai n'est pas maîtrisable
   depuis ce dépôt et n'est pas quantifié ici : aucune preuve dans le dépôt qu'elle ait
   été entamée (les quatre variables sont vides, section 1).
5. **Remplacer le tunnel de démonstration par un hébergement HTTPS permanent.** Non
   chiffré précisément — dépend d'une décision d'hébergement qui n'existe pas encore ;
   de quelques heures à une journée selon la solution retenue, estimation basse
   confiance.
6. **Corriger BUG-10 si l'on veut réellement exploiter la mémoire conversationnelle en
   démonstration** (« l'agent se souvient de mon prénom ») — deux causes indépendantes,
   chacune déjà qualifiée par l'audit comme dépassant un round de correction et méritant
   sa propre tâche (routage sans historique dans `tools/conversation.py`/`graph_nodes.py`,
   garde-fou anti-hallucination dans `prompts.py`). Non chiffré ici : hors périmètre de ce
   document, et l'audit ne le chiffre pas non plus.

**Total pour les postes quantifiables en développement (2 et 3) : 4 à 7 jours-hommes**,
auxquels s'ajoute un délai côté Meta non maîtrisable (point 4) avant toute mise en service
avec de vraies données. Les postes 5 et 6 sont volontairement laissés hors total : l'un
dépend d'une décision d'hébergement non prise, l'autre est déjà renvoyé par l'audit à des
tâches séparées.

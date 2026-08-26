# Brancher l'agent UAM sur WhatsApp

Le même agent qui répond sur le site répond aussi sur WhatsApp : le code est déjà
en place ([api/whatsapp.py](api/whatsapp.py) et les deux routes `/webhook/whatsapp`
de [api/main.py](api/main.py)). Il ne reste qu'à créer l'application côté Meta et à
exposer le serveur local.

Comptez une vingtaine de minutes. Aucune vérification d'entreprise n'est nécessaire
pour la démonstration : Meta fournit un numéro de test gratuit.

---

## 1. Créer l'application Meta

1. Ouvrir [developers.facebook.com](https://developers.facebook.com) → **Mes applications**
   → **Créer une application** → type **Entreprise**.
2. Dans le tableau de bord, ajouter le produit **WhatsApp**.
3. Onglet **API Setup**, relever :
   - **Phone number ID** — l'identifiant du numéro de test (pas le numéro lui-même) ;
   - **Temporary access token** — valable **24 h seulement** ;
   - dans « To », ajouter votre propre numéro comme destinataire autorisé (jusqu'à 5).
4. Onglet **Paramètres de l'application → Général**, relever l'**App secret**.

> ⚠️ Le token expire au bout de 24 h. Le jour de la soutenance, régénérez-le le matin
> même et relancez le serveur.

## 2. Renseigner le `.env`

```env
WHATSAPP_VERIFY_TOKEN=uam-demo-2026     # chaîne de votre choix, recopiée à l'étape 4
WHATSAPP_ACCESS_TOKEN=EAAG...           # token temporaire de l'étape 1
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_APP_SECRET=abc123...           # valide la signature des webhooks
```

## 3. Démarrer le serveur et le tunnel

```bash
./run_api.sh                            # terminal 1 — http://localhost:8000
cloudflared tunnel --url http://localhost:8000   # terminal 2
```

`cloudflared` affiche une URL en `https://…trycloudflare.com`. `ngrok http 8000`
fait la même chose. **Cette URL change à chaque redémarrage du tunnel** : gardez-le
ouvert entre la configuration et la démonstration.

## 4. Déclarer le webhook chez Meta

Produit **WhatsApp → Configuration → Webhook → Modifier** :

| Champ | Valeur |
|---|---|
| URL de rappel | `https://VOTRE-TUNNEL.trycloudflare.com/webhook/whatsapp` |
| Jeton de vérification | la valeur de `WHATSAPP_VERIFY_TOKEN` |

Cliquer sur **Vérifier et enregistrer** : Meta appelle immédiatement la route en `GET`.
Le journal du serveur doit afficher `Webhook WhatsApp vérifié par Meta.`

Puis, sous **Champs de webhook**, s'abonner à **messages**. Sans cet abonnement, la
vérification passe mais aucun message n'arrive jamais.

## 5. Tester

Envoyer un message WhatsApp au numéro de test depuis votre téléphone. Le journal montre :

```
Message WhatsApp reçu de 227… : Quels sont les frais d'inscription ?
Réponse WhatsApp envoyée à 227… (5210 ms)
```

Sans téléphone sous la main, on peut simuler un message entrant :

```bash
curl -X POST localhost:8000/webhook/whatsapp -H "Content-Type: application/json" -d '{
  "entry":[{"changes":[{"value":{"messages":[
    {"id":"wamid.TEST","from":"22790000000","type":"text",
     "text":{"body":"Comment s'"'"'inscrire en L1 ?"}}]}}]}]}'
```

La réponse HTTP est immédiate (`200`) et l'agent travaille en arrière-plan — c'est
voulu : Meta n'attend pas, et rejoue les webhooks qu'il croit perdus.

---

## Ce que fait le code

| Comportement | Pourquoi |
|---|---|
| Accusé de réception `200` immédiat, traitement en tâche de fond | Meta impose un délai d'acquittement court ; une réponse prend 4 à 8 s |
| Déduplication sur l'identifiant du message | Sans elle, un webhook rejoué produit une réponse en double |
| Notifications de statut (envoyé, lu…) ignorées | Elles représentent la majorité des appels reçus |
| `thread_id = whatsapp:<numéro>` | Chaque contact garde le fil de sa conversation |
| Vérification de la signature `X-Hub-Signature-256` | Empêche l'injection de faux messages ; désactivée si `WHATSAPP_APP_SECRET` est absent |
| Markdown converti (`**gras**` → `*gras*`), messages découpés à 4 000 caractères | WhatsApp ignore le markdown et refuse au-delà de 4 096 caractères |

## Le jour de la soutenance

- Régénérer le token Meta le matin, remettre le `.env` à jour, relancer le serveur.
- Relancer le tunnel **et** recoller son URL dans la configuration du webhook.
- Enregistrer à l'avance une **capture vidéo de 30 s** de l'échange : le réseau d'une
  salle de soutenance et un tunnel gratuit sont deux points de défaillance que vous ne
  contrôlez pas.

## Pour aller en production

Le checkpointer LangGraph persiste désormais par défaut dans SQLite
([agent_graph.py:_build_checkpointer](agent_graph.py#L19)) : une conversation
survit à un redémarrage du serveur. Reste à obtenir un numéro WhatsApp vérifié
au nom de l'université et un hébergement HTTPS permanent — le tunnel décrit
plus haut ne convient qu'à une démonstration.

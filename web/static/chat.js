/* ==========================================================================
   Site UAM — assistant d'orientation et interactions de la page
   ========================================================================== */
(function () {
  "use strict";

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ── Session ───────────────────────────────────────────────────────────
     Le thread_id LangGraph : conservé d'une visite à l'autre pour que
     l'assistant garde le fil de la conversation. */
  const CLE_SESSION = "uam.session";

  function nouvelleSession() {
    const id = (crypto.randomUUID && crypto.randomUUID()) ||
               "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    localStorage.setItem(CLE_SESSION, id);
    return id;
  }

  let sessionId = localStorage.getItem(CLE_SESSION) || nouvelleSession();

  /* ── Panneau de l'assistant ────────────────────────────────────────── */

  const chat        = $("#chat");
  const fil         = $("[data-fil]");
  const voile       = $("[data-voile]");
  const bulle       = $(".bulle");
  const champChat   = $("[data-formulaire-chat] input");
  const boutonChat  = $("[data-formulaire-chat] button");
  let dernierFocus  = null;

  function ouvrirChat(question) {
    dernierFocus = document.activeElement;
    chat.hidden = false;
    voile.hidden = false;
    requestAnimationFrame(() => {
      chat.classList.add("chat--ouvert");
      voile.classList.add("voile--visible");
    });
    bulle.hidden = true;
    if (question) {
      envoyer(question);
    } else {
      champChat.focus();
    }
  }

  function fermerChat() {
    chat.classList.remove("chat--ouvert");
    voile.classList.remove("voile--visible");
    bulle.hidden = false;
    setTimeout(() => {
      chat.hidden = true;
      voile.hidden = true;
    }, 260);
    if (dernierFocus) dernierFocus.focus();
  }

  /* Remet le fil à zéro ET repart sur une session vierge côté serveur : une
     conversation longue coûte du contexte à chaque question, donc du temps. */
  function reinitialiserConversation() {
    sessionId = nouvelleSession();
    fil.innerHTML = "";
    fil.appendChild($("[data-accueil]").content.cloneNode(true));
    brancherSuggestions(fil);
    champChat.focus();
  }

  $$("[data-ouvre-chat]").forEach((btn) =>
    btn.addEventListener("click", () => ouvrirChat(btn.dataset.question || ""))
  );
  $$("[data-ferme-chat]").forEach((btn) => btn.addEventListener("click", fermerChat));
  $("[data-nouvelle-conversation]").addEventListener("click", reinitialiserConversation);
  voile.addEventListener("click", fermerChat);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && chat.classList.contains("chat--ouvert")) fermerChat();
  });

  /* ── Rendu des messages ────────────────────────────────────────────── */

  function echapper(texte) {
    const div = document.createElement("div");
    div.textContent = texte;
    return div.innerHTML;
  }

  /* Le LLM répond en markdown léger : on n'en rend que ce qui sert la lecture. */
  function enHtml(texte) {
    const lignes = echapper(texte).split("\n");
    let html = "";
    let dansListe = false;

    for (const ligne of lignes) {
      const puce = ligne.match(/^\s*[-*•]\s+(.*)$/);
      if (puce) {
        if (!dansListe) { html += "<ul>"; dansListe = true; }
        html += "<li>" + puce[1] + "</li>";
        continue;
      }
      if (dansListe) { html += "</ul>"; dansListe = false; }
      if (ligne.trim()) html += "<p>" + ligne + "</p>";
    }
    if (dansListe) html += "</ul>";

    return html
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*(?!\s)([^*]+?)\*(?=[\s.,;:)!?]|$)/g, "$1<em>$2</em>");
  }

  function auBas() {
    fil.scrollTop = fil.scrollHeight;
  }

  /* Temps de réponse et sources, ajoutés une fois la réponse terminée. */
  function ajouterMeta(bloc, sources, tempsMs) {
    if (!bloc) return;
    if (tempsMs === undefined && !(sources && sources.length)) return;

    const meta = document.createElement("div");
    meta.className = "msg__meta";
    if (tempsMs !== undefined) {
      meta.textContent = (tempsMs / 1000).toFixed(1) + " s";
    }
    bloc.appendChild(meta);

    if (sources && sources.length) {
      const details = document.createElement("details");
      details.className = "msg__sources";
      details.innerHTML =
        "<summary>Sources consultées (" + sources.length + ")</summary>" +
        sources
          .map(
            (s) =>
              '<div class="source"><span class="source__nom">' +
              echapper(s.source) +
              '</span><p class="source__extrait">' +
              echapper(s.content) +
              "…</p></div>"
          )
          .join("");
      bloc.appendChild(details);
    }
    auBas();
  }

  function ajouterMessage(role, contenu, options = {}) {
    const bloc = document.createElement("div");
    bloc.className = "msg msg--" + role + (options.erreur ? " msg--erreur" : "");
    bloc.innerHTML = role === "moi" ? "<p>" + echapper(contenu) + "</p>" : enHtml(contenu);

    fil.appendChild(bloc);
    ajouterMeta(bloc, options.sources, options.tempsMs);
    auBas();
    return bloc;
  }

  /* Réécrit le corps d'une bulle en cours de réception, en préservant les méta
     éventuellement déjà ajoutées. */
  function majBulle(bloc, texte) {
    const meta = bloc.querySelector(".msg__meta");
    const sources = bloc.querySelector(".msg__sources");
    bloc.innerHTML = enHtml(texte);
    if (meta) bloc.appendChild(meta);
    if (sources) bloc.appendChild(sources);
    auBas();
  }

  function ajouterAttente() {
    const bloc = document.createElement("div");
    bloc.className = "msg msg--bot";
    bloc.innerHTML =
      '<span class="attente" role="status" aria-label="Recherche en cours">' +
      "<span></span><span></span><span></span></span>" +
      '<span class="attente__libelle"></span>';
    fil.appendChild(bloc);
    auBas();
    return bloc;
  }

  /* Affiche l'étape en cours (« recherche dans les documents… ») pendant l'attente. */
  function majAttente(bloc, libelle) {
    const cible = bloc && bloc.querySelector(".attente__libelle");
    if (cible) cible.textContent = libelle || "";
  }

  /* ── Envoi ─────────────────────────────────────────────────────────── */

  let enCours = false;

  const ERREUR_SERVICE = "Le service n'a pas pu traiter cette question. Réessayez dans un instant.";
  const ERREUR_RESEAU =
    "Connexion au serveur impossible. Vérifiez que le service est démarré, puis réessayez.";

  async function envoyer(question) {
    question = (question || "").trim();
    if (!question || enCours) return;

    enCours = true;
    boutonChat.disabled = true;
    $$(".chat__suggestions").forEach((el) => el.remove());

    ajouterMessage("moi", question);
    const attente = ajouterAttente();

    try {
      await envoyerEnFlux(question, attente);
    } catch (err) {
      // Le flux a échoué : on retente une fois en mode classique, qui reste la
      // référence (c'est aussi le chemin utilisé par WhatsApp).
      try {
        await envoyerClassique(question, attente);
      } catch (err2) {
        attente.remove();
        ajouterMessage("bot", ERREUR_RESEAU, { erreur: true });
      }
    } finally {
      enCours = false;
      boutonChat.disabled = false;
      champChat.focus();
    }
  }

  /* Streaming (SSE) : la réponse s'affiche au fil de sa génération. Le temps total
     est le même, mais les premiers mots arrivent en quelques secondes. */
  async function envoyerEnFlux(question, attente) {
    const reponse = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, session_id: sessionId }),
    });

    if (!reponse.ok || !reponse.body) throw new Error("flux indisponible");

    const lecteur = reponse.body.getReader();
    const decodeur = new TextDecoder();
    let tampon = "";
    let bulle = null;
    let texte = "";

    for (;;) {
      const { done, value } = await lecteur.read();
      if (done) break;

      tampon += decodeur.decode(value, { stream: true });
      const blocs = tampon.split("\n\n");
      tampon = blocs.pop();

      for (const bloc of blocs) {
        const ligne = bloc.split("\n").find((l) => l.startsWith("data:"));
        if (!ligne) continue;  // commentaire SSE de maintien (« : ping »)

        let evenement;
        try {
          evenement = JSON.parse(ligne.slice(5).trim());
        } catch (e) {
          continue;
        }

        if (evenement.type === "etape") {
          majAttente(attente, evenement.libelle);
        } else if (evenement.type === "token") {
          if (!bulle) {
            attente.remove();
            bulle = ajouterMessage("bot", "");
          }
          texte += evenement.texte;
          majBulle(bulle, texte);
        } else if (evenement.type === "fin") {
          if (!bulle) {
            attente.remove();
            bulle = ajouterMessage("bot", evenement.response || texte);
          } else if (evenement.response && evenement.response !== texte) {
            // Le texte complet fait foi (le flux peut avoir perdu un fragment)
            texte = evenement.response;
            majBulle(bulle, texte);
          }
          ajouterMeta(bulle, evenement.sources, evenement.elapsed_ms);
        } else if (evenement.type === "erreur") {
          attente.remove();
          ajouterMessage("bot", evenement.message || ERREUR_SERVICE, { erreur: true });
          return;
        }
      }
    }

    if (!bulle) throw new Error("flux vide");
  }

  /* Mode classique : une seule réponse JSON, sans affichage progressif. */
  async function envoyerClassique(question, attente) {
    const reponse = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, session_id: sessionId }),
    });

    attente.remove();

    if (!reponse.ok) {
      ajouterMessage("bot", ERREUR_SERVICE, { erreur: true });
      return;
    }

    const donnees = await reponse.json();
    ajouterMessage("bot", donnees.response, {
      sources: donnees.sources,
      tempsMs: donnees.elapsed_ms,
    });
  }

  $("[data-formulaire-chat]").addEventListener("submit", (e) => {
    e.preventDefault();
    const valeur = champChat.value;
    champChat.value = "";
    envoyer(valeur);
  });

  const formulaireHero = $("[data-formulaire-hero]");
  if (formulaireHero) {
    formulaireHero.addEventListener("submit", (e) => {
      e.preventDefault();
      const champ = $("input", formulaireHero);
      const valeur = champ.value;
      champ.value = "";
      ouvrirChat(valeur);
    });
  }

  // Les suggestions du panneau sont recréées à chaque nouvelle conversation :
  // le branchement doit donc pouvoir être rejoué sur un sous-arbre.
  function brancherSuggestions(racine) {
    $$("[data-suggestions] button", racine).forEach((btn) =>
      btn.addEventListener("click", () => ouvrirChat(btn.textContent.trim()))
    );
  }

  // Fil initial : le même contenu que celui rejoué par « Nouvelle conversation »
  fil.appendChild($("[data-accueil]").content.cloneNode(true));
  brancherSuggestions(document);

  // Lien direct vers l'assistant : http://…/#assistant l'ouvre au chargement
  if (location.hash === "#assistant") ouvrirChat();

  /* ── Fiches des composantes ────────────────────────────────────────── */

  $$("[data-fiche]").forEach((carte) => {
    const ouvrir = () => {
      const dialogue = document.getElementById(carte.dataset.fiche);
      if (dialogue) dialogue.showModal();
    };
    carte.addEventListener("click", ouvrir);
    carte.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        ouvrir();
      }
    });
  });

  // Les boutons « interroger l'assistant » placés dans les fiches
  $$("dialog [data-ouvre-chat]").forEach((btn) =>
    btn.addEventListener("click", () => btn.closest("dialog").close())
  );

  /* ── Filtre des composantes ────────────────────────────────────────── */

  const cartes = $$("[data-composantes] .carte");
  $$("[data-filtre-type]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("[data-filtre-type]").forEach((b) => b.classList.remove("puce--on"));
      btn.classList.add("puce--on");
      const type = btn.dataset.filtreType;
      cartes.forEach((c) => {
        c.hidden = type !== "tous" && c.dataset.type !== type;
      });
    });
  });

  /* ── Filtre des formations ─────────────────────────────────────────── */

  const table = $("[data-table-formations]");
  if (table) {
    const lignes     = $$("tbody tr", table);
    const recherche  = $("[data-recherche-formation]");
    const selComp    = $("[data-filtre-composante]");
    const selNiveau  = $("[data-filtre-niveau]");
    const compteur   = $("[data-compteur-formations]");
    const messageVide = $("[data-vide-formations]");

    function filtrer() {
      const texte  = recherche.value.trim().toLowerCase();
      const comp   = selComp.value;
      const niveau = selNiveau.value;
      let visibles = 0;

      lignes.forEach((ligne) => {
        const ok =
          (!texte || ligne.dataset.texte.includes(texte)) &&
          (!comp || ligne.dataset.composante === comp) &&
          (!niveau || ligne.dataset.niveau === niveau);
        ligne.hidden = !ok;
        if (ok) visibles++;
      });

      compteur.textContent = visibles + (visibles > 1 ? " résultats" : " résultat");
      messageVide.hidden = visibles > 0;
    }

    [recherche, selComp, selNiveau].forEach((el) => {
      el.addEventListener("input", filtrer);
      el.addEventListener("change", filtrer);
    });
  }

  /* ── Menu mobile ───────────────────────────────────────────────────── */

  const burger = $("[data-burger]");
  const nav = $(".nav");
  if (burger) {
    burger.addEventListener("click", () => {
      const ouvert = nav.classList.toggle("nav--ouverte");
      burger.setAttribute("aria-expanded", String(ouvert));
    });
    $$(".nav a").forEach((a) =>
      a.addEventListener("click", () => {
        nav.classList.remove("nav--ouverte");
        burger.setAttribute("aria-expanded", "false");
      })
    );
  }

  /* ── Révélation au défilement ──────────────────────────────────────── */

  const animations = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (animations && "IntersectionObserver" in window) {
    const cibles = $$(".section .titre, .section .duo, .cartes, .chiffres__grille, .contacts");
    cibles.forEach((el) => el.classList.add("reveal"));

    const observateur = new IntersectionObserver(
      (entrees) => {
        entrees.forEach((entree) => {
          if (entree.isIntersecting) {
            entree.target.classList.add("reveal--vu");
            observateur.unobserve(entree.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    cibles.forEach((el) => observateur.observe(el));
  }
})();

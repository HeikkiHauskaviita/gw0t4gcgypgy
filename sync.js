/* ============================================================
   PERHESYNKKA — jaettu tila GitHub-repon data-haarassa
   ============================================================
   Synkronoi sivujen localStorage-tilan perheen laitteiden välillä.

   Toimintaperiaate:
   - Data tallentuu JSON-tiedostoina repon `data`-haaraan (ei main-haaraan,
     jotta GitHub Pages ei buildaa joka tallennuksesta).
   - LUKU: julkinen repo → pull onnistuu ilman tokenia kaikilta laitteilta.
   - KIRJOITUS: vaatii fine-grained personal access tokenin (vain tämän
     repon Contents: Read and write -oikeus). Token syötetään kerran per
     laite ⇅-napista ja tallentuu selaimeen.
   - Ristiriidat: koko tiedosto "viimeisin voittaa" -periaatteella
     (paivitetty-aikaleima). Perhekäyttöön riittävä.

   Sivu tunnistetaan localStorage-avaimista (SYNC_BUNDLES). Tallennukset
   havaitaan kietomalla localStorage.setItem — siksi tämä tiedosto pitää
   ladata <head>issä ENNEN sivun omia skriptejä.
   ============================================================ */
(function () {
  "use strict";

  var OWNER = "HeikkiHauskaviita";
  var REPO = "gw0t4gcgypgy";
  var BRANCH = "data";
  var API = "https://api.github.com/repos/" + OWNER + "/" + REPO;
  var TOKEN_KEY = "perhe-sync-token";
  var META_KEY = "perhe-sync-meta";
  var PUSH_DEBOUNCE_MS = 8000;

  // Mitkä localStorage-avaimet kuuluvat millekin sivulle/tiedostolle.
  // "keys" = täsmäavaimet, "prefixes" = kaikki avaimet jotka alkavat näin.
  var SYNC_BUNDLES = [
    { file: "data/ruokalista.json",  keys: ["perheen-ruokalista-v3"], prefixes: [] },
    { file: "data/huoltokirja.json", keys: ["perheen-huoltokirja-v1"], prefixes: [] },
    { file: "data/siivous.json",     keys: [], prefixes: ["siivous-"] }
  ];
  // Näitä ei koskaan synkata (laitekohtaisia)
  var IGNORE_KEYS = [TOKEN_KEY, META_KEY, "ruokalista-theme"];

  function nowIso() { return new Date().toISOString(); }

  function loadMeta() {
    try { return JSON.parse(localStorage.getItem(META_KEY)) || {}; } catch (e) { return {}; }
  }
  function saveMeta(meta) {
    try { rawSetItem.call(localStorage, META_KEY, JSON.stringify(meta)); } catch (e) {}
  }
  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }

  function bundleForKey(key) {
    if (!key || IGNORE_KEYS.indexOf(key) !== -1) return null;
    for (var i = 0; i < SYNC_BUNDLES.length; i++) {
      var b = SYNC_BUNDLES[i];
      if (b.keys.indexOf(key) !== -1) return b;
      for (var j = 0; j < b.prefixes.length; j++) {
        if (key.indexOf(b.prefixes[j]) === 0) return b;
      }
    }
    return null;
  }

  // Sivulla läsnä olevat bundlet = ne joiden avaimia on localStoragessa TAI
  // joiden avaimia sivu kirjoittaa (havaitaan setItem-kiedonnassa).
  function activeBundles() {
    var act = [];
    for (var i = 0; i < SYNC_BUNDLES.length; i++) {
      var b = SYNC_BUNDLES[i];
      var found = false;
      for (var k = 0; k < localStorage.length; k++) {
        if (bundleForKey(localStorage.key(k)) === b) { found = true; break; }
      }
      if (found) act.push(b);
    }
    return act;
  }

  function collectBundle(b) {
    var keys = {};
    for (var k = 0; k < localStorage.length; k++) {
      var key = localStorage.key(k);
      if (bundleForKey(key) === b) keys[key] = localStorage.getItem(key);
    }
    return { paivitetty: nowIso(), keys: keys };
  }

  function applyBundle(b, payload) {
    if (!payload || typeof payload.keys !== "object") return;
    // Poista ensin bundleen kuuluvat paikalliset avaimet (esim. poistetut kuukaudet)
    var toRemove = [];
    for (var k = 0; k < localStorage.length; k++) {
      var key = localStorage.key(k);
      if (bundleForKey(key) === b && !(key in payload.keys)) toRemove.push(key);
    }
    toRemove.forEach(function (key) { localStorage.removeItem(key); });
    Object.keys(payload.keys).forEach(function (key) {
      rawSetItem.call(localStorage, key, payload.keys[key]);
    });
  }

  // ---------- GitHub API ----------
  function apiHeaders(withAuth) {
    var h = { "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
    var t = getToken();
    if (withAuth && t) h["Authorization"] = "Bearer " + t;
    return h;
  }

  function fetchRemote(b) {
    // Julkinen luku — ei tokenia tarvita. cache-bust query estää välimuistin.
    return fetch(API + "/contents/" + b.file + "?ref=" + BRANCH + "&t=" + Date.now(), {
      headers: apiHeaders(true)
    }).then(function (r) {
      if (r.status === 404) return { missing: true };
      if (!r.ok) throw new Error("GitHub-luku epäonnistui (" + r.status + ")");
      return r.json().then(function (j) {
        var text = "";
        try { text = decodeURIComponent(escape(atob((j.content || "").replace(/\n/g, "")))); } catch (e) {}
        var payload = null;
        try { payload = JSON.parse(text); } catch (e) {}
        return { sha: j.sha, payload: payload };
      });
    });
  }

  function ensureBranch() {
    // Luo data-haara mainin päälle jos sitä ei vielä ole (vaatii tokenin).
    return fetch(API + "/git/ref/heads/" + BRANCH, { headers: apiHeaders(true) })
      .then(function (r) {
        if (r.ok) return true;
        if (r.status !== 404) throw new Error("Haaran tarkistus epäonnistui (" + r.status + ")");
        return fetch(API + "/git/ref/heads/main", { headers: apiHeaders(true) })
          .then(function (r2) {
            if (!r2.ok) throw new Error("main-haaran luku epäonnistui");
            return r2.json();
          })
          .then(function (j) {
            return fetch(API + "/git/refs", {
              method: "POST",
              headers: apiHeaders(true),
              body: JSON.stringify({ ref: "refs/heads/" + BRANCH, sha: j.object.sha })
            });
          })
          .then(function (r3) {
            if (!r3.ok) throw new Error("data-haaran luonti epäonnistui (" + r3.status + ")");
            return true;
          });
      });
  }

  function pushBundle(b, attempt) {
    attempt = attempt || 0;
    var payload = collectBundle(b);
    var body = JSON.stringify(payload, null, 1);
    var b64 = btoa(unescape(encodeURIComponent(body)));
    var meta = loadMeta();
    var fileMeta = meta[b.file] || {};

    return ensureBranch().then(function () {
      var put = {
        message: "sync: " + b.file.replace("data/", "").replace(".json", ""),
        content: b64,
        branch: BRANCH
      };
      if (fileMeta.sha) put.sha = fileMeta.sha;
      return fetch(API + "/contents/" + b.file, {
        method: "PUT",
        headers: apiHeaders(true),
        body: JSON.stringify(put)
      });
    }).then(function (r) {
      if ((r.status === 409 || r.status === 422) && attempt < 1) {
        // sha vanhentunut — hae tuore ja yritä kerran uudelleen (LWW)
        return fetchRemote(b).then(function (remote) {
          var m = loadMeta();
          m[b.file] = m[b.file] || {};
          m[b.file].sha = remote.sha || null;
          saveMeta(m);
          return pushBundle(b, attempt + 1);
        });
      }
      if (!r.ok) throw new Error("Tallennus GitHubiin epäonnistui (" + r.status + ")");
      return r.json();
    }).then(function (j) {
      if (j && j.content) {
        var m = loadMeta();
        m[b.file] = m[b.file] || {};
        m[b.file].sha = j.content.sha;
        m[b.file].lastPushed = payload.paivitetty;
        m[b.file].touchedAt = null;
        saveMeta(m);
      }
      return true;
    });
  }

  // ---------- pull sivua avattaessa ----------
  function pullAll(manual) {
    var bundles = activeBundles();
    if (!bundles.length) bundles = SYNC_BUNDLES; // ensikäynti: kokeile kaikkia
    var applied = false;
    var chain = Promise.resolve();
    bundles.forEach(function (b) {
      chain = chain.then(function () {
        return fetchRemote(b).then(function (remote) {
          var meta = loadMeta();
          meta[b.file] = meta[b.file] || {};
          if (remote.missing || !remote.payload) {
            saveMeta(meta);
            return;
          }
          meta[b.file].sha = remote.sha;
          var localTouched = meta[b.file].touchedAt || null;
          var lastApplied = meta[b.file].lastApplied || null;
          var remoteTime = remote.payload.paivitetty || null;
          // Sovella jos remote on uudempi kuin viimeksi sovellettu EIKÄ
          // paikallisia tallentamattomia muutoksia ole remoten jälkeen.
          var isNew = remoteTime && remoteTime !== lastApplied;
          var localNewer = localTouched && remoteTime && localTouched > remoteTime;
          if (isNew && !localNewer) {
            applyBundle(b, remote.payload);
            meta[b.file].lastApplied = remoteTime;
            applied = true;
          }
          saveMeta(meta);
        });
      });
    });
    return chain.then(function () {
      if (applied) {
        // Lataa sivu kerran uudelleen, jotta sivun skriptit lukevat uuden tilan.
        var guard = null;
        try { guard = sessionStorage.getItem("perhe-sync-reloaded"); } catch (e) {}
        var stamp = nowIso().slice(0, 16);
        if (manual || guard !== stamp) {
          try { sessionStorage.setItem("perhe-sync-reloaded", stamp); } catch (e) {}
          location.reload();
          return "reload";
        }
      }
      return applied ? "applied" : "uptodate";
    });
  }

  // ---------- push-jono ----------
  var pushTimers = {};
  function queuePush(b) {
    var meta = loadMeta();
    meta[b.file] = meta[b.file] || {};
    meta[b.file].touchedAt = nowIso();
    saveMeta(meta);
    setStatus("pending");
    if (!getToken()) return; // vain luku -tila: muutokset jäävät paikallisiksi
    clearTimeout(pushTimers[b.file]);
    pushTimers[b.file] = setTimeout(function () {
      setStatus("syncing");
      pushBundle(b).then(function () {
        setStatus("ok", "Synkronoitu " + new Date().toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" }));
      }).catch(function (e) {
        setStatus("error", e.message);
      });
    }, PUSH_DEBOUNCE_MS);
  }

  function flushAll() {
    if (!getToken()) return;
    var meta = loadMeta();
    SYNC_BUNDLES.forEach(function (b) {
      var fm = meta[b.file];
      if (fm && fm.touchedAt && pushTimers[b.file]) {
        clearTimeout(pushTimers[b.file]);
        pushBundle(b).catch(function () {});
      }
    });
  }
  window.addEventListener("pagehide", flushAll);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flushAll();
  });

  // ---------- localStorage-kiedonta ----------
  var rawSetItem = Storage.prototype.setItem;
  var rawRemoveItem = Storage.prototype.removeItem;
  Storage.prototype.setItem = function (key, value) {
    rawSetItem.call(this, key, value);
    if (this === window.localStorage) {
      var b = bundleForKey(key);
      if (b) queuePush(b);
    }
  };
  Storage.prototype.removeItem = function (key) {
    rawRemoveItem.call(this, key);
    if (this === window.localStorage) {
      var b = bundleForKey(key);
      if (b) queuePush(b);
    }
  };

  // ---------- käyttöliittymä (kelluva ⇅-merkki + dialogi) ----------
  var chip, dialog;
  function setStatus(state, title) {
    if (!chip) return;
    var colors = {
      readonly: "#9d8a63",
      ok: "#d4a94a",
      pending: "#d4a94a",
      syncing: "#f0c76a",
      error: "#c85a5a"
    };
    chip.style.borderColor = colors[state] || colors.readonly;
    chip.style.color = colors[state] || colors.readonly;
    chip.textContent = state === "syncing" ? "⇅ …" : state === "error" ? "⇅ !" : "⇅";
    chip.title = title || {
      readonly: "Perhesynkka: vain luku (lisää token kirjoittaaksesi)",
      ok: "Perhesynkka: ajan tasalla",
      pending: "Perhesynkka: tallentamattomia muutoksia",
      syncing: "Perhesynkka: synkronoidaan…",
      error: "Perhesynkka: virhe"
    }[state] || "Perhesynkka";
  }

  function buildUi() {
    chip = document.createElement("button");
    chip.id = "perheSyncChip";
    chip.type = "button";
    chip.setAttribute("aria-label", "Perhesynkan asetukset");
    chip.style.cssText =
      "position:fixed;bottom:14px;right:14px;z-index:9999;" +
      "background:rgba(10,6,18,0.85);border:1px solid #9d8a63;color:#9d8a63;" +
      "font-size:16px;line-height:1;padding:8px 10px;cursor:pointer;border-radius:2px;" +
      "font-family:Georgia,serif;";
    chip.addEventListener("click", openDialog);
    document.body.appendChild(chip);
    setStatus(getToken() ? "ok" : "readonly");
  }

  function openDialog() {
    if (dialog) { dialog.remove(); dialog = null; return; }
    dialog = document.createElement("div");
    dialog.style.cssText =
      "position:fixed;bottom:54px;right:14px;z-index:9999;width:min(340px,90vw);" +
      "background:#1a102a;border:1px solid rgba(212,169,74,0.5);color:#ede4cc;" +
      "padding:14px 16px;font-family:Georgia,serif;font-size:14px;line-height:1.5;" +
      "box-shadow:0 4px 24px rgba(0,0,0,0.7);";
    var hasToken = !!getToken();
    dialog.innerHTML =
      '<strong style="letter-spacing:0.08em">PERHESYNKKA</strong><br>' +
      '<span style="color:#9d8a63">Tila: ' + (hasToken ? "luku + kirjoitus" : "vain luku") + "</span>" +
      '<p style="margin:8px 0">Tiedot haetaan GitHubista sivua avattaessa. Kirjoittamiseen tarvitaan token (Settings → Developer settings → Fine-grained tokens; oikeudeksi vain tämän repon Contents: Read and write).</p>' +
      '<input id="psTokenInput" type="password" placeholder="github_pat_…" style="width:100%;padding:6px;background:rgba(0,0,0,0.3);border:1px solid rgba(212,169,74,0.4);color:#ede4cc;font-size:13px"><br>' +
      '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">' +
      '<button id="psSaveToken" style="padding:6px 12px;cursor:pointer;background:#d4a94a;border:none;color:#1a0f00">Tallenna token</button>' +
      '<button id="psSyncNow" style="padding:6px 12px;cursor:pointer;background:transparent;border:1px solid rgba(212,169,74,0.5);color:#d4a94a">Synkronoi nyt</button>' +
      (hasToken ? '<button id="psClearToken" style="padding:6px 12px;cursor:pointer;background:transparent;border:1px solid rgba(200,90,90,0.5);color:#c85a5a">Poista token</button>' : "") +
      "</div>";
    document.body.appendChild(dialog);
    dialog.querySelector("#psSaveToken").addEventListener("click", function () {
      var v = dialog.querySelector("#psTokenInput").value.trim();
      if (!v) return;
      rawSetItem.call(localStorage, TOKEN_KEY, v);
      dialog.remove(); dialog = null;
      setStatus("ok", "Token tallennettu tälle laitteelle");
    });
    dialog.querySelector("#psSyncNow").addEventListener("click", function () {
      setStatus("syncing");
      flushAll();
      pullAll(true).then(function (res) {
        if (res !== "reload") setStatus(getToken() ? "ok" : "readonly", "Haettu " + new Date().toLocaleTimeString("fi-FI"));
      }).catch(function (e) { setStatus("error", e.message); });
      dialog.remove(); dialog = null;
    });
    var clearBtn = dialog.querySelector("#psClearToken");
    if (clearBtn) clearBtn.addEventListener("click", function () {
      localStorage.removeItem(TOKEN_KEY);
      dialog.remove(); dialog = null;
      setStatus("readonly");
    });
  }

  // ---------- käynnistys ----------
  function start() {
    buildUi();
    pullAll(false).then(function (res) {
      if (res === "uptodate" || res === "applied") {
        setStatus(getToken() ? "ok" : "readonly");
      }
    }).catch(function (e) {
      // Offline tms. — sivu toimii paikallisella datalla normaalisti.
      setStatus("error", "Synkka ei käytettävissä: " + e.message);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

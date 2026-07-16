/* Tender tool interactions — vanilla JS (self-hosted, strict-CSP safe, no eval).
   Alpine is avoided because the production CSP forbids the unsafe-eval it needs.
   Covers: assignee search, upload-form reset, local-AI (DeepSeek) helpers, and
   Ably realtime chat + notifications. */
(function () {
  "use strict";

  function csrfToken() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function postForm(url, fields) {
    var body = new URLSearchParams(fields);
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  // Poll an AIJob until it's ready/failed. Resolves with the result text or
  // rejects with an error message. ~90s ceiling (60 × 1.5s).
  function pollJob(pollUrl) {
    return new Promise(function (resolve, reject) {
      var attempts = 0;
      (function tick() {
        attempts += 1;
        fetch(pollUrl)
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.status === "ready") return resolve(d.result || "");
            if (d.status === "failed") return reject(new Error(d.error || "The AI request failed."));
            if (attempts >= 60) return reject(new Error("Timed out waiting for the AI."));
            setTimeout(tick, 1500);
          })
          .catch(function () {
            if (attempts >= 60) return reject(new Error("Network error."));
            setTimeout(tick, 1500);
          });
      })();
    });
  }

  // --- Searchable assignee list --------------------------------------------
  document.querySelectorAll("[data-assignee-picker]").forEach(function (picker) {
    var search = picker.querySelector("[data-assignee-search]");
    if (!search) return;
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      picker.querySelectorAll("[data-assignee-option]").forEach(function (option) {
        option.style.display = option.textContent.toLowerCase().indexOf(q) !== -1 ? "" : "none";
      });
    });
  });

  // --- Reset upload/chat forms after a successful HTMX post -----------------
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    var form = evt.target;
    if (!form || !form.matches || !form.matches("form[data-reset-on-success]")) return;
    var xhr = evt.detail && evt.detail.xhr;
    if (xhr && xhr.status >= 200 && xhr.status < 300) {
      form.reset();
      var docPlaceholder = document.getElementById("no-current-docs");
      if (docPlaceholder) docPlaceholder.remove();
      var chatPlaceholder = document.querySelector("[data-chat-empty]");
      if (chatPlaceholder) chatPlaceholder.remove();
      var log = document.getElementById("chat-log");
      if (log) log.scrollTop = log.scrollHeight;
    }
  });

  // --- Local AI (DeepSeek) helpers ------------------------------------------
  var aiPanel = document.getElementById("ai-panel");
  if (aiPanel) {
    var output = aiPanel.querySelector("[data-ai-output]");
    var errBox = aiPanel.querySelector("[data-ai-error]");
    function showOutput(text) {
      errBox.classList.add("hidden");
      output.textContent = text;
      output.classList.remove("hidden");
    }
    function showError(text) {
      output.classList.add("hidden");
      errBox.textContent = text;
      errBox.classList.remove("hidden");
    }
    // Enqueue (202 + poll_url), then poll the AIJob to completion.
    function run(btn, url, fields) {
      var label = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Thinking…";
      postForm(url, fields)
        .then(function (res) {
          if (res.status === 202 && res.data.poll_url) return pollJob(res.data.poll_url).then(showOutput);
          throw new Error((res.data && res.data.error) || "The AI request failed.");
        })
        .catch(function (e) { showError(e.message || "The AI request failed."); })
        .finally(function () { btn.disabled = false; btn.textContent = label; });
    }
    var askBtn = aiPanel.querySelector("[data-ai-ask]");
    if (askBtn) {
      askBtn.addEventListener("click", function () {
        var q = document.getElementById("ai-question").value.trim();
        if (!q) return;
        run(askBtn, aiPanel.dataset.askUrl, { question: q });
      });
    }
    var emailBtn = aiPanel.querySelector("[data-ai-draft-email]");
    if (emailBtn) {
      emailBtn.addEventListener("click", function () {
        run(emailBtn, aiPanel.dataset.emailUrl, { purpose: "a friendly progress update" });
      });
    }
  }

  // Draft description on the create/edit form.
  var draftDescBtn = document.querySelector("[data-ai-draft-description]");
  if (draftDescBtn) {
    draftDescBtn.addEventListener("click", function () {
      var status = document.querySelector("[data-ai-desc-status]");
      var title = document.querySelector(draftDescBtn.dataset.title);
      var client = document.querySelector(draftDescBtn.dataset.client);
      var sector = document.querySelector(draftDescBtn.dataset.sector);
      var target = document.querySelector(draftDescBtn.dataset.target);
      if (!title || !title.value.trim()) { status.textContent = "Enter a title first."; return; }
      draftDescBtn.disabled = true;
      status.textContent = "Drafting…";
      postForm(draftDescBtn.dataset.url, {
        title: title.value, client_name: client ? client.value : "", sector: sector ? sector.value : "",
      })
        .then(function (res) {
          if (res.status === 202 && res.data.poll_url) {
            return pollJob(res.data.poll_url).then(function (text) {
              if (target) target.value = text;
              status.textContent = "Draft inserted.";
            });
          }
          throw new Error((res.data && res.data.error) || "AI request failed.");
        })
        .catch(function (e) { status.textContent = e.message || "Network error."; })
        .finally(function () { draftDescBtn.disabled = false; });
    });
  }

  // --- Toast notifications --------------------------------------------------
  function showToast(message, url) {
    var wrap = document.getElementById("toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toast-wrap";
      wrap.style.cssText = "position:fixed;bottom:1rem;right:1rem;z-index:200;display:flex;flex-direction:column;gap:.5rem;";
      document.body.appendChild(wrap);
    }
    var toast = document.createElement(url ? "a" : "div");
    if (url) toast.href = url;
    toast.textContent = message;               // textContent → XSS-safe
    toast.className = "card px-4 py-3 text-sm shadow-lg";
    toast.style.cssText = "max-width:20rem;text-decoration:none;";
    wrap.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 6000);
  }

  // --- Ably realtime chat + notifications -----------------------------------
  function subscribeNotifications(client) {
    client.channels.get("staff-notifications").subscribe(function (msg) {
      showToast((msg.data && msg.data.message) || "Update", msg.data && msg.data.url);
    });
  }

  var chatPanel = document.getElementById("chat-panel");
  var notifConfig = document.getElementById("notif-config");

  if (chatPanel && chatPanel.dataset.realtime === "1" && window.Ably) {
    var log = document.getElementById("chat-log");
    var client = new Ably.Realtime({ authUrl: chatPanel.dataset.tokenUrl, authMethod: "GET" });

    function appendIncoming(d) {
      if (!d || !d.id) return;
      if (document.querySelector('[data-message-id="' + d.id + '"]')) return; // dedupe own
      var empty = document.querySelector("[data-chat-empty]");
      if (empty) empty.remove();
      var row = document.createElement("div");
      row.className = "flex gap-2.5";
      row.setAttribute("data-message-id", d.id);
      var avatar = document.createElement("span");
      avatar.className = "shrink-0 h-8 w-8 rounded-full bg-brand text-on-brand text-xs font-semibold inline-flex items-center justify-center";
      avatar.textContent = (d.author || "?").slice(0, 1).toUpperCase();
      var col = document.createElement("div");
      col.className = "max-w-[75%]";
      var meta = document.createElement("p");
      meta.className = "text-xs text-ink-subtle";
      meta.textContent = (d.author || "Unknown") + " · " + (d.created || "");
      var bubble = document.createElement("div");
      bubble.className = "mt-1 rounded-lg px-3 py-2 text-sm bg-surface-sunken text-ink";
      bubble.textContent = d.body || "";        // textContent → XSS-safe
      col.appendChild(meta); col.appendChild(bubble);
      row.appendChild(avatar); row.appendChild(col);
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
    }

    client.channels.get(chatPanel.dataset.tenderChannel).subscribe("message", function (msg) {
      appendIncoming(msg.data);
    });
    subscribeNotifications(client);
  } else if (notifConfig && notifConfig.dataset.realtime === "1" && window.Ably) {
    // Notifications-only pages (list, dashboard) — no chat channel.
    var notifClient = new Ably.Realtime({ authUrl: notifConfig.dataset.tokenUrl, authMethod: "GET" });
    subscribeNotifications(notifClient);
  }
})();

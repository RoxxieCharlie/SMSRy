(() => {
  window.__smsModalReady = true;
  const modal = document.getElementById("appModal");
  if (!modal) return;

  const titleEl = document.getElementById("appModalTitle");
  const subtitleEl = document.getElementById("appModalSubtitle");
  const bodyEl = document.getElementById("appModalBody");
  const iconEl = modal.querySelector(".app-modal__icon");
  const closeEls = modal.querySelectorAll("[data-modal-close]");
  const messageRoot = document.getElementById("djMessages");

  const queue = [];
  let isOpen = false;
  let activeType = "info";
  let redirectUrl = "";

  const _ico = (path) => `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
  const typeConfig = {
    success: { className: "is-success", title: "Success", subtitle: "Action completed successfully.", icon: _ico('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>') },
    error:   { className: "is-error",   title: "Error",   subtitle: "Please review and correct the issue.", icon: _ico('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>') },
    warning: { className: "is-error",   title: "Warning", subtitle: "Action requires attention.", icon: _ico('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>') },
    info:    { className: "",            title: "Notice",  subtitle: "", icon: _ico('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>') },
  };

  function normalizeType(tags) {
    const tagSet = new Set((tags || "").split(/\s+/).filter(Boolean).map((t) => t.toLowerCase()));
    if (tagSet.has("error")) return "error";
    if (tagSet.has("warning")) return "warning";
    if (tagSet.has("success")) return "success";
    return "info";
  }

  function setModalType(type) {
    activeType = type;
    modal.classList.remove("is-success", "is-error");
    const cfg = typeConfig[type] || typeConfig.info;
    if (cfg.className) modal.classList.add(cfg.className);
    if (titleEl) titleEl.textContent = cfg.title;
    if (subtitleEl) subtitleEl.textContent = cfg.subtitle;
    if (iconEl) iconEl.innerHTML = cfg.icon;
  }

  function showModal(message, type) {
    setModalType(type);
    if (bodyEl) bodyEl.textContent = message || "";
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    isOpen = true;
  }

  function closeModal() {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    isOpen = false;
    if (queue.length > 0) {
      const next = queue.shift();
      showModal(next.message, next.type);
      return;
    }

    if (activeType === "success" && redirectUrl) {
      const to = redirectUrl;
      redirectUrl = "";
      window.location.assign(to);
    }
  }

  function enqueueMessage(message, tags) {
    const type = normalizeType(tags);
    queue.push({ message, type });
  }

  function drainInitialMessages() {
    if (!messageRoot) return;
    redirectUrl = (messageRoot.dataset.redirectUrl || "").trim();
    const messageEls = messageRoot.querySelectorAll(".dj-msg");
    messageEls.forEach((el) => enqueueMessage((el.textContent || "").trim(), el.dataset.tags || ""));
  }

  closeEls.forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen) closeModal();
  });

  drainInitialMessages();
  if (queue.length > 0) {
    const first = queue.shift();
    showModal(first.message, first.type);
  }
})();



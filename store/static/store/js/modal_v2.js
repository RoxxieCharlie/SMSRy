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

  const typeConfig = {
    success: { className: "is-success", title: "Success", subtitle: "Action completed successfully.", icon: "OK" },
    error: { className: "is-error", title: "Error", subtitle: "Please review and correct the issue.", icon: "!" },
    warning: { className: "is-error", title: "Warning", subtitle: "Action requires attention.", icon: "!" },
    info: { className: "", title: "Notice", subtitle: "", icon: "i" },
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
    if (iconEl) iconEl.textContent = cfg.icon;
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



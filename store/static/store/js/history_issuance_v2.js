(() => {
  if (window.__issuanceHistoryInit) return;
  window.__issuanceHistoryInit = true;

  const root = document.querySelector(".table-wrapper");
  if (!root) return;

  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle-items]");
    if (!btn) return;

    const row = btn.closest("tr");
    const detailsRow = row?.nextElementSibling;

    if (!detailsRow || !detailsRow.classList.contains("details-row")) return;

    const isOpen = !detailsRow.hidden;

    // close other open panels (optional, clean UX)
    document.querySelectorAll(".details-row:not([hidden])").forEach(r => {
      if (r !== detailsRow) {
        r.hidden = true;
        const trigger = r.previousElementSibling?.querySelector("[data-toggle-items]");
        if (trigger) {
          trigger.classList.remove("is-open");
          trigger.setAttribute("aria-expanded", "false");
        }
      }
    });

    // toggle this one
    detailsRow.hidden = isOpen;
    btn.classList.toggle("is-open", !isOpen);
    btn.setAttribute("aria-expanded", String(!isOpen));
  });
})();
(() => {
  // Guard: prevent double init if loaded twice
  if (window.__historyStockinV2Init) return;
  window.__historyStockinV2Init = true;

  // We delegate clicks from the table container
  const wrap = document.querySelector(".table-wrap");
  if (!wrap) return;

  wrap.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle-items]");
    if (!btn) return;

    const row = btn.closest("tr");
    if (!row) return;

    const detailsRow = row.nextElementSibling;
    if (!detailsRow || !detailsRow.classList.contains("details-row")) return;

    const isOpen = !detailsRow.hidden;

    // Optional: close any other open details rows (clean UX)
    wrap.querySelectorAll(".details-row:not([hidden])").forEach((r) => {
      if (r !== detailsRow) {
        r.hidden = true;
        const trigger = r.previousElementSibling?.querySelector("[data-toggle-items]");
        if (trigger) {
          trigger.classList.remove("is-open");
          trigger.setAttribute("aria-expanded", "false");
        }
      }
    });

    // Toggle this one
    detailsRow.hidden = isOpen;

    btn.classList.toggle("is-open", !isOpen);
    btn.setAttribute("aria-expanded", String(!isOpen));
  });
})();
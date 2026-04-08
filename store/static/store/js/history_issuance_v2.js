(function () {
  if (window.__issuanceHistoryInit) return;
  window.__issuanceHistoryInit = true;

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-toggle-items]");
    if (!btn) return;

    var row = btn.closest("tr");
    if (!row) return;
    var detailsRow = row.nextElementSibling;
    if (!detailsRow) return;
    if (!detailsRow.classList.contains("details-row")) return;

    var isOpen = !detailsRow.hidden;
    document.querySelectorAll(".details-row:not([hidden])").forEach(function (openRow) {
      if (openRow === detailsRow) return;
      openRow.hidden = true;
      var trigger = openRow.previousElementSibling;
      if (trigger) trigger = trigger.querySelector("[data-toggle-items]");
      if (trigger) {
        trigger.classList.remove("is-open");
        trigger.setAttribute("aria-expanded", "false");
      }
    });

    detailsRow.hidden = isOpen;
    btn.classList.toggle("is-open", !isOpen);
    btn.setAttribute("aria-expanded", String(!isOpen));
  });
}());

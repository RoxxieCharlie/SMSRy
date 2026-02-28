// static/store/js/issue_item_v2.js
(() => {
  // Prevent double init (the #1 cause of "adds 2 rows")
  if (window.__ISSUE_ITEM_V2_INIT__) return;
  window.__ISSUE_ITEM_V2_INIT__ = true;

  const rowsWrap = document.getElementById("rows");
  if (!rowsWrap) return;

  const itemsCount = document.getElementById("itemsCount");
  const totalItems = document.getElementById("totalItems");

  const addRowBtnTop = document.getElementById("addRowBtnTop"); // may be null (you commented it)
  const addRowBtnMid = document.getElementById("addRowBtnMid"); // may be null (you removed it)
  const fabAdd = document.getElementById("fabAdd");

  const cancelBtn = document.getElementById("cancelBtn");
  const form = document.getElementById("issuanceForm");

  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  function updateCounters() {
    const n = rowsWrap.querySelectorAll("[data-row]").length;
    if (itemsCount) itemsCount.textContent = `${n} item${n === 1 ? "" : "s"}`;
    if (totalItems) totalItems.textContent = String(n);
  }

  function setStockPill(row) {
    const select = row.querySelector(".item-select");
    const pill = row.querySelector("[data-stockpill]");
    const qtyInput = row.querySelector(".qty-input");
    if (!select || !pill || !qtyInput) return;

    const opt = select.options[select.selectedIndex];
    const stockStr = opt?.getAttribute("data-stock");
    const stock = stockStr !== null && stockStr !== undefined && stockStr !== ""
      ? Number(stockStr)
      : null;

    pill.classList.remove("stock-ok", "stock-bad", "stock-unknown");

    if (stock === null || Number.isNaN(stock)) {
      pill.textContent = "--";
      pill.classList.add("stock-unknown");
      return;
    }

    const qty = Number(qtyInput.value || 0);
    if (stock <= 0) {
      pill.textContent = "0 in stock";
      pill.classList.add("stock-bad");
    } else {
      pill.textContent = `${stock} in stock`;
      pill.classList.add(qty > stock ? "stock-bad" : "stock-ok");
    }
  }

  function renumberNames() {
    const rows = rowsWrap.querySelectorAll("[data-row]");
    rows.forEach((row, i) => {
      const itemSel = row.querySelector(".item-select");
      const qtyInput = row.querySelector(".qty-input");
      if (!itemSel || !qtyInput) return;

      itemSel.name = `items[${i}][item_id]`;
      qtyInput.name = `items[${i}][qty]`;
    });
  }

  function resetRow(row) {
    const select = row.querySelector(".item-select");
    const qty = row.querySelector(".qty-input");
    if (select) select.selectedIndex = 0;
    if (qty) qty.value = "1";
    setStockPill(row);
  }

  function createRow() {
    const first = rowsWrap.querySelector("[data-row]");
    if (!first) return;

    const clone = first.cloneNode(true);
    resetRow(clone);

    rowsWrap.appendChild(clone);
    renumberNames();
    updateCounters();
  }

  // -------------------------
  // EVENT DELEGATION (rows)
  // -------------------------
  // One handler for ALL rows (prevents per-row double binding issues)
  rowsWrap.addEventListener("click", (e) => {
    const row = e.target.closest("[data-row]");
    if (!row) return;

    const stepBtn = e.target.closest("[data-step]");
    const removeBtn = e.target.closest("[data-remove]");

    if (stepBtn) {
      const qtyInput = row.querySelector(".qty-input");
      if (!qtyInput) return;

      const step = Number(stepBtn.getAttribute("data-step"));
      const val = Number(qtyInput.value || 1);
      qtyInput.value = String(clamp(val + step, 1, 999999));
      setStockPill(row);
      return;
    }

    if (removeBtn) {
      const all = rowsWrap.querySelectorAll("[data-row]");
      if (all.length === 1) {
        resetRow(row);
        return;
      }
      row.remove();
      renumberNames();
      updateCounters();
      return;
    }
  });

  rowsWrap.addEventListener("change", (e) => {
    const row = e.target.closest("[data-row]");
    if (!row) return;
    if (e.target.matches(".item-select")) setStockPill(row);
  });

  rowsWrap.addEventListener("input", (e) => {
    const row = e.target.closest("[data-row]");
    if (!row) return;
    if (e.target.matches(".qty-input")) {
      if (!e.target.value || Number(e.target.value) < 1) e.target.value = "1";
      setStockPill(row);
    }
  });

  // Init existing rows
  rowsWrap.querySelectorAll("[data-row]").forEach(setStockPill);
  renumberNames();
  updateCounters();

  // -------------------------
  // SAFE button binding
  // -------------------------
  [addRowBtnTop, addRowBtnMid, fabAdd].forEach((btn) => {
    if (!btn) return;
    btn.removeEventListener("click", createRow); // idempotent
    btn.addEventListener("click", createRow);
  });

  // Cancel
  if (cancelBtn && form) {
    cancelBtn.addEventListener("click", () => {
      form.reset();

      const rows = Array.from(rowsWrap.querySelectorAll("[data-row]"));
      rows.slice(1).forEach(r => r.remove());

      const first = rowsWrap.querySelector("[data-row]");
      if (first) resetRow(first);

      renumberNames();
      updateCounters();
    });
  }

  // Optional submit validation (qty <= stock)
  if (form) {
    form.addEventListener("submit", (e) => {
      const rows = rowsWrap.querySelectorAll("[data-row]");
      for (const row of rows) {
        const select = row.querySelector(".item-select");
        const qtyInput = row.querySelector(".qty-input");
        if (!select || !qtyInput) continue;

        const opt = select.options[select.selectedIndex];
        const stockStr = opt?.getAttribute("data-stock");
        const stock = stockStr ? Number(stockStr) : null;
        const qty = Number(qtyInput.value || 0);

        if (stock !== null && !Number.isNaN(stock) && stock >= 0 && qty > stock) {
          e.preventDefault();
          alert("One or more items exceed available stock. Adjust quantities before saving.");
          return;
        }
      }
    });
  }
})();

(() => {
  const modal = document.getElementById("appModal");
  const msgWrap = document.getElementById("djMessages");

  if (!modal || !msgWrap) return;

  const titleEl = document.getElementById("appModalTitle");
  const subtitleEl = document.getElementById("appModalSubtitle");
  const bodyEl = document.getElementById("appModalBody");

  const closeEls = modal.querySelectorAll("[data-modal-close]");

  let timer = null;

  function closeModal() {
    if (timer) clearTimeout(timer);
    timer = null;
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    modal.classList.remove("is-success", "is-error");
  }

  function openModal({ type, title, subtitle, body, autocloseMs }) {
    if (timer) clearTimeout(timer);
    timer = null;

    modal.classList.remove("is-success", "is-error");
    modal.classList.add(type === "success" ? "is-success" : "is-error");

    if (titleEl) titleEl.textContent = title || (type === "success" ? "Success" : "Action Failed");
    if (subtitleEl) subtitleEl.textContent = subtitle || "";
    if (bodyEl) bodyEl.textContent = body || "";

    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");

    if (autocloseMs && autocloseMs > 0) {
      timer = setTimeout(closeModal, autocloseMs);
    }
  }

  closeEls.forEach((el) => el.addEventListener("click", closeModal));

  // Close on ESC
  window.addEventListener("keydown", (e) => {
    if (!modal.hidden && e.key === "Escape") closeModal();
  });

  // Read Django messages
  const msgs = Array.from(msgWrap.querySelectorAll(".dj-msg")).map((el) => {
    const tags = (el.getAttribute("data-tags") || "").toLowerCase();
    const text = (el.textContent || "").trim();
    return { tags, text };
  }).filter(m => m.text);

  if (!msgs.length) return;

  // Priority: show first ERROR if any, else show first SUCCESS/info
  const err = msgs.find(m => m.tags.includes("error") || m.tags.includes("danger"));
  const ok = msgs.find(m => m.tags.includes("success")) || msgs[0];

  if (err) {
    openModal({
      type: "error",
      title: "Error",
      subtitle: "Please fix this and try again.",
      body: err.text,
      autocloseMs: 0, // errors do NOT auto close
    });
    return;
  }

  openModal({
    type: "success",
    title: "Saved",
    subtitle: "Your action completed successfully.",
    body: ok.text,
    autocloseMs: 3500, // success auto closes
  });
})();
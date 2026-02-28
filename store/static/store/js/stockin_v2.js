(() => {
  // ✅ Guard: if this file is loaded twice, do nothing the 2nd time
  if (window.__stockInV2Initialized) return;
  window.__stockInV2Initialized = true;

  const rowsWrap = document.getElementById("rows");
  const itemsCount = document.getElementById("itemsCount");
  const totalItems = document.getElementById("totalItems");
  const fabAdd = document.getElementById("fabAdd");
  const cancelBtn = document.getElementById("cancelBtn");
  const form = document.getElementById("stockInForm");
  const documentInput = document.getElementById("document");

  if (!rowsWrap || !itemsCount || !totalItems || !fabAdd || !cancelBtn || !form) return;

  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  function updateCounters() {
    const n = rowsWrap.querySelectorAll("[data-row]").length;
    itemsCount.textContent = `${n} item${n === 1 ? "" : "s"}`;
    totalItems.textContent = String(n);
  }

  function setStockPill(row) {
    const select = row.querySelector(".item-select");
    const pill = row.querySelector("[data-stockpill]");
    if (!select || !pill) return;

    const opt = select.options[select.selectedIndex];
    const stockStr = opt?.getAttribute("data-stock");
    const stock = stockStr ? Number(stockStr) : null;

    pill.classList.remove("stock-ok", "stock-unknown");

    if (stock === null || Number.isNaN(stock)) {
      pill.textContent = "--";
      pill.classList.add("stock-unknown");
      return;
    }

    pill.textContent = `${stock} in stock`;
    pill.classList.add("stock-ok");
  }

  function renumberNames() {
    const rows = rowsWrap.querySelectorAll("[data-row]");
    rows.forEach((row, i) => {
      const select = row.querySelector(".item-select");
      const qty = row.querySelector(".qty-input");
      if (select) select.name = `items[${i}][item_id]`;
      if (qty) qty.name = `items[${i}][qty]`;
    });
  }

  function bindRow(row) {
    // ✅ prevent double-binding per row (if anything re-calls bindRow)
    if (row.dataset.bound === "1") return;
    row.dataset.bound = "1";

    const select = row.querySelector(".item-select");
    const qtyInput = row.querySelector(".qty-input");

    row.addEventListener("click", (e) => {
      const stepBtn = e.target.closest("[data-step]");
      const removeBtn = e.target.closest("[data-remove]");

      if (stepBtn && qtyInput) {
        const step = Number(stepBtn.getAttribute("data-step"));
        const val = Number(qtyInput.value || 1);
        qtyInput.value = String(clamp(val + step, 1, 999999));
      }

      if (removeBtn) {
        const all = rowsWrap.querySelectorAll("[data-row]");
        if (all.length === 1) {
          if (select) select.selectedIndex = 0;
          if (qtyInput) qtyInput.value = "1";
          setStockPill(row);
          return;
        }
        row.remove();
        renumberNames();
        updateCounters();
      }
    });

    if (select) select.addEventListener("change", () => setStockPill(row));

    if (qtyInput) {
      qtyInput.addEventListener("input", () => {
        if (!qtyInput.value || Number(qtyInput.value) < 1) qtyInput.value = "1";
      });
    }

    setStockPill(row);
  }

  function createRow() {
    const first = rowsWrap.querySelector("[data-row]");
    const clone = first.cloneNode(true);

    // ✅ IMPORTANT: remove the "already bound" marker copied from the first row
    delete clone.dataset.bound;              // or: clone.removeAttribute("data-bound")

    // reset fields
    clone.querySelector(".item-select").selectedIndex = 0;
    clone.querySelector(".qty-input").value = "1";
    clone.querySelector("[data-stockpill]").textContent = "--";
    clone.querySelector("[data-stockpill]").classList.remove("stock-ok");
    clone.querySelector("[data-stockpill]").classList.add("stock-unknown");

    rowsWrap.appendChild(clone);

    bindRow(clone);
    renumberNames();
    updateCounters();
  }

  // init
  rowsWrap.querySelectorAll("[data-row]").forEach(bindRow);
  renumberNames();
  updateCounters();

  // ✅ bind FAB once
  if (fabAdd.dataset.bound !== "1") {
    fabAdd.dataset.bound = "1";
    fabAdd.addEventListener("click", createRow);
  }

  cancelBtn.addEventListener("click", () => {
    form.reset();

    const rows = Array.from(rowsWrap.querySelectorAll("[data-row]"));
    rows.slice(1).forEach((r) => r.remove());

    const first = rowsWrap.querySelector("[data-row]");
    if (first) {
      const select = first.querySelector(".item-select");
      const qty = first.querySelector(".qty-input");
      if (select) select.selectedIndex = 0;
      if (qty) qty.value = "1";
      setStockPill(first);
    }

    if (documentInput) documentInput.value = "";

    renumberNames();
    updateCounters();
  });

  form.addEventListener("submit", (e) => {
    const rows = rowsWrap.querySelectorAll("[data-row]");
    for (const row of rows) {
      const select = row.querySelector(".item-select");
      const qtyInput = row.querySelector(".qty-input");
      if (!select?.value) {
        e.preventDefault();
        alert("Please select an item in each row.");
        return;
      }
      if (Number(qtyInput?.value || 0) < 1) {
        e.preventDefault();
        alert("Quantity must be at least 1.");
        return;
      }
    }
  });

  // ✅ optional: auto-dismiss toasts if you add them (below)
  const toasts = document.querySelectorAll("[data-toast]");
  toasts.forEach((t) => {
    setTimeout(() => t.classList.add("hide"), 4500);
    t.querySelector("[data-toast-close]")?.addEventListener("click", () => t.classList.add("hide"));
  });
})();
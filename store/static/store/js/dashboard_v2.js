// static/store/js/dashboard_v2.js
(() => {
  // Guard
  if (window.__dashboardV2SearchInit) return;
  window.__dashboardV2SearchInit = true;

  const input = document.getElementById("globalSearch");
  const dropdown = document.getElementById("searchDropdown");
  if (!input || !dropdown) return;

  const SEARCH_URL = input.getAttribute("data-search-url");
  if (!SEARCH_URL) return;

  let controller = null;
  let activeIndex = -1;
  let flatItems = []; // keyboard navigation targets (action links)
  let lastData = null; // latest JSON response for Enter routing

  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  const debounce = (fn, delay = 180) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  };

  // CSS.escape fallback (some browsers)
  const cssEscape = (value) => {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(value);
    // minimal safe fallback:
    return String(value).replace(/["\\]/g, "\\$&");
  };

  function hideDropdown() {
    dropdown.hidden = true;
    dropdown.innerHTML = "";
    activeIndex = -1;
    flatItems = [];
    lastData = null;
  }

  function showDropdown() {
    dropdown.hidden = false;
  }

  function injectDropdownStylesOnce() {
    if (document.getElementById("dashboardSearchStyles")) return;

    const style = document.createElement("style");
    style.id = "dashboardSearchStyles";
    style.textContent = `
      /* Dashboard search dropdown (theme-aligned) */
      .search__dropdown{ padding: 10px; }

      .sd__section{ padding: 6px 0 10px; }
      .sd__sectionTitle{
        font-size: 11px;
        letter-spacing: .10em;
        text-transform: uppercase;
        color: rgba(234,240,255,.55);
        padding: 8px 10px;
      }

      .sd__row{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap: 12px;
        padding: 10px 10px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,.06);
        background: rgba(0,0,0,.10);
        margin: 6px 4px;
        transition: background .12s ease, border-color .12s ease;
        cursor: pointer;
      }

      .sd__row:hover{
        background: rgba(255,255,255,.06);
        border-color: rgba(255,255,255,.12);
      }

      .sd__row.is-active{
        background: rgba(78,165,255,.14);
        border-color: rgba(78,165,255,.30);
        box-shadow: 0 0 0 2px rgba(78,165,255,.14) inset;
      }

      .sd__main{ min-width: 0; }
      .sd__label{
        font-weight: 850;
        color: rgba(234,240,255,.92);
        font-size: 13px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 360px;
      }
      .sd__meta{
        font-size: 12px;
        color: rgba(234,240,255,.55);
        margin-top: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 360px;
      }

      .sd__actions{
        display:flex;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-end;
      }

      .sd__action{
        text-decoration:none;
        font-size: 12px;
        font-weight: 800;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,.12);
        background: rgba(255,255,255,.06);
        color: rgba(234,240,255,.80);
        transition: background .12s ease, border-color .12s ease, transform .12s ease;
      }

      .sd__action:hover{
        background: rgba(255,255,255,.10);
        border-color: rgba(255,255,255,.18);
        transform: translateY(-1px);
      }

      .sd__empty{
        padding: 14px 12px;
        color: rgba(234,240,255,.55);
        font-size: 13px;
      }

      @media (max-width: 640px){
        .sd__label, .sd__meta{ max-width: 220px; }
      }
    `;
    document.head.appendChild(style);
  }

  function buildSection(title, rows) {
    if (!rows || rows.length === 0) return "";

    const itemsHtml = rows
      .map((row) => {
        const actions = (row.actions || [])
          .map((a) => {
            const url = escapeHtml(a.url);
            const label = escapeHtml(a.label);
            return `<a class="sd__action" href="${url}" data-url="${url}">${label}</a>`;
          })
          .join("");

        // Row-level default navigation: prefer "Issuances", else first action
        const rowDefaultUrl =
          (row.actions || []).find((a) => (a.label || "").toLowerCase() === "issuances")?.url ||
          (row.actions || [])[0]?.url ||
          "";

        return `
          <div class="sd__row" role="option" tabindex="-1" data-default-url="${escapeHtml(rowDefaultUrl)}">
            <div class="sd__main">
              <div class="sd__label">${escapeHtml(row.label)}</div>
              ${row.meta ? `<div class="sd__meta">${escapeHtml(row.meta)}</div>` : ""}
            </div>
            <div class="sd__actions">${actions}</div>
          </div>
        `;
      })
      .join("");

    return `
      <div class="sd__section">
        <div class="sd__sectionTitle">${escapeHtml(title)}</div>
        ${itemsHtml}
      </div>
    `;
  }

  function flattenForKeyboard(data) {
    const blocks = [
      ...(data.items || []),
      ...(data.staff || []),
      ...(data.storekeepers || []),
      ...(data.departments || []),
    ];

    const out = [];
    blocks.forEach((row) => {
      (row.actions || []).forEach((a) => {
        out.push({ url: a.url });
      });
    });
    return out;
  }

  function render(data) {
    lastData = data;
    injectDropdownStylesOnce();

    const html =
      buildSection("Items", data.items) +
      buildSection("Staff", data.staff) +
      buildSection("Storekeepers", data.storekeepers) +
      buildSection("Departments", data.departments);

    dropdown.innerHTML = html || `<div class="sd__empty">No results</div>`;
    showDropdown();

    flatItems = flattenForKeyboard(data);
    activeIndex = -1;
  }

  const doSearch = debounce(async () => {
    const q = input.value.trim();
    if (!q) {
      hideDropdown();
      return;
    }

    if (controller) controller.abort();
    controller = new AbortController();

    try {
      const url = `${SEARCH_URL}?q=${encodeURIComponent(q)}`;
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      render(data);
    } catch (err) {
      if (err.name === "AbortError") return;
      dropdown.innerHTML = `<div class="sd__empty">Could not load results.</div>`;
      showDropdown();
      flatItems = [];
      activeIndex = -1;
      lastData = null;
    }
  }, 200);

  // Typing triggers search
  input.addEventListener("input", doSearch);

  // Show dropdown on focus (if it has content)
  input.addEventListener("focus", () => {
    if (input.value.trim() && dropdown.innerHTML.trim()) showDropdown();
  });

  // Click handling (event delegation)
  dropdown.addEventListener("click", (e) => {
    const action = e.target.closest(".sd__action");
    if (action) {
      // let normal navigation happen, but close dropdown immediately for UX
      hideDropdown();
      return;
    }

    const row = e.target.closest(".sd__row");
    if (!row) return;

    const url = row.getAttribute("data-default-url");
    if (url) {
      window.location.href = url;
      hideDropdown();
    }
  });

  // Click outside closes dropdown (tolerant: supports .search wrapper or input wrapper)
  document.addEventListener("click", (e) => {
    const inside =
      e.target.closest(".search") ||
      e.target.closest("#globalSearch") ||
      e.target.closest("#searchDropdown");
    if (!inside) hideDropdown();
  });

  // Keyboard navigation: Up/Down highlights action links, Enter routes
  input.addEventListener("keydown", (e) => {
    if (dropdown.hidden) return;

    if (e.key === "Escape") {
      hideDropdown();
      return;
    }

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!flatItems.length) return;

      activeIndex =
        e.key === "ArrowDown"
          ? Math.min(activeIndex + 1, flatItems.length - 1)
          : Math.max(activeIndex - 1, 0);

      dropdown.querySelectorAll(".sd__row").forEach((r) => r.classList.remove("is-active"));

      const active = flatItems[activeIndex];
      const link = dropdown.querySelector(`a[data-url="${cssEscape(active.url)}"]`);
      const row = link?.closest(".sd__row");
      if (row) {
        row.classList.add("is-active");
        row.scrollIntoView({ block: "nearest" });
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();

      // If user navigated with arrows, go to highlighted action
      if (activeIndex >= 0 && flatItems.length) {
        const active = flatItems[activeIndex];
        if (active?.url) window.location.href = active.url;
        hideDropdown();
        return;
      }

      // Otherwise route to "best match" from the latest results
      const d = lastData || {};
      const firstItem = (d.items || [])[0];
      const firstStaff = (d.staff || [])[0];
      const firstKeeper = (d.storekeepers || [])[0];
      const firstDept = (d.departments || [])[0];

      const pickAction = (row, preferredLabel) => {
        const actions = row?.actions || [];
        if (!actions.length) return null;
        const preferred = actions.find(
          (a) => (a.label || "").toLowerCase() === preferredLabel.toLowerCase()
        );
        return preferred || actions[0];
      };

      // Priority: Item > Staff > Storekeeper > Department
      const target =
        pickAction(firstItem, "Issuances") ||
        pickAction(firstStaff, "Issuances") ||
        pickAction(firstKeeper, "Issuances") ||
        pickAction(firstDept, "Issuances");

      if (target?.url) window.location.href = target.url;
      hideDropdown();
    }
  });
})();
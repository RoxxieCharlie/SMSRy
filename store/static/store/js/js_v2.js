(function () {
  const input = document.getElementById("globalSearch");
  const dropdown = document.getElementById("searchDropdown");
  if (!input || !dropdown) return;

  let timer = null;
  let lastQuery = "";

  function hide() {
    dropdown.hidden = true;
    dropdown.innerHTML = "";
  }

  function section(title, items) {
    if (!items || !items.length) return "";
    const rows = items.map(it => `
      <a class="dd__item" href="${it.url}">
        <span>${it.label}</span>
        <span class="dd__meta">${it.meta ?? ""}</span>
      </a>
    `).join("");
    return `
      <div class="dd__section">
        <div class="dd__title">${title}</div>
        ${rows}
      </div>
    `;
  }

  async function runSearch(q) {
    const url = input.dataset.searchUrl;
    if (!url) return;

    dropdown.hidden = false;
    dropdown.innerHTML = `<div class="dd__section"><div class="dd__title">Searching…</div></div>`;

    const res = await fetch(`${url}?q=${encodeURIComponent(q)}`, { headers: { "X-Requested-With": "XMLHttpRequest" } });
    if (!res.ok) throw new Error("Search failed");
    return await res.json();
  }

  input.addEventListener("input", () => {
    const q = input.value.trim();
    if (q.length < 2) return hide();
    if (q === lastQuery) return;

    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        lastQuery = q;
        const data = await runSearch(q);
        dropdown.innerHTML =
          section("Items", data.items) +
          section("Staff", data.staff) +
          section("Departments", data.departments);

        dropdown.hidden = dropdown.innerHTML.trim().length === 0;
      } catch (e) {
        dropdown.hidden = false;
        dropdown.innerHTML = `<div class="dd__section"><div class="dd__title">No results</div></div>`;
      }
    }, 250);
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target) && e.target !== input) hide();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hide();
  });
})();
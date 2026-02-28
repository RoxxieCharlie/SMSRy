document.addEventListener("DOMContentLoaded", function() {

  const table = document.getElementById("inventoryTable");
  const searchInput = document.getElementById("searchInput");
  const categoryFilter = document.getElementById("categoryFilter");

  // Search + Filter
  function filterTable() {
    const searchValue = searchInput.value.toLowerCase();
    const categoryValue = categoryFilter.value.toLowerCase();

    Array.from(table.tBodies[0].rows).forEach(row => {
      const name = row.querySelector(".item-name").innerText.toLowerCase();
      const category = row.querySelector(".item-category").innerText.toLowerCase();

      const matchesSearch = name.includes(searchValue);
      const matchesCategory = !categoryValue || category === categoryValue;

      row.style.display = matchesSearch && matchesCategory ? "" : "none";
    });
  }

  searchInput.addEventListener("input", filterTable);
  categoryFilter.addEventListener("change", filterTable);

  // Sorting
  document.querySelectorAll("th[data-sort]").forEach(header => {
    header.addEventListener("click", () => {
      const index = Array.from(header.parentNode.children).indexOf(header);
      const rows = Array.from(table.tBodies[0].rows);

      const asc = header.classList.toggle("asc");

      rows.sort((a, b) => {
        const A = a.cells[index].innerText;
        const B = b.cells[index].innerText;

        if (!isNaN(A) && !isNaN(B)) {
          return asc ? A - B : B - A;
        }
        return asc ? A.localeCompare(B) : B.localeCompare(A);
      });

      rows.forEach(row => table.tBodies[0].appendChild(row));
    });
  });

});
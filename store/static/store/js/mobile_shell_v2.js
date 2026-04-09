(function () {
  const body = document.body;
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const close = document.querySelector("[data-mobile-nav-close]");
  const sidebar = document.querySelector(".sidebar");

  if (!toggle || !close || !sidebar) return;

  function setOpen(isOpen) {
    body.classList.toggle("nav-open", isOpen);
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    close.hidden = !isOpen;
  }

  toggle.addEventListener("click", function () {
    setOpen(!body.classList.contains("nav-open"));
  });

  close.addEventListener("click", function () {
    setOpen(false);
  });

  sidebar.addEventListener("click", function (event) {
    const link = event.target.closest(".nav__link");
    if (link && window.innerWidth <= 820) {
      setOpen(false);
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 820) {
      setOpen(false);
    }
  });
})();

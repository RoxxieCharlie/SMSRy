(() => {
  const btn = document.querySelector("[data-toggle-password]");
  const input = document.getElementById("passwordInput");
  if (!btn || !input) return;

  btn.addEventListener("click", () => {
    const isPwd = input.getAttribute("type") === "password";
    input.setAttribute("type", isPwd ? "text" : "password");
    btn.setAttribute("aria-pressed", isPwd ? "true" : "false");
  });
})();
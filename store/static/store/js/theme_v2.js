(function () {
  var THEME_KEY = 'sms-theme';

  function getPreferred() {
    var stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
    return window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light' : 'dark';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-label',
        theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      btn.setAttribute('data-current-theme', theme);
      var icon = btn.querySelector('.theme-toggle__icon');
      var label = btn.querySelector('.theme-toggle__label');
      if (icon) icon.textContent = theme === 'dark' ? '◑' : '◐';
      if (label) label.textContent =
        theme === 'dark' ? 'Light mode' : 'Dark mode';
    });
  }

  function toggleTheme() {
    var current =
      document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getPreferred());
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', toggleTheme);
    });
  });
})();

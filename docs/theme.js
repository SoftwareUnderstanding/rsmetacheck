// rsmetacheck docs — light/dark theme toggle (shared).
// Injects a small toggle button (top-right) and switches the theme by setting
// data-theme on <html>. With no choice made, the OS preference still applies.
(function () {
  if (document.querySelector('.theme-toggle')) return;

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'theme-toggle';
  btn.setAttribute('aria-label', 'Toggle light and dark mode');
  document.body.appendChild(btn);

  var mq = window.matchMedia('(prefers-color-scheme: dark)');

  function currentTheme() {
    var t = document.documentElement.dataset.theme;
    if (t === 'dark' || t === 'light') return t;
    return mq.matches ? 'dark' : 'light';
  }

  function sync() {
    btn.textContent = currentTheme() === 'dark' ? 'Light' : 'Dark';
  }

  btn.addEventListener('click', function () {
    var root = document.documentElement;
    root.classList.add('theming');
    root.dataset.theme = currentTheme() === 'dark' ? 'light' : 'dark';
    sync();
    window.setTimeout(function () { root.classList.remove('theming'); }, 260);
  });

  sync();
})();

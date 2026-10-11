/* Blocking external script: no credentials, inline JS, or network access. */
(function () {
  var preference = 'system';
  try {
    var saved = localStorage.getItem('routeshield-theme');
    if (saved === 'light' || saved === 'dark') preference = saved;
  } catch { /* Storage can be denied; system preference still works. */ }
  var dark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = preference === 'system' ? (dark ? 'dark' : 'light') : preference;
  document.documentElement.dataset.themePreference = preference;
}());

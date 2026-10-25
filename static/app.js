'use strict';
document.querySelectorAll('[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
document.querySelectorAll('.dismiss-flash').forEach(button => {
  button.addEventListener('click', () => button.closest('.flash').remove());
});
document.querySelectorAll('.password-toggle').forEach(button => {
  button.addEventListener('click', () => {
    const field = document.getElementById(button.dataset.target);
    const show = field.type === 'password';
    field.type = show ? 'text' : 'password';
    button.setAttribute('aria-label', show ? 'Ukryj hasło' : 'Pokaż hasło');
    button.setAttribute('aria-pressed', String(show));
  });
});

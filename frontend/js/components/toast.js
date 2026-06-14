/* ═══════════════════════════════════════════
   toast.js — Toast notification system
   ═══════════════════════════════════════════ */

function toast(message, type = 'info') {
  const wrap = document.getElementById('toast-wrap');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: 'check', error: 'alert', info: 'info' };
  el.innerHTML = `${iconSvg(icons[type] || 'info')}<span>${message}</span>`;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 2200);
  setTimeout(() => el.remove(), 2600);
}

'use strict';
(() => {
  const button = document.getElementById('sidebar-toggle');
  function setCollapsed(collapsed) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    button.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
    button.title = collapsed ? 'Expand navigation' : 'Collapse navigation';
    try { localStorage.setItem('flowscope-sidebar-collapsed', String(collapsed)); } catch {}
  }
  let collapsed = false;
  try { collapsed = localStorage.getItem('flowscope-sidebar-collapsed') === 'true'; } catch {}
  setCollapsed(collapsed);
  button.addEventListener('click', () => setCollapsed(!document.body.classList.contains('sidebar-collapsed')));
})();

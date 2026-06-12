/* ============================================================
   McGee Family Website — Shared JS
   Nav toggle · Lightbox · Active link highlighting
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ── NAV MOBILE TOGGLE ─────────────────────────────────────
  const toggle = document.querySelector('.nav-mobile-toggle');
  const links  = document.querySelector('.nav-links');

  if (toggle && links) {
    toggle.addEventListener('click', () => {
      const isOpen = links.classList.toggle('open');
      toggle.textContent = isOpen ? '✕' : '☰';
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
    links.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        links.classList.remove('open');
        toggle.textContent = '☰';
      });
    });
  }

  // ── ACTIVE NAV LINK ──────────────────────────────────────
  const current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === current || (current === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });

  // ── NAV MORE DROPDOWN ─────────────────────────────────────
  const moreBtn  = document.querySelector('.nav-more-btn');
  const moreItem = document.querySelector('.nav-more');

  if (moreBtn && moreItem) {
    // Toggle on button click
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = moreItem.classList.toggle('open');
      moreBtn.setAttribute('aria-expanded', String(isOpen));
    });
    // Close when clicking anywhere outside
    document.addEventListener('click', (e) => {
      if (!moreItem.contains(e.target)) {
        moreItem.classList.remove('open');
        moreBtn.setAttribute('aria-expanded', 'false');
      }
    });
    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        moreItem.classList.remove('open');
        moreBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ── FADE-UP OBSERVER ─────────────────────────────────────
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationDelay = entry.target.dataset.delay || '0s';
        entry.target.classList.add('fade-up');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  document.querySelectorAll('[data-animate]').forEach(el => observer.observe(el));

}); // end DOMContentLoaded

// ── SERVICE WORKER ────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .catch(() => {}); // Silent fail — SW is an enhancement
  });
}

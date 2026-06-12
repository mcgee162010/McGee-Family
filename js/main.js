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

  // ── LIGHTBOX ─────────────────────────────────────────────
  const lightbox = document.getElementById('lightbox');
  const lbImg    = document.getElementById('lightbox-img');
  const lbClose  = document.getElementById('lightbox-close');

  if (lightbox && lbImg) {

    const openLightbox = (src, alt) => {
      lbImg.src = src;
      lbImg.alt = alt || '';
      lightbox.classList.add('open');
      document.body.style.overflow = 'hidden';
      lbClose && lbClose.focus();
    };

    const closeLightbox = () => {
      lightbox.classList.remove('open');
      document.body.style.overflow = '';
      setTimeout(() => {
        if (!lightbox.classList.contains('open')) { lbImg.src = ''; }
      }, 250);
    };

    // Attach to ALL content images — photo-grid, masonry, member cards,
    // wedding strip, pet cards, bentley grid, baby card, tribute strip, etc.
    const LIGHTBOX_SELECTOR =
      '.photo-grid img, .masonry img, .bentley-grid img, ' +
      '.member-photo, .wedding-photo, .pet-grid img, ' +
      '.baby-card img, .bentley-strip img, [style*="cursor:zoom-in"]';

    const attachLightbox = () => {
      document.querySelectorAll(LIGHTBOX_SELECTOR).forEach(img => {
        if (!img.dataset.lbBound) {
          img.dataset.lbBound = '1';
          img.style.cursor = 'zoom-in';
          img.addEventListener('click', () => openLightbox(img.src, img.alt));
        }
      });
    };

    attachLightbox();

    // Re-attach after gallery tab switches
    document.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => { setTimeout(attachLightbox, 50); });
    });

    // ── FOCUS TRAP ────────────────────────────────────────────
    lightbox.addEventListener('keydown', e => {
      if (!lightbox.classList.contains('open')) return;
      if (e.key !== 'Tab') return;
      const focusable = [...lightbox.querySelectorAll('button, img[tabindex="0"]')];
      const first = focusable[0]; const last = focusable[focusable.length - 1];
      if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last && last.focus(); } }
      else            { if (document.activeElement === last)  { e.preventDefault(); first && first.focus(); } }
    });

    let _lbTrigger = null;
    document.addEventListener('click', e => {
      if (e.target.matches(LIGHTBOX_SELECTOR)) {
        _lbTrigger = e.target;
      }
    });
    lightbox.addEventListener('transitionend', () => {
      if (!lightbox.classList.contains('open') && _lbTrigger) {
        _lbTrigger.focus(); _lbTrigger = null;
      }
    });
    lbImg.setAttribute('tabindex', '0');

    // Close controls
    if (lbClose) lbClose.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', e => {
      if (e.target === lightbox) closeLightbox();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeLightbox();
    });

    // Arrow key navigation
    let currentSrcs = [];
    let currentIdx  = 0;

    lbImg.addEventListener('click', () => {
      const allImgs = [...document.querySelectorAll(LIGHTBOX_SELECTOR)]
        .filter(img => img.offsetParent !== null);
      currentSrcs = allImgs.map(i => ({ src: i.src, alt: i.alt }));
      currentIdx  = currentSrcs.findIndex(s => s.src === lbImg.src);
      if (currentIdx < currentSrcs.length - 1) {
        currentIdx++;
        lbImg.src = currentSrcs[currentIdx].src;
      }
    });

    document.addEventListener('keydown', e => {
      if (!lightbox.classList.contains('open')) return;
      const allImgs = [...document.querySelectorAll(LIGHTBOX_SELECTOR)]
        .filter(img => img.offsetParent !== null);
      currentSrcs = allImgs.map(i => ({ src: i.src, alt: i.alt }));
      currentIdx  = currentSrcs.findIndex(s => s.src === lbImg.src);
      if (e.key === 'ArrowRight' && currentIdx < currentSrcs.length - 1) {
        currentIdx++; lbImg.src = currentSrcs[currentIdx].src; lbImg.alt = currentSrcs[currentIdx].alt;
      } else if (e.key === 'ArrowLeft' && currentIdx > 0) {
        currentIdx--; lbImg.src = currentSrcs[currentIdx].src; lbImg.alt = currentSrcs[currentIdx].alt;
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

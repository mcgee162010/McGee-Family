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
      links.classList.toggle('open');
      toggle.textContent = links.classList.contains('open') ? '✕' : '☰';
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
    };

    const closeLightbox = () => {
      lightbox.classList.remove('open');
      document.body.style.overflow = '';
      setTimeout(() => { lbImg.src = ''; }, 300);
    };

    // Attach to ALL images — photo-grid, masonry, member-photo, bently-grid, etc.
    const attachLightbox = () => {
      document.querySelectorAll(
        '.photo-grid img, .masonry img, .bently-grid img, .member-photo'
      ).forEach(img => {
        if (!img.dataset.lbBound) {
          img.dataset.lbBound = '1';
          img.style.cursor = 'zoom-in';
          img.addEventListener('click', () => openLightbox(img.src, img.alt));
        }
      });
    };

    // Initial attach
    attachLightbox();

    // Re-attach after gallery tab switches (tabs reveal hidden images)
    document.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => {
        setTimeout(attachLightbox, 50);
      });
    });

    // Close controls
    if (lbClose) lbClose.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', e => {
      if (e.target === lightbox) closeLightbox();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeLightbox();
    });

    // Arrow key / swipe navigation
    let currentSrcs = [];
    let currentIdx  = 0;

    lightbox.addEventListener('click', e => {
      if (e.target !== lightbox && e.target !== lbClose && e.target !== lbImg) return;
    });

    lbImg.addEventListener('click', e => {
      // Clicking the image itself navigates to next
      const allImgs = [...document.querySelectorAll(
        '.masonry img:not([style*="display:none"]), .photo-grid img, .bently-grid img'
      )].filter(img => img.offsetParent !== null); // only visible
      currentSrcs = allImgs.map(i => ({ src: i.src, alt: i.alt }));
      currentIdx  = currentSrcs.findIndex(s => s.src === lbImg.src);
      if (currentIdx < currentSrcs.length - 1) {
        currentIdx++;
        lbImg.src = currentSrcs[currentIdx].src;
      }
    });

    document.addEventListener('keydown', e => {
      if (!lightbox.classList.contains('open')) return;
      const allImgs = [...document.querySelectorAll(
        '.masonry img, .photo-grid img, .bently-grid img'
      )].filter(img => img.offsetParent !== null);
      currentSrcs = allImgs.map(i => ({ src: i.src, alt: i.alt }));
      currentIdx  = currentSrcs.findIndex(s => s.src === lbImg.src);

      if (e.key === 'ArrowRight' && currentIdx < currentSrcs.length - 1) {
        currentIdx++;
        lbImg.src = currentSrcs[currentIdx].src;
        lbImg.alt = currentSrcs[currentIdx].alt;
      } else if (e.key === 'ArrowLeft' && currentIdx > 0) {
        currentIdx--;
        lbImg.src = currentSrcs[currentIdx].src;
        lbImg.alt = currentSrcs[currentIdx].alt;
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

});

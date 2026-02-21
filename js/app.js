
  /* ── THEME TOGGLE ──────────────────────────────────────────────── */
  const html         = document.documentElement;
  const themeToggle  = document.getElementById('themeToggle');
  const toggleTrack  = document.getElementById('toggleTrack');
  const themeLabel   = document.getElementById('themeLabel');

  function setTheme(dark) {
    html.setAttribute('data-theme', dark ? 'dark' : 'light');
    toggleTrack.classList.toggle('active', dark);
    themeLabel.textContent = dark ? 'Ciemny' : 'Jasny';
    localStorage.setItem('san-theme', dark ? 'dark' : 'light');
  }

  // load saved preference
  const saved = localStorage.getItem('san-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(saved ? saved === 'dark' : prefersDark);

  themeToggle.addEventListener('click', () => {
    setTheme(html.getAttribute('data-theme') !== 'dark');
  });
  themeToggle.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      themeToggle.click();
    }
  });

  /* ── DAY FILTER ────────────────────────────────────────────────── */
  const pills    = document.querySelectorAll('.day-pill');
  const sections = document.querySelectorAll('.day-section');

  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const filter = pill.dataset.filter;
      sections.forEach(sec => {
        if (filter === 'all' || sec.dataset.day === filter) {
          sec.classList.remove('hidden');
        } else {
          sec.classList.add('hidden');
        }
      });

      // scroll to section
      if (filter !== 'all') {
        const target = document.getElementById('day-' + filter);
        if (target) {
          setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
        }
      }
    });
  });

  /* ── DATES TOGGLE ──────────────────────────────────────────────── */
  document.querySelectorAll('.dates-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const targetId = toggle.dataset.target;
      const grid     = document.getElementById(targetId);
      const isOpen   = grid.classList.contains('visible');

      grid.classList.toggle('visible', !isOpen);
      toggle.classList.toggle('open', !isOpen);
      toggle.innerHTML = isOpen
        ? `<span class="arrow">›</span> Pokaż terminy (${grid.children.length} zajęć)`
        : `<span class="arrow">›</span> Ukryj terminy`;
    });
  });

  /* ── HIGHLIGHT TODAY'S DATES ───────────────────────────────────── */
  // Current date: 20.02.2026 (Friday, Pi)
  // Mark today in all date grids if "20.02" appears - not in the data,
  // but mark the relevant Friday section as today
  // Today's date as "d.mm" → "20.02" — not in any course dates (semester starts 4.03)
  // So we just highlight today's day section visually — already done via .day-badge-today

  /* ── AUTO-SCROLL TO TODAY ON LOAD ─────────────────────────────── */
  window.addEventListener('load', () => {
    const todaySection = document.getElementById('day-pi');
    if (todaySection) {
      setTimeout(() => {
        todaySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 400);
    }
  });
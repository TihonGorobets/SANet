
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
  const pills    = document.querySelectorAll('.day-pill[data-filter]');
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

  /* ── TODAY DETECTION (runs on every page load, always accurate) ── */
  (function () {
    // getDay(): 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat
    const dayShort   = ['nd', 'pn', 'wt', 'sr', 'czw', 'pi', 'sob'];
    const todayShort = dayShort[new Date().getDay()];

    // Highlight the day pill
    const todayPill = document.querySelector('.day-pill[data-filter="' + todayShort + '"]');
    if (todayPill) todayPill.classList.add('today');

    // Insert "Dzisiaj" badge into the day section header
    const todaySection = document.getElementById('day-' + todayShort);
    if (todaySection) {
      const header = todaySection.querySelector('.day-header');
      if (header && !header.querySelector('.day-badge-today')) {
        const badge = document.createElement('span');
        badge.className = 'day-badge-today';
        badge.textContent = 'Dzisiaj';
        header.appendChild(badge);
      }
      // Auto-scroll to today on load
      setTimeout(() => todaySection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400);
    }
  })();
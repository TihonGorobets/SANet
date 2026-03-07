
  /* ── I18N ──────────────────────────────────────────────────────── */
  const LANGS = {
    pl: {
      'hdr-eyebrow':   'Społeczna Akademia Nauk · Warszawa',
      'hdr-title':     'Zarządzanie II \u2014 Plan Zajęć',
      'hdr-subtitle':  'Grupy: gr1 \u2022 gr2 \u2022 gr3 \u2014 studia stacjonarne \u2022 rok akad. 2025/26',
      'wb-btn':        'Whiteboard',
      'theme-light':   'Jasny',
      'theme-dark':    'Ciemny',
      'stat-entries':  n => `${n} zajęć`,
      'stat-groups':   n => `${n} grup`,
      'stat-semester': 'Sem. letni 2025/26',
      'stat-location': 'Łucka 11, Warszawa',
      'filter-group-label': 'Grupa:',
      'filter-all-groups':  'Wszystkie grupy',
      'filter-day-label':   'Dzień:',
      'filter-all-days':    'Wszystkie',
      'days': { pn:'Poniedziałek', wt:'Wtorek', sr:'Środa', czw:'Czwartek', pi:'Piątek', sob:'Sobota', nd:'Niedziela' },
      'today-badge':   'Dzisiaj',
      'dates-show':    n => `Pokaż terminy (${n} zajęć)`,
      'dates-hide':    'Ukryj terminy',
      'empty-day':     'Brak zajęć w tym dniu',
      'empty-group':   g => `Brak zajęć dla grupy ${g}`,
      'change-badge':  'Zmiana w planie',
      'change-new':    '✨ Nowe zajęcia',
      'change-dates':  'zaktualizowane',
      'change-field-room':       'Sala',
      'change-field-time_start': 'Godzina od',
      'change-field-time_end':   'Godzina do',
      'change-field-class_mode': 'Tryb',
      'change-field-instructor': 'Prowadzący',
      'change-field-dates':      'Terminy',
      'legend-title':  'Legenda typów zajęć',
      'legend-wyk':    'Wykład (wyk)',
      'legend-war':    'Warsztaty (war)',
      'legend-cw':     'Ćwiczenia (cw)',
      'legend-kw':     'Konwersatorium (kw)',
      'legend-lab':    'Laboratorium (lab)',
      'legend-sem':    'Seminarium (sem)',
      'footer-generated':  'Plan wygenerowany:',
      'footer-groups':     'Grupy:',
      'footer-source':     'Źródło:',
      'footer-disclaimer': 'Prosimy o sprawdzanie planu przed zajęciami. Plan oraz sale mogą ulec zmianie.',
    },
    ua: {
      'hdr-eyebrow':   'Суспільна академія наук · Варшава',
      'hdr-title':     'Менеджмент II \u2014 Розклад занять',
      'hdr-subtitle':  'Групи: гр1 \u2022 гр2 \u2022 гр3 \u2014 стаціонар \u2022 навч. рік 2025/26',
      'wb-btn':        'Дошка',
      'theme-light':   'Світла',
      'theme-dark':    'Темна',
      'stat-entries':  n => `${n} занять`,
      'stat-groups':   n => `${n} груп`,
      'stat-semester': 'Літній сем. 2025/26',
      'stat-location': 'Łucka 11, Варшава',
      'filter-group-label': 'Група:',
      'filter-all-groups':  'Усі групи',
      'filter-day-label':   'День:',
      'filter-all-days':    'Усі',
      'days': { pn:'Понеділок', wt:'Вівторок', sr:'Середа', czw:'Четвер', pi:'П\'ятниця', sob:'Субота', nd:'Неділя' },
      'today-badge':   'Сьогодні',
      'dates-show':    n => `Показати терміни (${n} занять)`,
      'dates-hide':    'Сховати терміни',
      'empty-day':     'Немає занять у цей день',
      'empty-group':   g => `Немає занять для групи ${g}`,
      'change-badge':  'Зміна в розкладі',
      'change-new':    '✨ Нове заняття',
      'change-dates':  'оновлено',
      'change-field-room':       'Кімната',
      'change-field-time_start': 'Початок',
      'change-field-time_end':   'Кінець',
      'change-field-class_mode': 'Режим',
      'change-field-instructor': 'Викладач',
      'change-field-dates':      'Терміни',
      'legend-title':  'Легенда типів занять',
      'legend-wyk':    'Лекція (лек)',
      'legend-war':    'Семінар-практ. (сп)',
      'legend-cw':     'Практика (пр)',
      'legend-kw':     'Конверсаторій (кнв)',
      'legend-lab':    'Лабораторія (лаб)',
      'legend-sem':    'Семінар (сем)',
      'footer-generated':  'Розклад оновлено:',
      'footer-groups':     'Групи:',
      'footer-source':     'Джерело:',
      'footer-disclaimer': 'Будь ласка, перевіряйте розклад перед заняттями. Розклад і аудиторії можуть змінюватися.',
    },
    en: {
      'hdr-eyebrow':   'University of Social Sciences · Warsaw',
      'hdr-title':     'Management II \u2014 Schedule',
      'hdr-subtitle':  'Groups: gr1 \u2022 gr2 \u2022 gr3 \u2014 full-time studies \u2022 acad. year 2025/26',
      'wb-btn':        'Whiteboard',
      'theme-light':   'Light',
      'theme-dark':    'Dark',
      'stat-entries':  n => `${n} classes`,
      'stat-groups':   n => `${n} groups`,
      'stat-semester': 'Summer sem. 2025/26',
      'stat-location': 'Łucka 11, Warsaw',
      'filter-group-label': 'Group:',
      'filter-all-groups':  'All groups',
      'filter-day-label':   'Day:',
      'filter-all-days':    'All',
      'days': { pn:'Monday', wt:'Tuesday', sr:'Wednesday', czw:'Thursday', pi:'Friday', sob:'Saturday', nd:'Sunday' },
      'today-badge':   'Today',
      'dates-show':    n => `Show dates (${n} classes)`,
      'dates-hide':    'Hide dates',
      'empty-day':     'No classes today',
      'empty-group':   g => `No classes for group ${g}`,
      'change-badge':  'Schedule change',
      'change-new':    '✨ New class',
      'change-dates':  'updated',
      'change-field-room':       'Room',
      'change-field-time_start': 'Start time',
      'change-field-time_end':   'End time',
      'change-field-class_mode': 'Mode',
      'change-field-instructor': 'Instructor',
      'change-field-dates':      'Dates',
      'legend-title':  'Class type legend',
      'legend-wyk':    'Lecture (lec)',
      'legend-war':    'Workshop (ws)',
      'legend-cw':     'Exercises (ex)',
      'legend-kw':     'Seminar (sem)',
      'legend-lab':    'Laboratory (lab)',
      'legend-sem':    'Seminar (sem)',
      'footer-generated':  'Schedule generated:',
      'footer-groups':     'Groups:',
      'footer-source':     'Source:',
      'footer-disclaimer': 'Please verify the schedule before classes. Timetable and rooms may change.',
    },
  };

  let currentLang = localStorage.getItem('san-lang') || 'pl';

  function t(key, arg) {
    const val = (LANGS[currentLang] || LANGS.pl)[key];
    if (typeof val === 'function') return val(arg);
    return val !== undefined ? val : key;
  }

  function applyLang(code) {
    currentLang = code;
    localStorage.setItem('san-lang', code);

    // Active lang button
    document.querySelectorAll('.lang-btn').forEach(btn =>
      btn.classList.toggle('active', btn.dataset.lang === code)
    );

    // html[lang] attribute
    document.documentElement.lang = code === 'ua' ? 'uk' : code;

    // All static data-i18n elements
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const n   = el.dataset.n;
      el.textContent = n !== undefined ? t(key, n) : t(key);
    });

    // Day filter pills (use data-filter key to pick day name)
    document.querySelectorAll('.day-pill[data-filter]').forEach(pill => {
      const dayKey = pill.dataset.filter;
      pill.textContent = dayKey === 'all'
        ? t('filter-all-days')
        : ((LANGS[currentLang] || LANGS.pl).days[dayKey] || dayKey);
    });

    // Day section headers
    document.querySelectorAll('[data-i18n-day]').forEach(el => {
      const dayKey = el.dataset.i18nDay;
      el.textContent = (LANGS[currentLang] || LANGS.pl).days[dayKey] || el.textContent;
    });

    // Theme label (depends on current theme state)
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.getElementById('themeLabel').textContent = isDark ? t('theme-dark') : t('theme-light');

    // Today badge
    const todayBadge = document.querySelector('.day-badge-today');
    if (todayBadge) todayBadge.textContent = t('today-badge');

    // Dates toggles
    document.querySelectorAll('.dates-toggle').forEach(toggle => {
      const grid   = document.getElementById(toggle.dataset.target);
      const isOpen = grid && grid.classList.contains('visible');
      const n      = grid ? grid.children.length : 0;
      const arrow  = document.createElement('span');
      arrow.className   = 'arrow';
      arrow.textContent = '›';
      toggle.textContent = isOpen ? t('dates-hide') : t('dates-show', n);
      toggle.prepend(arrow);
    });

    // Any visible dynamic empty-group messages
    document.querySelectorAll('.day-empty-group').forEach(el => {
      if (el.style.display === 'none') return;
      const activeBtn = document.querySelector('#groupFilter .day-pill.active');
      const g = activeBtn ? activeBtn.dataset.group : 'all';
      el.textContent = g === 'all' ? t('empty-day') : t('empty-group', g);
    });
  }

  // Expose t() for inline scripts that run after app.js
  window.SAN_I18N = { t };

  /* ── THEME TOGGLE ──────────────────────────────────────────────── */
  const html         = document.documentElement;
  const themeToggle  = document.getElementById('themeToggle');
  const toggleTrack  = document.getElementById('toggleTrack');
  const themeLabel   = document.getElementById('themeLabel');

  function setTheme(dark) {
    html.setAttribute('data-theme', dark ? 'dark' : 'light');
    toggleTrack.classList.toggle('active', dark);
    themeLabel.textContent = dark ? t('theme-dark') : t('theme-light');
    localStorage.setItem('san-theme', dark ? 'dark' : 'light');
  }

  // Load saved theme preference
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

  /* ── LANGUAGE SWITCHER ─────────────────────────────────────────── */
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => applyLang(btn.dataset.lang));
  });

  // Apply saved language on load (after DOM + app.js are ready)
  applyLang(currentLang);

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
      const arrow = document.createElement('span');
      arrow.className = 'arrow';
      arrow.textContent = '›';
      toggle.textContent = isOpen
        ? t('dates-show', grid.children.length)
        : t('dates-hide');
      toggle.prepend(arrow);
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

    // Insert today badge into the day section header
    const todaySection = document.getElementById('day-' + todayShort);
    if (todaySection) {
      const header = todaySection.querySelector('.day-header');
      if (header && !header.querySelector('.day-badge-today')) {
        const badge = document.createElement('span');
        badge.className = 'day-badge-today';
        badge.textContent = t('today-badge');
        header.appendChild(badge);
      }
      // Auto-scroll to today on load
      setTimeout(() => todaySection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400);
    }
  })();
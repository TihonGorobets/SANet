"""
generator.py
Reads schedule data from the database and writes a fully self-contained
``zarzadzanie.html`` file that reuses the existing CSS/JS assets.

The generated page mirrors the structure of ``schedule.html`` so that
the same ``css/styles.css`` and ``js/app.js`` apply without modification.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import DAY_MAP, OUTPUT_HTML, TARGET_GROUPS
from .database import fetch_all

logger = logging.getLogger(__name__)

# Ordered list of Polish day names for consistent rendering
_DAY_ORDER = [
    "Poniedziałek", "Wtorek", "Środa",
    "Czwartek",     "Piątek", "Sobota", "Niedziela",
]

# Badge colour by class type (CSS data-type attribute)
_TYPE_CSS: dict[str, str] = {
    "Wykład":         "wyk",
    "Ćwiczenia":      "cw",
    "Laboratorium":   "lab",
    "Warsztaty":      "war",
    "Konwersatorium": "kw",
    "Seminarium":     "sem",
    "Projekt":        "proj",
    "Lektorat":       "lek",
}

# SVG icons (inline, no external dependency)
_SVG_PERSON = (
    '<svg width="14" height="14" fill="none" viewBox="0 0 24 24" '
    'stroke="currentColor" stroke-width="2">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>'
    "</svg>"
)
_SVG_ROOM = (
    '<svg width="14" height="14" fill="none" viewBox="0 0 24 24" '
    'stroke="currentColor" stroke-width="2">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5'
    "M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
    '"/></svg>'
)
_SVG_GROUP = (
    '<svg width="14" height="14" fill="none" viewBox="0 0 24 24" '
    'stroke="currentColor" stroke-width="2">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857'
    "M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857"
    "m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
    '"/></svg>'
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _duration(start: str, end: str) -> str:
    """Return a human-readable duration, e.g. '90 min'."""
    try:
        fmt  = "%H:%M"
        diff = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
        mins = int(diff.total_seconds() / 60)
        if mins <= 0:
            return ""
        if mins % 45 == 0 and mins >= 90:
            return f"{mins // 45} × 45 min"
        return f"{mins} min"
    except (ValueError, TypeError):
        return ""


def _type_badge_css(class_type: str) -> str:
    return _TYPE_CSS.get(class_type, "wyk")


def _escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# Mode display labels and CSS classes
_MODE_BADGE: dict[str, tuple[str, str]] = {
    "Teams":       ("Teams",       "mode-teams"),
    "w kontakcie": ("w sali",      "mode-sala"),
    "Zdalnie":     ("Zdalnie",     "mode-zdal"),
    "Hybrydowo":   ("Hybrydowo",   "mode-hyb"),
    "Online":      ("Online",      "mode-teams"),
}


def _render_change_details(details_json: str | None) -> str:
    """Render a <ul class="change-details"> from the stored JSON diff, or '' if none."""
    if not details_json:
        return ""
    try:
        changes: list[dict] = json.loads(details_json)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not changes:
        return ""
    items = []
    for ch in changes:
        field = ch.get("field", "")
        label = _escape(str(ch.get("label", field)))
        if field == "new":
            items.append('<li class="change-detail-item change-new">'
                         '<span data-i18n="change-new">✨ Nowe zajęcia</span></li>')
        elif field == "dates":
            items.append(f'<li class="change-detail-item">'
                         f'<span class="change-field" data-i18n="change-field-dates">{label}:</span>'
                         f' <span class="change-indicator" data-i18n="change-dates">zaktualizowane</span></li>')
        else:
            old = _escape(str(ch.get("old", "")))
            new = _escape(str(ch.get("new", "")))
            items.append(f'<li class="change-detail-item">'
                         f'<span class="change-field" data-i18n="change-field-{field}">{label}:</span>'
                         f' <span class="old-val">{old}</span>'
                         f'<span class="change-arrow"> → </span>'
                         f'<span class="new-val">{new}</span></li>')
    if not items:
        return ""
    return '<ul class="change-details">' + "".join(items) + "</ul>"


def _card_html(entry: dict, card_id: str) -> str:
    """Render a single ``<article class="class-card">`` block."""
    ts    = _escape(entry.get("time_start", ""))
    te    = _escape(entry.get("time_end",   ""))
    dur   = _duration(entry.get("time_start", ""), entry.get("time_end", ""))
    subj  = _escape(entry.get("subject",    ""))
    ctype = entry.get("class_type", "")
    css   = _type_badge_css(ctype)
    instr = _escape(entry.get("instructor", ""))
    raw_room = entry.get("room", "")
    group = _escape(entry.get("group_name", ""))
    cmode = entry.get("class_mode", "")
    is_changed = bool(entry.get("is_changed", 0))
    change_details_str: str | None = entry.get("change_details") if is_changed else None

    # Multi-room display
    if raw_room and "," in raw_room:
        room_label  = "Różne sale"
        room_detail = _escape(raw_room)
        room_html   = f' Różne sale <strong title="{room_detail}">{room_detail}</strong>'
    elif raw_room:
        room_label  = _escape(raw_room)
        room_html   = f' Sala <strong>{room_label}</strong>'
    else:
        room_html   = ""

    # Mode badge
    if cmode and cmode in _MODE_BADGE:
        mode_label, mode_cls = _MODE_BADGE[cmode]
        mode_badge_html = f' <span class="mode-badge {mode_cls}">{mode_label}</span>'
    else:
        mode_badge_html = ""

    dates: list = entry.get("dates", [])
    n_dates      = len(dates)
    dates_id     = f"dates-{card_id}"

    date_chips = "".join(
        f'<span class="date-chip">{_escape(d)}</span>' for d in dates
    )

    time_sep_style = ' style="min-height:28px"' if dur and "×" in dur else ""

    if is_changed:
        details_html = _render_change_details(change_details_str)
        change_banner = (
            f'        <div class="change-badge">'
            f'<span class="change-icon">\u26a0</span>'
            f' <span data-i18n="change-badge">Zmiana w planie</span>'
            f'{details_html}</div>'
        )
    else:
        change_banner = ""

    lines = [
        f'      <article class="class-card" data-type="{css}" data-group="{group}">',
        change_banner,
        f'        <div class="card-time">',
        f'          <span class="time-start">{ts}</span>',
        f'          <div class="time-sep"{time_sep_style}></div>',
        f'          <span class="time-end">{te}</span>',
    ]
    if dur:
        lines.append(f'          <span class="time-duration">{dur}</span>')
    lines += [
        f'        </div>',
        f'        <div class="card-content">',
        f'          <div class="card-top">',
        f'            <h3 class="card-subject">{subj}</h3>',
        f'            <div class="badge-group">',
        f'              {("<span class=\"type-badge " + css + "\">" + _escape(ctype) + "</span>") if ctype else ""}',
        f'              {mode_badge_html}',
        f'            </div>',
        f'          </div>',
        f'          <div class="card-meta">',
    ]
    if instr:
        lines.append(
            f'            <span class="meta-item">{_SVG_PERSON}'
            f' <strong>{instr}</strong></span>'
        )
    if room_html:
        lines.append(
            f'            <span class="meta-item">{_SVG_ROOM}{room_html}</span>'
        )
    if group:
        lines.append(
            f'            <span class="meta-item">{_SVG_GROUP}'
            f' <strong>{group}</strong></span>'
        )
    lines += [
        f'          </div>',  # /card-meta
    ]
    if dates:
        lines += [
            f'          <div class="card-dates">',
            f'            <span class="dates-toggle" data-target="{dates_id}">',
            f'              <span class="arrow">›</span> Pokaż terminy ({n_dates} zajęć)',
            f'            </span>',
            f'            <div class="dates-grid" id="{dates_id}">',
            f'              {date_chips}',
            f'            </div>',
            f'          </div>',
        ]
    lines += [
        f'        </div>',  # /card-content
        f'      </article>',
    ]
    return "\n".join(lines)


def _day_section_html(
    day_name: str,
    short: str,
    en_name: str,
    entries: list[dict],
    is_today: bool = False,
) -> str:
    """Render a full ``<section class="day-section">`` for one day."""
    today_badge = '\n      <span class="day-badge-today">Dzisiaj</span>' if is_today else ""
    cards = []

    for idx, entry in enumerate(entries):
        card_id = f"{short}{idx + 1}"
        cards.append(_card_html(entry, card_id))

    if cards:
        inner = '\n    <div class="cards-list">\n' + "\n".join(cards) + "\n    </div>"
    else:
        inner = '\n    <div class="day-empty">Brak zajęć w tym dniu</div>'

    return (
        f'\n  <!-- ── {day_name.upper()} ──────────────────────────────────────── -->\n'
        f'  <section class="day-section" data-day="{short}" id="day-{short}">\n'
        f'    <div class="day-header">\n'
        f'      <span class="day-name" data-i18n-day="{short}">{day_name}</span>\n'
        f'      <span class="day-name-pl">{en_name}</span>{today_badge}\n'
        f'      <div class="day-divider"></div>\n'
        f'    </div>'
        f'{inner}\n'
        f'  </section>'
    )


def _short_group_name(full_name: str) -> str:
    """Extract short display name: 'Zarządzanie II gr1' → 'Gr 1'."""
    m = re.search(r'gr(\d+)$', full_name, re.IGNORECASE)
    if m:
        return f"Gr {m.group(1)}"
    return full_name


def _build_group_tabs(groups: list[str]) -> str:
    """Build group filter pill buttons (short display names)."""
    buttons = ['        <button class="day-pill active" data-group="all" data-i18n="filter-all-groups">Wszystkie grupy</button>']
    for g in groups:
        short = _short_group_name(g)
        buttons.append(f'        <button class="day-pill" data-group="{_escape(g)}">{_escape(short)}</button>')
    return "\n".join(buttons)


# ── public API ─────────────────────────────────────────────────────────────────

def generate_html(
    out_path: Path     = OUTPUT_HTML,
    groups: list[str]  = TARGET_GROUPS,
) -> Path:
    """
    Read schedule data from the database, render an HTML page, and write it to
    *out_path*.  Returns the path of the written file.
    """
    entries = fetch_all()
    logger.info("Generating HTML from %d schedule entries …", len(entries))

    # Group entries by day → list of entries
    day_entries: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        day_entries[e["day"]].append(e)

    # Build day sections (today detection is done client-side in JS)
    sections_html = []
    for day_name in _DAY_ORDER:
        meta    = DAY_MAP.get(day_name, {"short": day_name.lower()[:3], "en": day_name})
        short   = meta["short"]
        en_name = meta["en"]
        sections_html.append(
            _day_section_html(day_name, short, en_name, day_entries[day_name], is_today=False)
        )

    # Day filter pills (no today_cls — JS adds .today dynamically)
    day_pills = []
    for day_name in _DAY_ORDER:
        meta  = DAY_MAP.get(day_name, {"short": day_name[:2].lower()})
        short = meta["short"]
        day_pills.append(f'        <button class="day-pill" data-filter="{short}">{day_name}</button>')

    day_pills_str = (
        '        <button class="day-pill active" data-filter="all" data-i18n="filter-all-days">Wszystkie</button>\n'
        + "\n".join(day_pills)
    )

    now = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    groups_summary = ", ".join(groups) if groups else "Zarządzanie"

    html = f"""<!DOCTYPE html>
<html lang="pl" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 'unsafe-inline';
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    font-src https://fonts.gstatic.com;
    img-src 'self' data:;
    connect-src 'none';
    object-src 'none';
    base-uri 'self';
    form-action 'none';
  " />
  <title>Zarządzanie II — Plan Zajęć</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/styles.css" />
</head>
<body>

<div class="page-wrapper">

  <!-- ── HEADER ───────────────────────────────────────────────────────────── -->
  <header class="site-header">
    <div class="header-brand">
      <span class="header-eyebrow" data-i18n="hdr-eyebrow">Społeczna Akademia Nauk · Warszawa</span>
      <h1 class="header-title" data-i18n="hdr-title">Zarządzanie II — Plan Zajęć</h1>
      <p class="header-subtitle" data-i18n="hdr-subtitle">Grupy: gr1 · gr2 · gr3 — studia stacjonarne · rok akad. 2025/26</p>
    </div>
    <div class="header-actions">
      <div class="lang-switcher" role="group" aria-label="Language">
        <button class="lang-btn active" data-lang="pl">PL</button>
        <button class="lang-btn" data-lang="ua">UA</button>
        <button class="lang-btn" data-lang="en">EN</button>
      </div>
      <button class="wb-open-btn" id="wbOpenBtn" aria-label="Otwórz tablicę" style="display:none">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 20h9M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        <span data-i18n="wb-btn">Whiteboard</span>
      </button>
      <div class="theme-toggle" id="themeToggle" role="button" aria-label="Przełącz tryb ciemny" tabindex="0">
        <span class="theme-toggle-label" id="themeLabel">Jasny</span>
        <div class="toggle-track" id="toggleTrack">
          <div class="toggle-thumb"></div>
        </div>
      </div>
    </div>
  </header>

  <!-- ── STATS BAR ─────────────────────────────────────────────────────────── -->
  <div class="stats-bar">
    <div class="stat-chip"><span class="dot" style="background:#2563EB"></span><span data-i18n="stat-entries" data-n="{len(entries)}">{len(entries)} zajęć</span></div>
    <div class="stat-chip"><span class="dot" style="background:#22C55E"></span><span data-i18n="stat-groups" data-n="{len(groups)}">{len(groups)} grup</span></div>
    <div class="stat-chip"><span class="dot" style="background:#7C3AED"></span><span data-i18n="stat-semester">Sem. letni 2025/26</span></div>
    <div class="stat-chip"><span class="dot" style="background:#F59E0B"></span><span data-i18n="stat-location">Łucka 11, Warszawa</span></div>
  </div>

  <!-- ── FILTERS PANEL ─────────────────────────────────────────────────────── -->
  <div class="filters-panel">

    <!-- Group filter -->
    <div class="filter-row" role="group" aria-label="Filtruj według grupy" id="groupFilter">
      <span class="filter-row-label">
        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        <span data-i18n="filter-group-label">Grupa:</span>
      </span>
      <div class="filter-pills">
{_build_group_tabs(groups)}
      </div>
    </div>

    <div class="filter-divider"></div>

    <!-- Day filter -->
    <div class="filter-row" role="group" aria-label="Filtruj według dnia">
      <span class="filter-row-label">
        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <span data-i18n="filter-day-label">Dzień:</span>
      </span>
      <div class="filter-pills filter-pills-scroll">
{day_pills_str}
      </div>
    </div>

  </div>

  <!-- ═══════════════════════════════════════════════════════════════════════
       SCHEDULE SECTIONS (auto-generated — do not edit manually)
  ════════════════════════════════════════════════════════════════════════ -->
{"".join(sections_html)}

  <!-- ── LEGEND ─────────────────────────────────────────────────────────────── -->
  <div class="legend">
    <span class="legend-title" data-i18n="legend-title">Legenda typów zajęć</span>
    <div class="legend-item"><span class="legend-dot" style="background:#2563EB"></span><span data-i18n="legend-wyk">Wykład (wyk)</span></div>
    <div class="legend-item"><span class="legend-dot" style="background:#2563EB"></span><span data-i18n="legend-war">Warsztaty (war)</span></div>
    <div class="legend-item"><span class="legend-dot" style="background:#059669"></span><span data-i18n="legend-cw">Ćwiczenia (cw)</span></div>
    <div class="legend-item"><span class="legend-dot" style="background:#D97706"></span><span data-i18n="legend-kw">Konwersatorium (kw)</span></div>
    <div class="legend-item"><span class="legend-dot" style="background:#7C3AED"></span><span data-i18n="legend-lab">Laboratorium (lab)</span></div>
    <div class="legend-item"><span class="legend-dot" style="background:#BE185D"></span><span data-i18n="legend-sem">Seminarium (sem)</span></div>
  </div>

  <!-- ── FOOTER ─────────────────────────────────────────────────────────────── -->
  <footer class="site-footer">
    <p><span data-i18n="footer-generated">Plan wygenerowany:</span> <strong>{now}</strong> &bull;
       <span data-i18n="footer-groups">Grupy:</span> <strong>{_escape(groups_summary)}</strong> &bull;
       <span data-i18n="footer-source">Źródło:</span> <a href="https://san.edu.pl/plany-zajec-warszawa/studia-stacjonarne" target="_blank" rel="noopener noreferrer">san.edu.pl</a></p>
    <p style="margin-top:4px" data-i18n="footer-disclaimer">Prosimy o sprawdzanie planu przed zajęciami. Plan oraz sale mogą ulec zmianie.</p>
  </footer>

</div><!-- /page-wrapper -->

<script src="js/app.js"></script>
<script>
  /* ── GROUP FILTER ──────────────────────────────────────────────────────── */
  (function () {{
    const groupBtns  = document.querySelectorAll('#groupFilter .day-pill');
    const cards      = document.querySelectorAll('.class-card');
    const sections   = document.querySelectorAll('.day-section');

    function applyGroupFilter(g) {{
      cards.forEach(card => {{
        const grp = card.dataset.group || '';
        card.style.display = (g === 'all' || grp === g) ? '' : 'none';
      }});

      // Show/hide group-aware empty message per day section
      sections.forEach(section => {{
        const list    = section.querySelector('.cards-list');
        if (!list) return;          // day already has "Brak zajęć w tym dniu"
        let emptyMsg  = section.querySelector('.day-empty-group');
        const visible = [...list.querySelectorAll('.class-card')]
                          .some(c => c.style.display !== 'none');
        if (!visible) {{
          if (!emptyMsg) {{
            emptyMsg = document.createElement('div');
            emptyMsg.className = 'day-empty day-empty-group';
            list.after(emptyMsg);
          }}
          emptyMsg.textContent = g === 'all'
            ? window.SAN_I18N.t('empty-day')
            : window.SAN_I18N.t('empty-group', g);
          emptyMsg.style.display = '';
          list.style.display = 'none';
        }} else {{
          if (emptyMsg) emptyMsg.style.display = 'none';
          list.style.display = '';
        }}
      }});
    }}

    groupBtns.forEach(btn => {{
      btn.addEventListener('click', () => {{
        groupBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        applyGroupFilter(btn.dataset.group);
      }});
    }});
  }})();
</script>

<!-- Whiteboard overlay (shared with schedule.html) -->
<!-- <script src="js/whiteboard.js"></script> -->
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    logger.info("HTML written to %s", out_path)
    return out_path

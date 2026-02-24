"""
parser.py
Extracts schedule entries for the configured Zarządzanie groups from a SAN PDF.

Real PDF structure (confirmed by inspection of dzienne2xx.pdf files):
--------------------------------------------------------------------
• One page = one study group.
• The group name is the FIRST LINE of page.extract_text().
• Each page contains exactly one table with this layout:

    Row 0  │ University header (spans all cols)
    Row 1  │ (empty) │ slot-1 │ slot-2 │ … │ slot-7    ← time headers
    Row n  │ Day-abbr│ class  │ class  │ …             ← day rows
    Row n+1│ (empty) │ class  │ …                      ← extra row for same day

  Columns 1–7 map to time slots:
    1 → 08:00–09:30   2 → 09:45–11:15   3 → 11:30–13:00
    4 → 13:15–14:45   5 → 15:00–16:30   6 → 16:45–18:15
    7 → 18:30–20:00

• A class cell contains (newline-separated, two formats):

  FORMAT A — classroom ("w kontakcie"):
      Instructor, Name
      Subject ćw_w
      kontakcie (date1,date2,…)
      room

  FORMAT B — remote / hybrid ("teams", etc.):
      Instructor, Name
      Subject
      w(Ł+W)_teams (date1,date2,…)
      [no room – online]

  FORMAT C — no dates (PE, language courses):
      Instructor-Surname, Name
      Subject
      room(s)   OR   room1,room2,…

  The type abbreviations encode class type:
      ćw / cw  → Ćwiczenia        war → Warsztaty       lab → Laboratorium
      wyk / w  → Wykład (w also appears in w(Ł+W)_teams)
      kw       → Konwersatorium   sem → Seminarium

  The optional "(Ł+W)" parenthetical in w(Ł+W)_teams means the lecture
  is broadcast jointly to Łódź and Warszawa campuses.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from .config import TARGET_GROUPS

logger = logging.getLogger(__name__)

# ── static tables ──────────────────────────────────────────────────────────────

# Column index → (time_start, time_end)
_SLOT_TIMES: dict[int, tuple[str, str]] = {
    1: ("08:00", "09:30"),
    2: ("09:45", "11:15"),
    3: ("11:30", "13:00"),
    4: ("13:15", "14:45"),
    5: ("15:00", "16:30"),
    6: ("16:45", "18:15"),
    7: ("18:30", "20:00"),
}

# Short day names (col-0 of table) → full Polish names
_DAY_SHORT: dict[str, str] = {
    "pn":  "Poniedziałek",
    "wt":  "Wtorek",
    "śr":  "Środa",
    "czw": "Czwartek",
    "pt":  "Piątek",
    "pi":  "Piątek",
    "sob": "Sobota",
    "sb":  "Sobota",
    "nd":  "Niedziela",
    "ndz": "Niedziela",
}

# Class type abbrev (incl. bare "w" for Wykład) → full Polish name
_TYPE_FULL: dict[str, str] = {
    "w":    "Wykład",
    "wyk":  "Wykład",
    "war":  "Warsztaty",
    "cw":   "Ćwiczenia",
    "ćw":   "Ćwiczenia",
    "lab":  "Laboratorium",
    "kw":   "Konwersatorium",
    "sem":  "Seminarium",
    "proj": "Projekt",
    "lek":  "Lektorat",
}

# ── compiled regex patterns ────────────────────────────────────────────────────

# Matches the type token including optional campus tag: ćw_  war_  w(Ł+W)_  w_
# The campus tag like (Ł+W) is captured in group 2 (optional).
_TYPE_RE = re.compile(
    r"\b(ćw|cw|war|lab|wyk|kw|sem|proj|lek|w)(?:\([^)]*\))?_",
    re.IGNORECASE,
)

# Date tokens: "4.03", "11.03", "26.05", "4.03.2026"
_DATE_RE = re.compile(r"\b(\d{1,2}\.\d{2}(?:\.\d{2,4})?)\b")

# Instructor: "Lastname[-Hyphen], Firstname [Initial.]"
# Handles:  Skibińska, Małgorzata  |  Wierniuk-Osińska, Kamila  |  Perlińska, M.
_INSTR_RE = re.compile(
    r"[A-ZŁŚŻŹĆŃÓĄĘ][a-złśżźćńóąę]+"          # Lastname
    r"(?:-[A-ZŁŚŻŹĆŃÓĄĘ][a-złśżźćńóąę]+)?"     # optional -HyphenPart
    r",\s*"                                      # comma + space
    r"[A-ZŁŚŻŹĆŃÓĄĘ][a-złśżźćńóąę]*\.?"         # Firstname or Initial
)

# Slash-separated uppercase initials block: "ME / ŚJ / DK / KS"
_INITIALS_RE = re.compile(
    r"(?:[A-ZŁŚŻŹĆŃÓĄĘ]{1,3}\s*/\s*){1,}[A-ZŁŚŻŹĆŃÓĄĘ]{1,3}"
)

# Mode keywords (after the type underscore token)
_MODE_AFTER: dict[str, str] = {
    "kontakcie":   "w kontakcie",
    "w kontakcie": "w kontakcie",
    "teams":       "Teams",
    "zdalnie":     "Zdalnie",
    "hybrydowo":   "Hybrydowo",
    "online":      "Online",
}


# ── cell parser ────────────────────────────────────────────────────────────────

def _parse_cell(cell_text: str) -> dict | None:
    """
    Parse one PDF table cell into a schedule entry dict.

    Returns None for empty/unparseable cells.

    Keys returned:
        subject, class_type, class_mode, instructor, room, dates (JSON list)
    """
    raw = cell_text.strip()
    if not raw:
        return None

    # Flatten multi-line cell into a single string for uniform regex application.
    flat = " ".join(line.strip() for line in raw.splitlines() if line.strip())

    # ── step 1: extract dates ────────────────────────────────────────────────
    # Iterate all (…) groups and pick the FIRST one that contains date tokens.
    # This correctly skips "(Ł+W)" style campus tags which have no dates.
    dates: list[str] = []
    dates_span: tuple[int, int] | None = None
    for m in re.finditer(r"\([^)]+\)", flat):
        found = _DATE_RE.findall(m.group())
        if found:
            dates = found
            dates_span = (m.start(), m.end())
            break

    # Remove ALL (…) groups from the working copy (campus tags, date blocks, etc.)
    work = re.sub(r"\([^)]+\)", "", flat).strip()

    # ── step 2: class type & mode ────────────────────────────────────────────
    class_type = ""
    class_mode = ""
    type_m = _TYPE_RE.search(work)
    if type_m:
        abbrev     = type_m.group(1).lower()
        class_type = _TYPE_FULL.get(abbrev, abbrev.capitalize())

        # The token ends at type_m.end(); scan what follows for the mode word.
        after_token = work[type_m.end():].lstrip()
        for kw, label in _MODE_AFTER.items():
            if after_token.lower().startswith(kw):
                class_mode = label
                # Remove the mode word from `after_token`
                after_token = after_token[len(kw):].lstrip(",. ")
                break
        else:
            # "teams" sometimes appears after a space in the mode word
            for kw, label in _MODE_AFTER.items():
                if kw in after_token.lower()[:20]:
                    class_mode = label
                    after_token = re.sub(re.escape(kw), "", after_token, count=1, flags=re.IGNORECASE).strip()
                    break

        # Rebuild work: text before the type token + text after type+mode
        work = (work[: type_m.start()] + " " + after_token).strip()

    work = re.sub(r"\s+", " ", work).strip()

    # ── step 3: instructor ───────────────────────────────────────────────────
    instr_m    = _INSTR_RE.search(flat)
    instructor = instr_m.group(0).strip(" ,.") if instr_m else ""
    if instructor:
        work = work.replace(instructor, "").strip(" ,")

    # ── step 4: room(s) ──────────────────────────────────────────────────────
    # Room numbers are 3–4 digits in range 100–1200.
    # Language courses list several rooms: "511,513,515,520" → store all.
    room_nums = [r for r in re.findall(r"\b(\d{3,4})\b", work) if 100 <= int(r) <= 1200]
    if room_nums:
        room = ",".join(dict.fromkeys(room_nums[:4]))  # deduplicate, preserve order
        for r in room_nums[:4]:
            work = re.sub(r"(?<!\d)" + re.escape(r) + r"(?!\d)", "", work)
    else:
        room = ""

    # ── step 5: clean initials blocks & leftover punctuation ────────────────
    work = _INITIALS_RE.sub("", work)
    work = re.sub(r"\s+", " ", work).strip(" ,/-.·•")

    # ── step 6: subject ───────────────────────────────────────────────────────
    subject = work
    if not subject:
        return None

    return {
        "subject":    subject,
        "class_type": class_type,
        "class_mode": class_mode,
        "instructor": instructor,
        "room":       room,
        "dates":      json.dumps(dates, ensure_ascii=False),
    }


# ── group matching ─────────────────────────────────────────────────────────────

def _match_group(page_group: str, target_groups: list[str]) -> str | None:
    """Return the first matching group from *target_groups* or None."""
    pg_lower = page_group.strip().lower()
    for g in target_groups:
        if g.lower() in pg_lower or pg_lower in g.lower():
            return g
    return None


# ── grid table processor ───────────────────────────────────────────────────────

def _process_grid_page(
    table: list[list[Any]],
    group_name: str,
    page_num: int,
) -> list[dict]:
    """
    Process one page's day × time-slot grid table.

    Table layout (0-indexed rows):
        0  = institution header   (skip)
        1  = time slot headers    (skip)
        2+ = day data rows
    """
    entries: list[dict] = []
    if not table or len(table) < 3:
        return entries

    current_day = ""
    last_cell_per_col: dict[int, str] = {}   # span-deduplication tracker

    for ri, row in enumerate(table):
        if ri < 2:
            continue

        day_abbr = str(row[0] or "").strip().lower()
        if day_abbr:
            current_day = _DAY_SHORT.get(day_abbr, day_abbr.capitalize())
            last_cell_per_col = {}

        if not current_day:
            continue

        for col_idx in range(1, 8):
            try:
                raw = str(row[col_idx] or "").strip()
            except IndexError:
                break

            if not raw:
                last_cell_per_col.pop(col_idx, None)
                continue

            # Skip duplicate (same cell spanning multiple consecutive columns)
            if last_cell_per_col.get(col_idx) == raw:
                continue
            last_cell_per_col[col_idx] = raw

            parsed = _parse_cell(raw)
            if parsed is None:
                continue

            # Base time range for this slot
            ts, te = _SLOT_TIMES.get(col_idx, ("", ""))

            # Check if the same content continues in the next column(s) → extend
            next_col = col_idx + 1
            while next_col <= 7:
                try:
                    nxt = str(row[next_col] or "").strip()
                except IndexError:
                    break
                if nxt == raw:
                    _, te = _SLOT_TIMES.get(next_col, (ts, te))
                    last_cell_per_col[next_col] = raw
                    next_col += 1
                else:
                    break

            entry = {
                "group_name": group_name,
                "day":        current_day,
                "time_start": ts,
                "time_end":   te,
                **parsed,
            }
            entries.append(entry)
            logger.debug(
                "  %s | %s | %s | %s–%s | type=%s mode=%s room=%s dates=%d",
                group_name, parsed["subject"], current_day, ts, te,
                parsed["class_type"], parsed["class_mode"],
                parsed["room"], len(json.loads(parsed["dates"])),
            )

    return entries


# ── public API ─────────────────────────────────────────────────────────────────

def parse_pdf(pdf_path: Path, groups: list[str] = TARGET_GROUPS) -> list[dict]:
    """
    Parse *pdf_path* and return schedule entry dicts for every page whose
    group name matches one of *groups*.
    """
    entries: list[dict] = []
    logger.info("Parsing PDF: %s", pdf_path)
    logger.info("Target groups: %s", groups)

    with pdfplumber.open(pdf_path) as pdf:
        logger.info("PDF has %d page(s).", len(pdf.pages))

        for page_num, page in enumerate(pdf.pages, 1):
            page_text  = page.extract_text() or ""
            first_line = page_text.strip().splitlines()[0].strip() if page_text.strip() else ""
            logger.debug("Page %d – first line: %r", page_num, first_line)

            matched_group = _match_group(first_line, groups)
            if matched_group is None:
                continue

            logger.info("Page %d – processing group: %r", page_num, matched_group)

            tables = page.extract_tables()
            if tables:
                for table in tables:
                    page_entries = _process_grid_page(table, matched_group, page_num)
                    entries.extend(page_entries)
                    logger.info("  → %d entr%s.", len(page_entries), "y" if len(page_entries) == 1 else "ies")
            else:
                logger.warning("Page %d – no tables found.", page_num)

    logger.info("Extraction complete – %d total entries.", len(entries))
    return entries


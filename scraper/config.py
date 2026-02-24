"""
config.py
Central configuration for the SAN schedule automation system.
All tunable parameters are defined here – no magic strings in other modules.
"""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
DATA_DIR      = BASE_DIR / "data"
PDF_DIR       = DATA_DIR / "pdfs"
DB_PATH       = DATA_DIR / "schedule.db"
HASH_FILE     = DATA_DIR / "last_hash.txt"
LOG_DIR       = BASE_DIR / "logs"
OUTPUT_HTML   = BASE_DIR / "index.html"

# ── Source ───────────────────────────────────────────────────────────────────
# The page that lists all timetable PDFs
SOURCE_PAGE_URL = "https://san.edu.pl/plany-zajec-warszawa/studia-stacjonarne"

# Keyword (case‑insensitive, Unicode‑normalised) used to identify the
# correct PDF link on the schedule page.
PDF_KEYWORD = "zarządzanie"

# ── Target groups ────────────────────────────────────────────────────────────
# The exact group identifiers as they appear in the PDF.
# Adjust these to match what you see when you open dzienne217.pdf.
# Typical SAN naming pattern:  "ZAR_1", "ZAR gr.1", "Zarządzanie I", etc.
TARGET_GROUPS: list[str] = [
    "Zarządzanie II gr1",
    "Zarządzanie II gr2",
    "Zarządzanie II gr3",
]

# Day‑of‑week mapping used by the HTML generator
DAY_MAP: dict[str, dict] = {
    "Poniedziałek": {"short": "pn",  "en": "Monday"},
    "Wtorek":       {"short": "wt",  "en": "Tuesday"},
    "Środa":        {"short": "sr",  "en": "Wednesday"},
    "Czwartek":     {"short": "czw", "en": "Thursday"},
    "Piątek":       {"short": "pi",  "en": "Friday"},
    "Sobota":       {"short": "sob", "en": "Saturday"},
    "Niedziela":    {"short": "nd",  "en": "Sunday"},
}

# ── HTTP ─────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT   = 30        # seconds
REQUEST_HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
}
MAX_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_BASE   = 2      # seconds – doubles on each retry

# ── Hashing ──────────────────────────────────────────────────────────────────
HASH_ALGORITHM = "sha256"     # any algorithm accepted by hashlib

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE        = LOG_DIR / "schedule_update.log"
LOG_MAX_BYTES   = 5 * 1024 * 1024   # 5 MB
LOG_BACKUP_COUNT = 3

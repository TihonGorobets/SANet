"""
main.py — CLI entry point & orchestrator.

Workflow
--------
1. Download the schedule page and find the Zarządzanie PDF link.
2. Download the PDF to data/pdfs/.
3. Compare the SHA-256 hash of the new PDF with the stored hash.
4. If CHANGED (or first run):
       a. Clear stale rows from the database.
       b. Parse the PDF and insert fresh entries.
       c. Regenerate zarzadzanie.html from the database.
       d. Log a summary.
5. If UNCHANGED: log and exit cleanly.

Run from the repository root:
    python -m scraper.main
Or directly:
    python scraper/main.py
"""

import argparse
import logging
import sys
from datetime import datetime

from .config import TARGET_GROUPS
from .database import clear_schedule, fetch_fingerprints, init_db, insert_entries, mark_changed_entries, set_meta
from .detector import has_changed
from .fetcher import download_pdf, find_pdf_url
from .generator import generate_html
from .logging_setup import configure_logging
from .parser import parse_pdf


def run(*, force: bool = False, dry_run: bool = False) -> int:
    """
    Execute one full update cycle.

    Parameters
    ----------
    force:
        Skip hash check and always process the PDF.
    dry_run:
        Parse and log but do not modify the database or HTML.

    Returns
    -------
    int
        0 on success, 1 on error.
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("SAN schedule updater started at %s", datetime.now().isoformat())
    if dry_run:
        logger.info("DRY-RUN mode – database and HTML will NOT be modified.")

    # ── Step 1: find and download the PDF ────────────────────────────────────
    try:
        pdf_url  = find_pdf_url()
        pdf_path = download_pdf(pdf_url)
    except Exception as exc:
        logger.error("Failed to acquire PDF: %s", exc, exc_info=True)
        return 1

    # ── Step 2: change detection ──────────────────────────────────────────────
    changed = force or has_changed(pdf_path)

    if not changed:
        logger.info("No changes detected – nothing to do.")
        return 0

    # ── Step 3: parse ─────────────────────────────────────────────────────────
    try:
        entries = parse_pdf(pdf_path, groups=TARGET_GROUPS)
    except Exception as exc:
        logger.error("PDF parsing failed: %s", exc, exc_info=True)
        return 1

    if not entries:
        logger.warning(
            "Parser returned 0 entries for groups %s. "
            "The PDF format may have changed – manual review required.",
            TARGET_GROUPS,
        )
        # Still return 0 (not a crash), but skip DB/HTML update to avoid wiping data
        return 0

    logger.info("Parsed %d schedule entr%s.", len(entries), "y" if len(entries) == 1 else "ies")

    if dry_run:
        for e in entries:
            logger.info(
                "  [DRY-RUN] %s | %s | %s | %s–%s | %s",
                e["group_name"], e["subject"], e["day"],
                e["time_start"], e["time_end"], e["room"],
            )
        return 0

    # ── Step 4: update database ───────────────────────────────────────────────
    try:
        init_db()
        prev_fingerprints = fetch_fingerprints()
        cleared  = clear_schedule()
        inserted = insert_entries(entries)
        n_changed = mark_changed_entries(prev_fingerprints)
        set_meta("last_update", datetime.now().isoformat())
        set_meta("source_pdf",  str(pdf_path.name))
        logger.info("Database updated: removed %d old rows, inserted %d new rows, %d changed.",
                    cleared, inserted, n_changed)
    except Exception as exc:
        logger.error("Database update failed: %s", exc, exc_info=True)
        return 1

    # ── Step 5: regenerate HTML ───────────────────────────────────────────────
    try:
        out = generate_html()
        logger.info("Schedule page regenerated: %s", out)
    except Exception as exc:
        logger.error("HTML generation failed: %s", exc, exc_info=True)
        return 1

    logger.info("Update complete.")
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SAN schedule updater – fetch, parse and publish the Zarządzanie timetable."
    )
    p.add_argument(
        "--force", action="store_true",
        help="Ignore stored hash and process the PDF regardless of changes.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Parse and log entries but do not persist anything.",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    configure_logging(args.log_level)
    sys.exit(run(force=args.force, dry_run=args.dry_run))

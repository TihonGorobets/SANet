"""
fetcher.py
Responsible for:
  1. Scraping the schedule page and finding the correct PDF URL.
  2. Downloading the PDF with retry logic.
"""

import logging
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .config import (
    MAX_DOWNLOAD_RETRIES,
    PDF_DIR,
    PDF_KEYWORD,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_BASE,
    SOURCE_PAGE_URL,
)

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower‑case and strip the text for case‑insensitive comparison."""
    return text.strip().lower()


def _resolve_url(href: str, base: str) -> str:
    """Turn a possibly relative href into an absolute URL."""
    return urllib.parse.urljoin(base, href)


# ── public API ────────────────────────────────────────────────────────────────

def find_pdf_url(page_url: str = SOURCE_PAGE_URL, keyword: str = PDF_KEYWORD) -> str:
    """
    Fetch *page_url*, parse all ``<a>`` tags and return the absolute URL of
    the first PDF link whose **text or href** contains *keyword*.

    Raises
    ------
    ValueError
        When no matching link is found.
    requests.RequestException
        On HTTP / network errors.
    """
    logger.info("Fetching schedule page: %s", page_url)
    resp = requests.get(page_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    kw   = _normalise(keyword)

    for tag in soup.find_all("a", href=True):
        href = str(tag["href"])
        # Only consider actual PDF download links
        if not href.lower().endswith(".pdf"):
            continue
        text = tag.get_text(separator=" ")
        if kw in _normalise(text) or kw in _normalise(href):
            pdf_url = _resolve_url(href, page_url)
            logger.info("Found matching PDF link: %s  (text: %r)", pdf_url, text.strip())
            return pdf_url

    raise ValueError(
        f"No PDF link containing '{keyword}' found on {page_url}. "
        "The page structure may have changed."
    )


def download_pdf(pdf_url: str, dest_dir: Path = PDF_DIR) -> Path:
    """
    Download the PDF at *pdf_url* to *dest_dir* and return the local path.

    Uses :data:`~config.MAX_DOWNLOAD_RETRIES` retries with exponential back‑off.

    Raises
    ------
    requests.RequestException
        After all retries are exhausted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.urlparse(pdf_url).path).name or "schedule.pdf"
    dest     = dest_dir / filename

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            logger.info("Downloading PDF (attempt %d/%d): %s", attempt, MAX_DOWNLOAD_RETRIES, pdf_url)
            resp = requests.get(
                pdf_url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)

            logger.info("PDF saved to %s", dest)
            return dest

        except requests.RequestException as exc:
            logger.warning("Download attempt %d failed: %s", attempt, exc)
            if attempt < MAX_DOWNLOAD_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.info("Retrying in %s seconds…", wait)
                time.sleep(wait)
            else:
                logger.error("All %d download attempts failed.", MAX_DOWNLOAD_RETRIES)
                raise

    # Unreachable if MAX_DOWNLOAD_RETRIES >= 1, but satisfies the type checker.
    raise RuntimeError("MAX_DOWNLOAD_RETRIES must be at least 1.")

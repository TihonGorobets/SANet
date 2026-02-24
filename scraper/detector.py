"""
detector.py
SHA‑256 based change detection.

The hash of the downloaded PDF binary is stored in a plain‑text file at
:data:`~config.HASH_FILE`.  On each run the new hash is compared with the
stored one; the PDF is considered *changed* only when they differ.
"""

import hashlib
import logging
from pathlib import Path

from .config import HASH_ALGORITHM, HASH_FILE

logger = logging.getLogger(__name__)


def _compute_hash(path: Path, algorithm: str = HASH_ALGORITHM) -> str:
    """Return the hex digest of *path* using *algorithm*."""
    h = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    logger.debug("Hash of %s (%s): %s", path.name, algorithm, digest)
    return digest


def _read_stored_hash(hash_file: Path = HASH_FILE) -> str | None:
    """Return the previously stored hash, or *None* if no record exists."""
    if hash_file.is_file():
        stored = hash_file.read_text().strip()
        logger.debug("Stored hash: %s", stored)
        return stored
    logger.debug("No stored hash found – treating as first run.")
    return None


def _save_hash(digest: str, hash_file: Path = HASH_FILE) -> None:
    """Persist *digest* to *hash_file*."""
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(digest)
    logger.debug("Saved new hash: %s", digest)


def has_changed(pdf_path: Path) -> bool:
    """
    Return ``True`` when the PDF at *pdf_path* differs from the last run,
    and persist the new hash so the next run has it as baseline.

    Side‑effect
    -----------
    Always updates :data:`~config.HASH_FILE` with the current hash.
    """
    new_hash    = _compute_hash(pdf_path)
    stored_hash = _read_stored_hash()

    if stored_hash is None:
        logger.info("First run detected – treating as changed.")
        _save_hash(new_hash)
        return True

    if new_hash != stored_hash:
        logger.info("PDF has changed (old=%s…, new=%s…).", stored_hash[:12], new_hash[:12])
        _save_hash(new_hash)
        return True

    logger.info("PDF is unchanged – skipping update.")
    return False

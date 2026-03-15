"""
notifier.py — Telegram push notifications for schedule changes.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment variables.
If either is absent the notification is silently skipped (safe for local runs).

Usage
-----
Called automatically from main.py when n_changed > 0:

    from .notifier import notify_changes
    notify_changes(changed_entries, pdf_name, site_url)
"""

import json
import logging
import os
import urllib.request
import urllib.parse
import urllib.error
from typing import Any

logger = logging.getLogger(__name__)

SITE_URL = "https://tihongorobets.github.io/SANet/"


def _send(token: str, chat_id: str, text: str, *, parse_mode: str = "HTML") -> None:
    """POST a message to the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                logger.warning("Telegram API returned not-ok: %s", result)
            else:
                logger.info("Telegram notification sent successfully.")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        logger.warning("Telegram HTTP error %s: %s", exc.code, body)
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)


def _format_message(changed_entries: list[dict[str, Any]], pdf_name: str) -> str:
    """Build an HTML-formatted Telegram message from changed DB rows."""
    lines = [
        "📋 <b>Zmiana w planie zajęć!</b>",
        f"Źródło: <code>{pdf_name}</code>",
        "",
    ]

    # Group changes by group_name
    by_group: dict[str, list[dict]] = {}
    for entry in changed_entries:
        g = entry["group_name"]
        by_group.setdefault(g, []).append(entry)

    for group, entries in sorted(by_group.items()):
        lines.append(f"<b>{group}</b>")
        for e in entries:
            subject = e["subject"]
            day = e["day"]
            time_start = e["time_start"]
            time_end = e["time_end"]
            lines.append(f"  • {subject} — {day} {time_start}–{time_end}")

            details = e.get("change_details")
            if details:
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except json.JSONDecodeError:
                        details = []
                for diff in details:
                    field_label = diff.get("label", diff.get("field", ""))
                    old_val = diff.get("old", "")
                    new_val = diff.get("new", "")
                    lines.append(f"    <s>{field_label}: {old_val}</s> → <b>{new_val}</b>")
        lines.append("")

    lines.append(f'🔗 <a href="{SITE_URL}">Otwórz plan</a>')
    return "\n".join(lines)


def notify_changes(
    changed_entries: list[dict[str, Any]],
    pdf_name: str,
) -> None:
    """
    Send a Telegram notification if bot credentials are configured.

    Parameters
    ----------
    changed_entries:
        List of dicts with keys: group_name, subject, day, time_start,
        time_end, change_details (JSON string or list).
    pdf_name:
        Filename of the source PDF (for display in the message).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.debug(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set – skipping notification."
        )
        return

    if not changed_entries:
        logger.debug("No changed entries – skipping notification.")
        return

    message = _format_message(changed_entries, pdf_name)
    logger.info(
        "Sending Telegram notification for %d changed entr%s.",
        len(changed_entries),
        "y" if len(changed_entries) == 1 else "ies",
    )
    _send(token, chat_id, message)

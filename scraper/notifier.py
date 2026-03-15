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
import urllib.error
from typing import Any

logger = logging.getLogger(__name__)

SITE_URL = "https://tihongorobets.github.io/SANet/"

# ── i18n strings for notification messages ─────────────────────────────────────
_STRINGS = {
    "pl": {
        "header":  "📋 <b>Zmiana w planie zajęć!</b>",
        "source":  "Źródło",
        "open":    "Otwórz plan",
    },
    "ua": {
        "header":  "📋 <b>Зміна в розкладі занять!</b>",
        "source":  "Джерело",
        "open":    "Відкрити розклад",
    },
    "en": {
        "header":  "📋 <b>Schedule has changed!</b>",
        "source":  "Source",
        "open":    "Open schedule",
    },
}

_DAY_NAMES = {
    "ua": {
        "Poniedziałek": "Понеділок", "Wtorek": "Вівторок", "Środa": "Середа",
        "Czwartek": "Четвер", "Piątek": "П'ятниця", "Sobota": "Субота", "Niedziela": "Неділя",
    },
    "en": {
        "Poniedziałek": "Monday", "Wtorek": "Tuesday", "Środa": "Wednesday",
        "Czwartek": "Thursday", "Piątek": "Friday", "Sobota": "Saturday", "Niedziela": "Sunday",
    },
}

# Field label translations for change details
_FIELD_LABELS = {
    "ua": {
        "Sala": "Sala", "Godzina od": "Початок", "Godzina do": "Кінець",
        "Tryb": "Режим", "Prowadzący": "Викладач", "Daty": "Дати",
        "room": "Sala", "time_start": "Початок", "time_end": "Кінець",
        "class_mode": "Режим", "instructor": "Викладач", "dates": "Дати",
    },
    "en": {
        "Sala": "Room", "Godzina od": "Start", "Godzina do": "End",
        "Tryb": "Mode", "Prowadzący": "Instructor", "Daty": "Dates",
        "room": "Room", "time_start": "Start", "time_end": "End",
        "class_mode": "Mode", "instructor": "Instructor", "dates": "Dates",
    },
}

_EMPTY_LABEL = {"pl": "brak", "ua": "немає", "en": "none"}


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


def _format_message(changed_entries: list[dict[str, Any]], pdf_name: str, lang: str = "pl") -> str:
    """Build an HTML-formatted Telegram message from changed DB rows."""
    s = _STRINGS.get(lang, _STRINGS["pl"])
    days = _DAY_NAMES.get(lang, {})
    field_labels = _FIELD_LABELS.get(lang, {})
    empty = _EMPTY_LABEL.get(lang, "—")

    lines = [
        s["header"],
        f"{s['source']}: <code>{pdf_name}</code>",
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
            day = days.get(e["day"], e["day"])  # translate day name if available
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
                    raw_label = diff.get("label", diff.get("field", ""))
                    field_label = field_labels.get(raw_label, raw_label)
                    old_val = diff.get("old", "") or empty
                    new_val = diff.get("new", "") or empty
                    lines.append(f"    <s>{field_label}: {old_val}</s> → <b>{new_val}</b>")
        lines.append("")

    lines.append(f'🔗 <a href="{SITE_URL}">{s["open"]}</a>')
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

    # Read language from bot_config.json (set via /language command)
    try:
        from .bot_commands import get_language
        lang = get_language()
    except Exception:
        lang = "pl"

    message = _format_message(changed_entries, pdf_name, lang)
    logger.info(
        "Sending Telegram notification for %d changed entr%s.",
        len(changed_entries),
        "y" if len(changed_entries) == 1 else "ies",
    )
    _send(token, chat_id, message)

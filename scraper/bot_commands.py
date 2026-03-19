"""
bot_commands.py — Telegram bot command handler.

Polls the Telegram Bot API for new commands, processes them, and persists
settings to data/bot_config.json (cached across GitHub Actions runs).

Supported commands
------------------
/language pl|ua|en   — set the notification language
/language            — show current language
/help                — list available commands

Run from the repository root (called by GitHub Actions before the updater):
    python -m scraper.bot_commands
"""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "bot_config.json"

SUPPORTED_LANGS = {"pl", "ua", "en"}

LANG_LABELS = {"pl": "Polski 🇵🇱", "ua": "Українська 🇺🇦", "en": "English 🇬🇧"}

REPLIES = {
    "pl": {
        "lang_set":     "✅ Język powiadomień zmieniony na <b>{lang_label}</b>.",
        "lang_current": "Aktualny język powiadomień: <b>{lang_label}</b>.\nAby zmienić, wyślij /language pl|ua|en",
        "lang_invalid": "❌ Nieznany język. Dostępne opcje: /language pl | ua | en",
        "help":         "📋 <b>Dostępne komendy:</b>\n/language pl|ua|en — zmień język powiadomień\n/language — pokaż aktualny język\n/help — ta wiadomość",
    },
    "ua": {
        "lang_set":     "✅ Мову сповіщень змінено на <b>{lang_label}</b>.",
        "lang_current": "Поточна мова сповіщень: <b>{lang_label}</b>.\nЩоб змінити, надішліть /language pl|ua|en",
        "lang_invalid": "❌ Невідома мова. Доступні варіанти: /language pl | ua | en",
        "help":         "📋 <b>Доступні команди:</b>\n/language pl|ua|en — змінити мову сповіщень\n/language — показати поточну мову\n/help — це повідомлення",
    },
    "en": {
        "lang_set":     "✅ Notification language changed to <b>{lang_label}</b>.",
        "lang_current": "Current notification language: <b>{lang_label}</b>.\nTo change, send /language pl|ua|en",
        "lang_invalid": "❌ Unknown language. Available options: /language pl | ua | en",
        "help":         "📋 <b>Available commands:</b>\n/language pl|ua|en — change notification language\n/language — show current language\n/help — this message",
    },
}


# ── Config persistence ─────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load bot_config.json or return defaults."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"language": "pl", "offset": 0}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def get_language() -> str:
    """Return the currently configured notification language."""
    return load_config().get("language", "pl")


# ── Telegram API helpers ───────────────────────────────────────────────────────

def _api(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        logger.warning("Telegram API %s HTTP %s: %s", method, exc.code, body)
        return {}
    except Exception as exc:
        logger.warning("Telegram API %s failed: %s", method, exc)
        return {}


def _reply(token: str, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _api(token, "sendMessage", payload)
    if result.get("ok"):
        logger.info("Replied to chat %s.", chat_id)
    else:
        logger.warning("Failed to reply to chat %s: %s", chat_id, result)


def _answer_callback(token: str, callback_query_id: str) -> None:
    _api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})


_LANG_KEYBOARD = {
    "inline_keyboard": [[
        {"text": "Polski 🇵🇱",     "callback_data": "lang:pl"},
        {"text": "Українська 🇺🇦", "callback_data": "lang:ua"},
        {"text": "English 🇬🇧",    "callback_data": "lang:en"},
    ]]
}


# ── Command processing ─────────────────────────────────────────────────────────

def _handle_update(token: str, update: dict, config: dict) -> bool:
    """
    Process a single update. Returns True if config was modified.
    """
    # ── Inline keyboard button press ──────────────────────────────────────────
    callback = update.get("callback_query")
    if callback:
        data = callback.get("data", "")
        chat_id = callback["message"]["chat"]["id"]
        _answer_callback(token, callback["id"])

        if data.startswith("lang:"):
            chosen = data[5:]
            if chosen in SUPPORTED_LANGS:
                config["language"] = chosen
                lang = config.get("language", "pl")
                strings = REPLIES[chosen]
                _reply(token, chat_id, strings["lang_set"].format(
                    lang_label=LANG_LABELS[chosen]
                ))
                logger.info("Language changed to '%s' via button by chat %s.", chosen, chat_id)
                return True
        return False

    # ── Text command ──────────────────────────────────────────────────────────
    message = update.get("message") or update.get("channel_post")
    if not message:
        return False

    text: str = (message.get("text") or "").strip()
    chat_id: int = message["chat"]["id"]
    lang = config.get("language", "pl")
    strings = REPLIES.get(lang, REPLIES["pl"])

    if not text.startswith("/"):
        return False

    parts = text.split()
    command = parts[0].split("@")[0].lower()  # strip @botname suffix

    if command == "/language":
        if len(parts) == 1:
            # Show current language + selection buttons
            _reply(token, chat_id,
                   strings["lang_current"].format(lang_label=LANG_LABELS.get(lang, lang)),
                   reply_markup=_LANG_KEYBOARD)
            return False

        chosen = parts[1].lower()
        if chosen not in SUPPORTED_LANGS:
            _reply(token, chat_id, strings["lang_invalid"], reply_markup=_LANG_KEYBOARD)
            return False

        config["language"] = chosen
        new_strings = REPLIES[chosen]
        _reply(token, chat_id, new_strings["lang_set"].format(
            lang_label=LANG_LABELS[chosen]
        ))
        logger.info("Language changed to '%s' by chat %s.", chosen, chat_id)
        return True

    if command == "/help":
        _reply(token, chat_id, strings["help"])
        return False

    return False


def poll_and_process(token: str) -> None:
    """
    Fetch all pending updates, process commands, persist config changes.
    """
    config = load_config()
    offset = config.get("offset", 0)

    result = _api(token, "getUpdates", {
        "offset": offset,
        "timeout": 0,
        "allowed_updates": ["message", "channel_post", "callback_query"],
    })

    if not result.get("ok"):
        logger.warning("getUpdates failed: %s", result)
        return

    updates = result.get("result", [])
    if not updates:
        logger.info("No new Telegram updates.")
        return

    config_changed = False
    for update in updates:
        modified = _handle_update(token, update, config)
        if modified:
            config_changed = True
        # Advance offset past this update
        config["offset"] = update["update_id"] + 1

    save_config(config)
    if config_changed:
        logger.info("Bot config saved: %s", config)
    else:
        logger.info("Processed %d update(s), config unchanged.", len(updates))


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    from .logging_setup import configure_logging
    configure_logging("INFO")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.debug("TELEGRAM_BOT_TOKEN not set – skipping command polling.")
        return
    poll_and_process(token)


if __name__ == "__main__":
    main()

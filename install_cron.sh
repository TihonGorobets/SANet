#!/usr/bin/env bash
# install_cron.sh — registers a daily 06:00 cron job for the schedule updater.
#
# Usage (run once, from the repository root):
#   chmod +x install_cron.sh
#   ./install_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_FILE="${SCRIPT_DIR}/logs/cron.log"

CRON_CMD="cd \"${SCRIPT_DIR}\" && ${PYTHON_BIN} -m scraper.main >> \"${LOG_FILE}\" 2>&1"
CRON_LINE="0 6 * * * ${CRON_CMD}"

# Check if the entry already exists to avoid duplicates
if crontab -l 2>/dev/null | grep -qF "scraper.main"; then
  echo "Cron job already registered — no changes made."
else
  # Append to existing crontab
  (crontab -l 2>/dev/null; echo "${CRON_LINE}") | crontab -
  echo "Cron job installed:"
  echo "  ${CRON_LINE}"
fi

echo ""
echo "Current crontab:"
crontab -l

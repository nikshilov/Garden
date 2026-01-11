#!/usr/bin/env bash
set -euo pipefail

# Uses env vars from .env loaded in the shell (or export manually):
#   EVE_BOT_TOKEN, ADAM_BOT_TOKEN
#   WEBHOOK_BASE_URL (e.g. https://<your>.up.railway.app or https://<ngrok>.io)
#   WEBHOOK_SECRET_EVE, WEBHOOK_SECRET_ADAM
# Optional: ONLY (eve|adam)

ONLY="${ONLY:-}"

register() {
  local name="$1" token="$2" url="$3" secret="$4"
  if [[ -z "$token" ]]; then
    echo "[$name] Skipping: token is empty" >&2
    return 0
  fi
  if [[ -z "$url" ]]; then
    echo "[$name] ERROR: WEBHOOK_BASE_URL is empty" >&2
    return 1
  fi
  if [[ -z "$secret" ]]; then
    echo "[$name] ERROR: secret is empty" >&2
    return 1
  fi

  local api="https://api.telegram.org/bot${token}/setWebhook"
  local hook="${url}/tg/${name}/webhook"
  echo "[$name] Setting webhook -> ${hook}"
  local resp
  resp=$(curl -sS -X POST "$api" \
    -d "url=${hook}" \
    -d "secret_token=${secret}" \
    -d "allowed_updates=message,callback_query" || true)
  if command -v jq >/dev/null 2>&1; then
    echo "$resp" | jq -r '.'
  else
    echo "$resp"
  fi
}

main() {
  : "${WEBHOOK_BASE_URL:?WEBHOOK_BASE_URL is required}"

  if [[ -z "$ONLY" || "$ONLY" == "eve" ]]; then
    register "eve"  "${EVE_BOT_TOKEN:-}"  "$WEBHOOK_BASE_URL"  "${WEBHOOK_SECRET_EVE:-}"
  fi
  if [[ -z "$ONLY" || "$ONLY" == "adam" ]]; then
    register "adam" "${ADAM_BOT_TOKEN:-}" "$WEBHOOK_BASE_URL"  "${WEBHOOK_SECRET_ADAM:-}"
  fi
}

main "$@"

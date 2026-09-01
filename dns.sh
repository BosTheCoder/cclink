#!/usr/bin/env bash
# Point this repo's CNAME hostname at GitHub Pages, on Cloudflare.
#
#   with-secrets ./dns.sh          # apply
#   with-secrets ./dns.sh --check  # print the record, change nothing
#
# demo-tools automates DNS for the `fly` target but not for `pages`, where it
# only prints the record you need. This is that record, applied. Idempotent:
# re-running it on an already-correct record is a no-op.
#
# The record must be DNS-only (grey cloud). Proxying it breaks GitHub's
# certificate issuance, which fails as "http works, https does not".
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?not set — run this under with-secrets}"

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
HOSTNAME="$(tr -d '[:space:]' < "$HERE/CNAME")"
ZONE_NAME="${HOSTNAME#*.}"
SUBDOMAIN="${HOSTNAME%%.*}"
TARGET="$(git -C "$HERE" remote get-url origin | sed -E 's#.*[:/]([^/]+)/[^/]+$#\1#' | tr 'A-Z' 'a-z').github.io"

api() {
  curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
           -H "Content-Type: application/json" "$@"
}

ZONE_ID="$(api "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" | jq -r '.result[0].id // empty')"
[ -n "$ZONE_ID" ] || { echo "dns.sh: no Cloudflare zone for $ZONE_NAME" >&2; exit 1; }

EXISTING="$(api "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$HOSTNAME" \
            | jq -c '.result[0] // empty')"

echo "==> $HOSTNAME  CNAME  $TARGET  (DNS-only)"

if [ "${1:-}" = "--check" ]; then
  if [ -n "$EXISTING" ]; then
    echo "$EXISTING" | jq -r '"    now: \(.type) -> \(.content), proxied=\(.proxied)"'
  else
    echo "    now: no record"
  fi
  exit 0
fi

BODY="$(jq -nc --arg n "$SUBDOMAIN" --arg c "$TARGET" \
        '{type:"CNAME", name:$n, content:$c, proxied:false, ttl:1}')"

if [ -n "$EXISTING" ]; then
  ID="$(echo "$EXISTING" | jq -r .id)"
  if [ "$(echo "$EXISTING" | jq -r '"\(.type)|\(.content)|\(.proxied)"')" = "CNAME|$TARGET|false" ]; then
    echo "    already correct, nothing to do"
    exit 0
  fi
  echo "$EXISTING" | jq -r '"    replacing: \(.type) -> \(.content), proxied=\(.proxied)"'
  RESULT="$(api -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$ID" --data "$BODY")"
else
  RESULT="$(api -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" --data "$BODY")"
fi

echo "$RESULT" | jq -e '.success' >/dev/null \
  || { echo "$RESULT" | jq -r '.errors[]? | "    cloudflare: \(.message)"' >&2; exit 1; }

echo "    done. The Pages certificate can take up to an hour: just status"

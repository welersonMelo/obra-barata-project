#!/bin/sh
set -eu

INTERNAL_CA_CERT="${INTERNAL_CA_CERT:-/etc/cloudflared/internal-certs/internal-ca.crt}"
SYSTEM_CA_DIR="${SYSTEM_CA_DIR:-/usr/local/share/ca-certificates}"
SYSTEM_INTERNAL_CA_CERT="${SYSTEM_INTERNAL_CA_CERT:-$SYSTEM_CA_DIR/obra-barata-internal-ca.crt}"

for _ in $(seq 1 30); do
  if [ -s "$INTERNAL_CA_CERT" ]; then
    break
  fi

  echo "Waiting for internal CA certificate at $INTERNAL_CA_CERT"
  sleep 1
done

if [ -s "$INTERNAL_CA_CERT" ]; then
  cp "$INTERNAL_CA_CERT" "$SYSTEM_INTERNAL_CA_CERT"
  update-ca-certificates
  echo "Installed internal CA certificate for origin TLS verification"
else
  echo "Internal CA certificate was not found at $INTERNAL_CA_CERT"
fi

exec cloudflared "$@"

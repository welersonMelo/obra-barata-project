#!/bin/sh
set -eu

CERT_DIR="${NGINX_INTERNAL_CERT_DIR:-/etc/nginx/certs}"
CA_CERT_FILE="${NGINX_INTERNAL_CA_CERT_FILE:-$CERT_DIR/internal-ca.crt}"
CA_KEY_FILE="${NGINX_INTERNAL_CA_KEY_FILE:-$CERT_DIR/internal-ca.key}"
CERT_FILE="${NGINX_INTERNAL_CERT_FILE:-$CERT_DIR/internal-server.crt}"
KEY_FILE="${NGINX_INTERNAL_CERT_KEY_FILE:-$CERT_DIR/internal-server.key}"
CERT_CN="${NGINX_INTERNAL_CERT_CN:-nginx-proxy}"
CERT_DAYS="${NGINX_INTERNAL_CERT_DAYS:-3650}"
CERT_SAN="${NGINX_INTERNAL_CERT_SAN:-DNS:nginx-proxy,DNS:localhost,IP:127.0.0.1}"

mkdir -p "$CERT_DIR"

if [ -s "$CA_CERT_FILE" ] && [ -s "$CA_KEY_FILE" ] && [ -s "$CERT_FILE" ] && [ -s "$KEY_FILE" ]; then
  if openssl verify -CAfile "$CA_CERT_FILE" "$CERT_FILE" >/dev/null 2>&1; then
    echo "Internal nginx TLS certificate already exists at $CERT_FILE"
    exit 0
  fi

  echo "Existing internal nginx TLS certificate is invalid; regenerating"
fi

echo "Generating internal CA for nginx TLS"

cat > "$CERT_DIR/internal-ca.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
CN = obra-barata-internal-ca

[v3_ca]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
EOF

openssl req \
  -x509 \
  -nodes \
  -newkey rsa:2048 \
  -days "$CERT_DAYS" \
  -keyout "$CA_KEY_FILE" \
  -out "$CA_CERT_FILE" \
  -config "$CERT_DIR/internal-ca.conf"

echo "Generating internal nginx TLS certificate for $CERT_CN"

openssl req \
  -nodes \
  -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_DIR/internal-server.csr" \
  -subj "/CN=$CERT_CN"

cat > "$CERT_DIR/internal-server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$CERT_SAN
EOF

openssl x509 \
  -req \
  -in "$CERT_DIR/internal-server.csr" \
  -CA "$CA_CERT_FILE" \
  -CAkey "$CA_KEY_FILE" \
  -CAcreateserial \
  -days "$CERT_DAYS" \
  -out "$CERT_FILE" \
  -extfile "$CERT_DIR/internal-server.ext"

chmod 600 "$CA_KEY_FILE"
chmod 600 "$KEY_FILE"
chmod 644 "$CA_CERT_FILE"
chmod 644 "$CERT_FILE"

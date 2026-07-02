#!/usr/bin/env sh
set -eu

ENV_FILE=".env.prod"

if [ ! -f "$ENV_FILE" ]; then
  echo "$ENV_FILE file is required"
  exit 1
fi

get_env_value() {
  key="$1"
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE" \
    | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

API_DOMAIN="$(get_env_value API_DOMAIN)"
LETSENCRYPT_EMAIL="$(get_env_value LETSENCRYPT_EMAIL)"

if [ -z "$API_DOMAIN" ]; then
  echo "API_DOMAIN is required in $ENV_FILE"
  exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
  echo "LETSENCRYPT_EMAIL is required in $ENV_FILE"
  exit 1
fi

if ! printf '%s' "$API_DOMAIN" | grep -Eq '^[A-Za-z0-9.-]+$'; then
  echo "API_DOMAIN contains unsupported characters: $API_DOMAIN"
  exit 1
fi

echo "Preparing Let's Encrypt certificate for $API_DOMAIN"

sudo mkdir -p /etc/letsencrypt /var/www/certbot

docker compose -f docker-compose.prod.yml up -d nginx

if [ -f /etc/letsencrypt/live/"$API_DOMAIN"/fullchain.pem ]; then
  echo "Certificate already exists for $API_DOMAIN"
  docker compose -f docker-compose.prod.yml restart nginx
  exit 0
fi

echo "Requesting real certificate from Let's Encrypt"
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$API_DOMAIN"

docker compose -f docker-compose.prod.yml restart nginx

echo "HTTPS certificate is ready for $API_DOMAIN"

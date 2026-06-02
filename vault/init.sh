#!/bin/sh
set -e

if [ ! -f /secrets/credentials.json ]; then
  echo "ERROR: /secrets/credentials.json not found."
  echo "Copy your GCP credentials to secrets/credentials.json"
  exit 1
fi

echo "Loading GCP secrets into Vault..."

vault kv put secret/gcp/config \
  project_id="tp3-gcp-497003" \
  bucket_name="ejercicio-1-grupo-abc" \
  credentials="$(cat /secrets/credentials.json)"

echo "Secrets loaded successfully."

#!/bin/sh
set -e

MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET_NAME="${MINIO_BUCKET_NAME:-local-bucket}"
MINIO_SECURE="${MINIO_SECURE:-false}"

echo "Loading MinIO secrets into Vault..."
vault kv put secret/minio/config \
  endpoint="${MINIO_ENDPOINT}" \
  access_key="${MINIO_ACCESS_KEY}" \
  secret_key="${MINIO_SECRET_KEY}" \
  bucket_name="${MINIO_BUCKET_NAME}" \
  secure="${MINIO_SECURE}"

if [ -f /secrets/credentials.json ]; then
  echo "Loading GCP secrets into Vault..."

  vault kv put secret/gcp/config \
    project_id="${GOOGLE_CLOUD_PROJECT:-tp3-gcp-497003}" \
    bucket_name="${GCS_BUCKET_NAME:-ejercicio-1-grupo-abc}" \
    credentials="$(cat /secrets/credentials.json)"
elif [ "${STORAGE_MODE}" = "CLOUD" ]; then
  echo "ERROR: /secrets/credentials.json not found."
  echo "Copy your GCP credentials to secrets/credentials.json"
  exit 1
else
  echo "GCP credentials not found. MinIO secrets were loaded into Vault."
fi

echo "Secrets loaded successfully."

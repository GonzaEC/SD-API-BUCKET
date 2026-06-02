from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from google.cloud import storage
from google.oauth2 import service_account, credentials as oauth2_credentials
from google.api_core.exceptions import NotFound, Forbidden
from minio import Minio
from minio.error import S3Error
import hvac
import io
import os
import json
import traceback

app = FastAPI(title="Bucket API")

VAULT_ADDR  = os.getenv("VAULT_ADDR",  "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "root-token")
VAULT_GCP_PATH = os.getenv("VAULT_GCP_SECRET_PATH", "gcp/config")
VAULT_MINIO_PATH = os.getenv("VAULT_MINIO_SECRET_PATH", "minio/config")
STORAGE_MODE = os.getenv("STORAGE_MODE", "CLOUD").upper()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__, "trace": traceback.format_exc()},
    )


def get_vault_client() -> hvac.Client:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    if not client.is_authenticated():
        raise HTTPException(status_code=500, detail="Cannot authenticate with Vault")
    return client


def read_secret(path: str) -> dict:
    client = get_vault_client()
    response = client.secrets.kv.v2.read_secret_version(path=path, mount_point="secret")
    return response["data"]["data"]


def get_gcp_secrets() -> dict:
    return read_secret(VAULT_GCP_PATH)


def load_credentials(creds_info: dict):
    if creds_info.get("type") == "service_account":
        return service_account.Credentials.from_service_account_info(creds_info)
    # authorized_user (ADC / gcloud auth application-default login)
    return oauth2_credentials.Credentials(
        token=None,
        refresh_token=creds_info["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_info["client_id"],
        client_secret=creds_info["client_secret"],
    )


def get_gcs_client() -> storage.Client:
    secrets = get_gcp_secrets()
    creds_info = json.loads(secrets["credentials"])
    creds = load_credentials(creds_info)
    return storage.Client(project=secrets["project_id"], credentials=creds)


def get_bucket() -> storage.Bucket:
    secrets = get_gcp_secrets()
    client = get_gcs_client()
    return client.bucket(secrets["bucket_name"])


def get_minio_config() -> dict:
    secrets = read_secret(VAULT_MINIO_PATH)
    return {
        "endpoint": secrets["endpoint"],
        "access_key": secrets["access_key"],
        "secret_key": secrets["secret_key"],
        "bucket_name": secrets["bucket_name"],
        "secure": str(secrets.get("secure", "false")).lower() == "true",
    }


class GCSStorageBackend:
    def upload(self, filename: str, contents: bytes, content_type: str | None) -> dict:
        bucket = get_bucket()
        blob = bucket.blob(filename)

        try:
            blob.upload_from_string(contents, content_type=content_type)
            return {"filename": filename, "bucket": bucket.name}
        except Forbidden:
            raise HTTPException(status_code=403, detail=f"Permission denied on bucket '{bucket.name}'")
        except NotFound:
            raise HTTPException(status_code=404, detail=f"Bucket '{bucket.name}' not found")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    def download(self, filename: str) -> tuple[bytes, str, str]:
        bucket = get_bucket()
        blob = bucket.blob(filename)

        try:
            data = blob.download_as_bytes()
            media_type = blob.content_type or "application/octet-stream"
            return data, media_type, bucket.name
        except NotFound:
            raise HTTPException(status_code=404, detail=f"File '{filename}' not found in bucket '{bucket.name}'")
        except Forbidden:
            raise HTTPException(status_code=403, detail=f"Permission denied on bucket '{bucket.name}'")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    def list_files(self) -> dict:
        secrets = get_gcp_secrets()
        client = get_gcs_client()

        try:
            blobs = client.list_blobs(secrets["bucket_name"])
            return {"files": [blob.name for blob in blobs], "bucket": secrets["bucket_name"], "mode": "CLOUD"}
        except Forbidden:
            raise HTTPException(status_code=403, detail="Permission denied on bucket")
        except NotFound:
            raise HTTPException(status_code=404, detail="Bucket not found")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


class MinIOStorageBackend:
    def __init__(self):
        self.config = get_minio_config()
        self.client = Minio(
            self.config["endpoint"],
            access_key=self.config["access_key"],
            secret_key=self.config["secret_key"],
            secure=self.config["secure"],
        )
        self.bucket_name = self.config["bucket_name"]

    def upload(self, filename: str, contents: bytes, content_type: str | None) -> dict:
        try:
            self.client.put_object(
                self.bucket_name,
                filename,
                data=io.BytesIO(contents),
                length=len(contents),
                content_type=content_type or "application/octet-stream",
            )
            return {"filename": filename, "bucket": self.bucket_name}
        except S3Error as exc:
            status_code = 404 if exc.code == "NoSuchBucket" else 500
            raise HTTPException(status_code=status_code, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    def download(self, filename: str) -> tuple[bytes, str, str]:
        response = None
        try:
            response = self.client.get_object(self.bucket_name, filename)
            stat = self.client.stat_object(self.bucket_name, filename)
            data = response.read()
            media_type = stat.content_type or "application/octet-stream"
            return data, media_type, self.bucket_name
        except S3Error as exc:
            status_code = 404 if exc.code in {"NoSuchKey", "NoSuchBucket"} else 500
            raise HTTPException(status_code=status_code, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            try:
                response.close()
                response.release_conn()
            except Exception:
                pass

    def list_files(self) -> dict:
        try:
            objects = self.client.list_objects(self.bucket_name, recursive=True)
            return {"files": [obj.object_name for obj in objects], "bucket": self.bucket_name, "mode": "LOCAL"}
        except S3Error as exc:
            status_code = 404 if exc.code == "NoSuchBucket" else 500
            raise HTTPException(status_code=status_code, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


def get_storage_backend():
    if STORAGE_MODE == "CLOUD":
        return GCSStorageBackend()
    if STORAGE_MODE == "LOCAL":
        return MinIOStorageBackend()
    raise HTTPException(status_code=500, detail="Invalid STORAGE_MODE. Use CLOUD or LOCAL.")


@app.post("/upload/{filename}")
async def upload_file(filename: str, file: UploadFile = File(...)):
    backend = get_storage_backend()
    contents = await file.read()
    result = backend.upload(filename, contents, file.content_type)
    return {"message": "File uploaded successfully", **result, "mode": STORAGE_MODE}


@app.get("/download/{filename}")
def download_file(filename: str):
    backend = get_storage_backend()
    data, media_type, _ = backend.download(filename)

    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/files")
def list_files():
    backend = get_storage_backend()
    return backend.list_files()

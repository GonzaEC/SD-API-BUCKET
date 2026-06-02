from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from google.cloud import storage
from google.oauth2 import service_account, credentials as oauth2_credentials
from google.api_core.exceptions import NotFound, Forbidden
import hvac
import os
import json
import traceback

app = FastAPI(title="GCS Bucket API")

VAULT_ADDR  = os.getenv("VAULT_ADDR",  "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "root-token")
VAULT_PATH  = os.getenv("VAULT_SECRET_PATH", "gcp/config")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__, "trace": traceback.format_exc()},
    )


def get_gcp_secrets() -> dict:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    if not client.is_authenticated():
        raise HTTPException(status_code=500, detail="Cannot authenticate with Vault")
    response = client.secrets.kv.v2.read_secret_version(path=VAULT_PATH, mount_point="secret")
    return response["data"]["data"]


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


@app.post("/upload/{filename}")
async def upload_file(filename: str, file: UploadFile = File(...)):
    bucket = get_bucket()
    blob = bucket.blob(filename)

    try:
        contents = await file.read()
        blob.upload_from_string(contents, content_type=file.content_type)
    except Forbidden:
        raise HTTPException(status_code=403, detail=f"Permission denied on bucket '{bucket.name}'")
    except NotFound:
        raise HTTPException(status_code=404, detail=f"Bucket '{bucket.name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "File uploaded successfully", "filename": filename, "bucket": bucket.name}


@app.get("/download/{filename}")
def download_file(filename: str):
    bucket = get_bucket()
    blob = bucket.blob(filename)

    try:
        data = blob.download_as_bytes()
    except NotFound:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found in bucket '{bucket.name}'")
    except Forbidden:
        raise HTTPException(status_code=403, detail=f"Permission denied on bucket '{bucket.name}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        iter([data]),
        media_type=blob.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/files")
def list_files():
    secrets = get_gcp_secrets()
    client = get_gcs_client()
    try:
        blobs = client.list_blobs(secrets["bucket_name"])
        return {"files": [blob.name for blob in blobs], "bucket": secrets["bucket_name"]}
    except Forbidden:
        raise HTTPException(status_code=403, detail="Permission denied on bucket")
    except NotFound:
        raise HTTPException(status_code=404, detail="Bucket not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

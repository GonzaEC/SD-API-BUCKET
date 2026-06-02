# SD-API-BUCKET

## Estructura

- `version1/`: variante actual con Docker Compose
- `version2/`: variante Kubernetes con `Deployment`, `Service`, `ConfigMap`, `Secret` y `Job`

La raiz mantiene el trabajo actual para no romper nada de lo que ya estaba armado.

API en FastAPI para subir, listar y descargar archivos usando dos backends de storage:

- `CLOUD`: Google Cloud Storage
- `LOCAL`: MinIO

La configuracion de ambos backends se centraliza en Vault. La app no lee las credenciales de GCP ni la configuracion de MinIO directamente: las obtiene desde secretos cargados en Vault por `vault-init`.

## Arquitectura

Servicios del `docker-compose`:

- `vault`: servidor Vault en modo dev
- `vault-init`: carga secretos en Vault
- `minio`: storage local compatible con S3
- `minio-init`: crea el bucket local si no existe
- `api`: aplicacion FastAPI

Secrets esperados en Vault:

- `secret/gcp/config`
- `secret/minio/config`

## Requisitos

- Docker
- Docker Compose
- Para modo `CLOUD`: archivo `secrets/credentials.json` con credenciales de GCP validas

## Variables de entorno

Archivo base: [.env.example](/E:/Gonza/Programacion/2026/SD-API-BUCKET/.env.example:1)

Variables importantes:

- `STORAGE_MODE=CLOUD` o `LOCAL`
- `VAULT_GCP_SECRET_PATH=gcp/config`
- `VAULT_MINIO_SECRET_PATH=minio/config`
- `GCS_BUCKET_NAME`
- `GOOGLE_CLOUD_PROJECT`

## Como funciona Vault

Al levantar el stack:

1. `minio` inicia el storage local.
2. `minio-init` crea el bucket `local-bucket`.
3. `vault` inicia.
4. `vault-init` carga en Vault:
   - `secret/minio/config` siempre
   - `secret/gcp/config` solo si existe `secrets/credentials.json`
5. `api` arranca y usa `STORAGE_MODE` para elegir el backend.

Si `STORAGE_MODE=CLOUD` y faltan credenciales GCP, `vault-init` falla para evitar un arranque inconsistente.

## Levantar el proyecto

### 1. Configurar entorno

Copiar o editar `.env` y elegir el modo:

```env
STORAGE_MODE=LOCAL
```

o:

```env
STORAGE_MODE=CLOUD
```

Para `CLOUD`, colocar el archivo de credenciales en:

```text
secrets/credentials.json
```

### 2. Construir y levantar

```bash
docker compose up --build
```

La API queda disponible en:

```text
http://localhost:8000
```

MinIO Console:

```text
http://localhost:9001
```

Vault:

```text
http://localhost:8200
```

## Probar todo

### 1. Verificar que la API responda

Abrir:

```text
http://localhost:8000/docs
```

o probar listado:

```bash
curl http://localhost:8000/files
```

### 2. Subir un archivo

Ejemplo con `captura.png`:

En PowerShell, usar `curl.exe` en una sola linea:

```powershell
curl.exe -X POST "http://localhost:8000/upload/captura.png" -F "file=@captura.png"
```

Alternativa nativa con PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/upload/captura.png" -Method Post -Form @{ file = Get-Item .\captura.png }
```

En `cmd`, tambien funciona:

```bat
curl -X POST "http://localhost:8000/upload/captura.png" -F "file=@captura.png"
```

Respuesta esperada:

```json
{
  "message": "File uploaded successfully",
  "filename": "captura.png",
  "bucket": "local-bucket",
  "mode": "LOCAL"
}
```

En modo `CLOUD`, cambian `bucket` y `mode`.

### 3. Listar archivos

PowerShell:

```powershell
curl.exe http://localhost:8000/files
```

o:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/files" -Method Get
```

Respuesta esperada:

```json
{
  "files": ["captura.png"],
  "bucket": "local-bucket",
  "mode": "LOCAL"
}
```

### 4. Descargar un archivo

PowerShell:

```powershell
curl.exe "http://localhost:8000/download/captura.png" --output captura_descargada.png
```

o:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/download/captura.png" -OutFile .\captura_descargada.png
```

Luego comparar que el archivo exista y se haya descargado correctamente.

### 5. Repetir en ambos modos

#### Probar modo `LOCAL`

1. En `.env`, usar:

```env
STORAGE_MODE=LOCAL
```

2. Levantar:

```bash
docker compose up --build
```

3. Probar upload, list y download.

Resultado esperado:

- los archivos se guardan en MinIO
- Vault contiene `secret/minio/config`
- la API responde con `"mode": "LOCAL"`

#### Probar modo `CLOUD`

1. Guardar credenciales en `secrets/credentials.json`
2. En `.env`, usar:

```env
STORAGE_MODE=CLOUD
```

3. Levantar:

```bash
docker compose up --build
```

4. Probar upload, list y download.

Resultado esperado:

- los archivos se guardan en el bucket de GCP
- Vault contiene `secret/gcp/config`
- la API responde con `"mode": "CLOUD"`

## Verificar Vault

Se puede entrar al contenedor y leer los secretos cargados:

```bash
docker exec -it vault sh
```

Dentro del contenedor:

```bash
export VAULT_TOKEN=root-token
export VAULT_ADDR=http://127.0.0.1:8200
vault kv get secret/minio/config
vault kv get secret/gcp/config
```

Que deberias ver:

- en `minio/config`: `endpoint`, `access_key`, `secret_key`, `bucket_name`, `secure`
- en `gcp/config`: `project_id`, `bucket_name`, `credentials`

## Verificar MinIO

Entrar a la consola web:

```text
http://localhost:9001
```

Credenciales por defecto:

```text
usuario: minioadmin
password: minioadmin
```

Bucket esperado:

```text
local-bucket
```

## Detener el proyecto

```bash
docker compose down
```

Si tambien queres borrar volumenes y estado local:

```bash
docker compose down -v
```

## Endpoints

- `POST /upload/{filename}`
- `GET /download/{filename}`
- `GET /files`

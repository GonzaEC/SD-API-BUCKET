# Version 1

Esta carpeta contiene la version basada en Docker Compose del proyecto.

Archivos principales:

- `main.py`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `vault/init.sh`
- `.env.example`

## Levantar

1. Copiar `.env.example` a `.env` si queres manejar variables locales.
2. Si vas a usar `CLOUD`, colocar las credenciales GCP en `../secrets/credentials.json`.
3. Ejecutar:

```bash
docker compose up --build
```

## Modos

- `STORAGE_MODE=LOCAL`: usa MinIO
- `STORAGE_MODE=CLOUD`: usa GCP

En ambos casos la app lee configuracion desde Vault.

## Probar

Upload:

```powershell
curl.exe -X POST "http://localhost:8000/upload/captura.png" -F "file=@..\captura.png"
```

Listar:

```powershell
curl.exe http://localhost:8000/files
```

Descargar:

```powershell
curl.exe "http://localhost:8000/download/captura.png" --output captura_descargada.png
```

## Nota

La documentacion completa original sigue en el README de la raiz:

- [README.md](/E:/Gonza/Programacion/2026/SD-API-BUCKET/README.md)

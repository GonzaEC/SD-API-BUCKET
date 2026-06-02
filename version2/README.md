# Version 2

Esta carpeta contiene una propuesta de migracion a Kubernetes.

Incluye:

- `app/`: misma API FastAPI
- `k8s/`: manifests de Kubernetes

## Objetivo

Reemplazar `docker-compose` por recursos de Kubernetes:

- `Deployment`
- `Service`
- `ConfigMap`
- `Secret`
- `Job`

## Estructura

- `k8s/01-namespace.yaml`
- `k8s/02-configmap.yaml`
- `k8s/03-secrets.example.yaml`
- `k8s/04-vault.yaml`
- `k8s/05-minio.yaml`
- `k8s/06-bootstrap-jobs.yaml`
- `k8s/07-api.yaml`
- `k8s/kustomization.yaml`

## Como aplicar

1. Construir la imagen de la API:

```bash
docker build -t sd-api-bucket:v2 version2/app
```

2. Si usas `kind`, cargar la imagen en el cluster:

```bash
kind load docker-image sd-api-bucket:v2
```

3. Crear un archivo real de secretos a partir de `k8s/03-secrets.example.yaml`.
4. Completar el contenido de `credentials.json` si vas a usar `CLOUD`.
5. Aplicar los manifests:

```bash
kubectl apply -k version2/k8s
```

## Exponer localmente para pruebas

API:

```bash
kubectl port-forward -n sd-api-bucket-v2 svc/api 8000:8000
```

MinIO:

```bash
kubectl port-forward -n sd-api-bucket-v2 svc/minio 9000:9000
kubectl port-forward -n sd-api-bucket-v2 svc/minio-console 9001:9001
```

Vault:

```bash
kubectl port-forward -n sd-api-bucket-v2 svc/vault 8200:8200
```

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

## Importante

Esta `version2` deja armada la migracion a Kubernetes con replicas y `ClusterIP` para API, Vault y MinIO, pero para alta disponibilidad real de Vault y MinIO no alcanza con solo aumentar replicas:

- Vault necesita un backend HA real, por ejemplo Raft integrado con `StatefulSet`
- MinIO necesita modo distribuido y volumenes persistentes consistentes

Por eso esta version sirve como base academica o de migracion inicial. Si despues queres, el siguiente paso natural es hacer una `version2-ha` con `StatefulSet`, `PVC` y configuracion distribuida real.

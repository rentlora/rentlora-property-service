# rentlora-property-service

> Listing catalog service for the Rentlora platform — manages properties, reviews, availability, and image uploads via S3 presigned URLs.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-RDS-336791?logo=postgresql&logoColor=white)
![S3](https://img.shields.io/badge/AWS-S3-FF9900?logo=amazonaws&logoColor=white)
![SQS](https://img.shields.io/badge/AWS-SQS-FF9900?logo=amazonaws&logoColor=white)

---

## Overview

`property-service` is the catalog backbone of Rentlora. It owns every property listing — creation, updates, deletion, filtering, and reviews. Images are handled via an S3 presigned URL flow where the browser uploads directly to S3 (bypassing the pod), keeping pods stateless and images off ephemeral disk. When a property is created, updated, or deleted, the service publishes a `property-sync` event to SQS, which triggers `ai-search-service` to regenerate the property's vector embedding for semantic search — without any direct service-to-service HTTP call.

---

## API Endpoints

### Properties

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/properties` | List properties with filter support (location, price, dates) |
| `POST` | `/api/properties` | Create a new property listing |
| `GET` | `/api/properties/{id}` | Get a single property by ID |
| `PUT` | `/api/properties/{id}` | Update a property (host only) |
| `DELETE` | `/api/properties/{id}` | Delete a property (host only) |
| `GET` | `/api/properties/{id}/availability` | Check availability calendar |

### Reviews

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/reviews/{property_id}` | List reviews for a property |
| `POST` | `/api/reviews/{property_id}` | Submit a review (guests only, post-stay) |

### Image Upload (S3 Presigned Flow)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/properties/{id}/presigned-upload` | Get a presigned S3 PUT URL — browser uploads directly |
| `POST` | `/api/properties/{id}/confirm-upload` | Confirm the upload and store the CDN image URL |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/ready` | Readiness probe — checks DB connectivity |

All write endpoints require a valid JWT, validated locally from the shared signing secret issued by `user-service`.

---

## AWS Resources

| Service | Purpose |
|---|---|
| **RDS (PostgreSQL)** | Source of truth for properties, reviews, and availability |
| **S3** | Property listing images — presigned URL flow; browser PUTs directly to S3 |
| **CloudFront** | CDN for serving S3 images — edge-cached, global, bucket stays private via OAC |
| **SQS — `property-sync`** | Publish property change events; consumed by `ai-search-service` for re-embedding |
| **Secrets Manager** | DB password — fetched at startup via IRSA |
| **SSM Parameter Store** | DB config, S3 bucket name, CloudFront domain, SQS queue URL |
| **CloudWatch** | Custom metrics: image upload count and size |

---

## Image Upload Flow

```
1. Client   ──POST /presigned-upload──▶  property-service
2. property-service  ──▶  S3 (GeneratePresignedUrl)  ──▶  returns {upload_url, key}
3. Client   ──PUT {upload_url}──▶  S3 directly  (no pod involved)
4. Client   ──POST /confirm-upload {key}──▶  property-service
5. property-service  stores CloudFront CDN URL in DB
```

No binary data ever passes through a pod — images go directly browser → S3.

---

## Search Event Flow

```
POST/PUT/DELETE /api/properties/{id}
        │
        ├──▶ Write to PostgreSQL
        └──▶ Publish property-sync event (SQS)
                      │
                      ▼
              ai-search-service (consumer)
                      │
                      ▼
              Generate new embedding (Bedrock Titan)
                      └──▶ Store in pgvector
```

The property-service never calls `ai-search-service` directly — decoupled via SQS.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | PyJWT (HS256) |
| Image Processing | Pillow |
| HTTP Client | httpx |
| AWS SDK | boto3 |
| Logging | python-json-logger (structured JSON) |
| Container | Docker (multi-stage, non-root) |

---

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL (or use the project-level `docker-compose.yml` in the `rentlora` repo)
- (Optional) AWS credentials for S3 image upload and SQS events

### Run Locally

```bash
# From the rentlora repo root (starts all services)
docker-compose up --build property-service

# Or run standalone
cd rentlora-property-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

With `ENV=local` the service skips AWS lookups and uses defaults. S3 and SQS calls are skipped if not configured — basic CRUD works without AWS.

### Alembic Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "add_column_x"
```

---

## Deployment

This service is deployed on **Amazon EKS** as part of the Rentlora platform.

- **Container image**: built by GitHub Actions, scanned by Trivy, pushed to ECR
- **Helm chart**: `rentlora-helm/charts/property-service`
- **GitOps**: Argo CD reconciles chart changes automatically
- **Port**: `8001`
- **Replicas**: 2 minimum (HPA max 6, target 70% CPU)
- **AWS credentials**: IRSA — the pod's ServiceAccount is annotated with the property-service IAM role ARN

---

## Health Probes

| Probe | Path | Notes |
|---|---|---|
| Liveness | `GET /healthz` | Fast, no DB call |
| Readiness | `GET /ready` | Checks DB connectivity; returns HTTP 503 if unreachable |

---

## Project Context

This service is part of the Rentlora microservices platform:

| Repository | Role |
|---|---|
| [`rentlora`](../rentlora) | Application source — all services + frontend |
| [`rentlora-infra`](../rentlora-infra) | Terraform — AWS infrastructure |
| [`rentlora-helm`](../rentlora-helm) | Helm charts + Argo CD GitOps |

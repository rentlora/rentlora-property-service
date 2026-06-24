# property-service

The catalog service — owns properties, reviews, availability, and listing images.

## What it does
- **Property CRUD** — `GET/POST /api/properties`, `GET/PUT/DELETE /api/properties/{id}`
- **Reviews** — list/create reviews for a property
- **Availability** — `GET /api/properties/{id}/availability`
- **Image upload** — presigned S3 flow: `presigned-upload` → browser PUTs to S3 → `confirm-upload`
- **Search filters** — basic keyword/attribute filtering (semantic search lives in ai-search-service)
- Liveness/readiness: `/healthz`, `/ready`

## AWS resources & why

| Resource | Used for | Why / benefit |
|---|---|---|
| **RDS (PostgreSQL)** | properties, reviews, availability tables | Source of truth for the catalog; relational data with joins/filtering. |
| **S3** (`s3:PutObject/GetObject/DeleteObject`) | listing images via **presigned URLs** | Browser uploads straight to S3 — no large files through pods, nothing on ephemeral disk. |
| **CloudFront** (indirect) | serving those images | Edge-cached, low-latency global delivery; keeps the S3 bucket private (OAC). |
| **SQS — `property-sync` (SendMessage)** | publish a "property changed" event on create/update/delete | Decouples search indexing: ai-search-service consumes this and re-embeds the property. Async, resilient. |
| **Secrets Manager** | DB password | No DB creds in code/k8s; rotated centrally. |
| **SSM Parameter Store** | db endpoint/name/user, bucket, CDN domain, queue URL | Non-sensitive config injected per-env via IRSA. |
| **CloudWatch** (custom metrics) | image upload count/size | Operational visibility. |

## Event flow it drives
```
create/update/delete property ──▶ publish property-sync (SQS) ──▶ ai-search re-embeds
```
This is the write side of the search index — property-service never talks to ai-search directly.

## Improvements
- **Read caching** — properties are read-heavy; a short-TTL cache (Redis/ElastiCache, or CloudFront in front of the read API) would cut RDS load.
- **DB indexes** on common filters (location, price, host_id) + cursor pagination.
- Confirm-upload now stores the **medium** CDN variant (good); consider storing all 3 variant URLs so the UI can pick per context.
- A **dead-letter queue** on `property-sync` so a failed embed isn't lost.

## Unnecessary / cleanup
- The **local `/images` upload endpoint** (`upload_property_image_local`) is dev-only and now superseded by the presigned flow — keep it behind an "S3 not configured" guard or remove it from prod paths to avoid the broken-image trap.

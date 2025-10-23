# Red Hat Lightspeed → Google SecOps (Chronicle) Ingestion

Fetches **Red Hat Lightspeed events** (via the Notifications API)  and ingests them into **Google SecOps / Chronicle** using the Chronicle ingestion helper for centralized security analytics.

Designed to run manually or as a Cloud Function on a daily schedule.

This script:
- Fetches Red Hat Lightspeed events from the Red Hat Hybrid Cloud Console API (Notifications API), including full event payloads
- Transforms events into a Chronicle-compatible JSON structure
- Sends events using the `common.ingest.IngestClient` helper from the Chronicle `ingestion-scripts` repo

---

##  Environment Variables

| Variable | Description | Required (local) | Required (GCP) | Secret |
|---|---:|:---:|:---:|:---:|
| `INSIGHTS_CLIENT_ID` | Red Hat Insights OAuth client ID | Yes | Yes | Yes |
| `INSIGHTS_CLIENT_SECRET` | Red Hat Insights OAuth client secret | Yes | Yes | Yes |
| `CHRONICLE_API_KEY` | Chronicle ingestion API key (used by `IngestClient`) | Yes (for local usage) | No (if using service account via Secret Manager) | Yes |
| `CHRONICLE_REGION` | Chronicle region (default `malachite`) — e.g. `malachite`, `malachite-eu`, `malachite-asia` | No | No | No |
| `INSIGHTS_BASE_URL` | Base URL for Insights (override) | No | No | No |
| `CHRONICLE_SERVICE_ACCOUNT` | Optional: service account JSON or Secret Manager path. If left unset locally, set to `'{}'` to avoid Secret Manager lookups. | No | Yes | Yes |

---

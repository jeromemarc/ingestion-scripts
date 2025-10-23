import requests
import json
import os
import logging
import argparse
from datetime import datetime, timedelta, timezone
from common import ingest # from https://github.com/chronicle/ingestion-scripts

INSIGHTS_BASE_URL = "https://console.redhat.com"
INSIGHTS_TOKEN_URL = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
INSIGHTS_CLIENT_ID = os.getenv("INSIGHTS_CLIENT_ID")
INSIGHTS_CLIENT_SECRET = os.getenv("INSIGHTS_CLIENT_SECRET")
INSIGHTS_PULLING_LIMIT = 100
# URL for Chronicle instance - could also be malachiteingestion-eu.googleapis.com (Europe) and malachiteingestion-asia.googleapis.com (Asia)
CHRONICLE_API_KEY = os.getenv("CHRONICLE_API_KEY")
CHRONICLE_REGION = os.getenv("CHRONICLE_REGION", "malachite")  # e.g. us, europe, asia

def get_access_token(client_id, client_secret, scope="api.console"):
    payload = {
        "grant_type": "client_credentials",
        "scope": scope,
        "client_id": client_id,
        "client_secret": client_secret
    }
    resp = requests.post(INSIGHTS_TOKEN_URL, data=payload)
    resp.raise_for_status()
    return resp.json().get("access_token")

def get_insights_events(start_date, end_date, limit=INSIGHTS_PULLING_LIMIT):
    """
    Retrieve all Red Hat Insights events created within the last N hours, with pagination.
    """
    insights_token = get_access_token(INSIGHTS_CLIENT_ID, INSIGHTS_CLIENT_SECRET)
    headers = {"Authorization": f"Bearer {insights_token}"}
    url = f"{INSIGHTS_BASE_URL}/api/notifications/v1.0/notifications/events?includePayload=true&limit={limit}&startDate={start_date}&endDate={end_date}"
    all_events = []

    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        # Extract data
        events = result.get("data", [])
        all_events.extend(events)
        # Check for pagination
        links = result.get("links", {})
        next_path = links.get("next")
        # Bug: need to manually add missing search params to the next link (RHCLOUD-43015)
        url = f"{INSIGHTS_BASE_URL}{next_path}&startDate={start_date}&endDate={end_date}" if next_path else None

    print(f"Fetched {len(all_events)} events for {start_date} to {end_date}.")
    return all_events

def transform_event(event):
    """
    Transform a Red Hat Insights event into a Chronicle-compatible log.
    """
    # Basic metadata
    event_id = event.get("id")
    created = event.get("created")
    if created and not created.endswith("Z"):
        created = f"{created}Z"
    bundle = event.get("bundle", "Unknown")
    app = event.get("application", "Unknown")
    event_type = event.get("event_type", "Unknown")
    
    # Parse payload JSON string safely
    payload_raw = event.get("payload")
    parsed_payload = None
    if payload_raw:
        try:
            parsed_payload = json.loads(payload_raw)
        except (json.JSONDecodeError, TypeError):
            parsed_payload = {"error": "Invalid payload format", "raw": payload_raw}

    # Derive severity (simple mapping)
    severity_map = {
        "Policy triggered": "MEDIUM",
        "System became stale": "LOW",
        "New system registered": "INFO"
    }
    severity = severity_map.get(event_type, "INFO")

    # Build Chronicle-compatible structure
    return {
        "metadata": {
            "eventTimestamp": created,
            "vendor": "Red Hat Insights",
            "product": bundle,
            "eventType": event_type
        },
        "category": app.lower(),
        "severity": severity,
        "message": f"{event_type} event from {bundle} / {app}",
        "eventId": event_id,
        "rawLog": json.dumps(parsed_payload or event)
    }

def send_to_chronicle(events):
    """Send transformed Red Hat Insights events to Google Chronicle."""
    logger = logging.getLogger(__name__)

    # Chronicle ingestion client
    client = ingest.IngestClient(
        api_key=CHRONICLE_API_KEY,
        region=CHRONICLE_REGION,
        log_type="redhat_insights"
    )

    # The helper automatically handles batching, retries, and validation
    try:
        response = client.ingest(events)
        logger.info("Successfully sent %d events to Chronicle", len(events))
        logger.debug("Response: %s", response)
    except Exception as e:
        logger.error("Failed to send events to Chronicle: %s", e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Red Hat Insights events into Google Chronicle.")
    parser.add_argument("--dry-run", action="store_true", help="Print transformed events instead of sending to Chronicle.")
    args = parser.parse_args()

    # Retrieve all Insights events triggered yesterday
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    start_date = yesterday.strftime("%Y-%m-%d")
    end_date = (yesterday + timedelta(days=1)).strftime("%Y-%m-%d")
    
    insights_events = get_insights_events(start_date, end_date)
    formatted = [transform_event(e) for e in insights_events]
    
    if args.dry_run:
        print(json.dumps(formatted, indent=2))
    else:
        send_to_chronicle(formatted)

"""
Boston Food Inspections Dashboard - Data Sync Job
Fetches recent inspections from Analyze Boston CKAN API and updates PostgreSQL database
"""

import requests
from datetime import datetime, timedelta
import sys
import logging

from .config import settings
from .database import (
    get_db_connection,
    init_db,
    upsert_inspection,
    create_sync_log,
    update_sync_log
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_inspections_from_ckan(days: int = 90, limit: int = 10000, offset: int = 0) -> list:
    """
    Fetch inspections from Analyze Boston CKAN API.
    Uses SQL endpoint for date filtering with pagination support.

    Args:
        days: Number of days back to fetch
        limit: Max records per request (CKAN max is 32000)
        offset: Starting record for pagination
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Use resultdttm (inspection result date) for filtering
    sql = f'''
        SELECT * FROM "{settings.CKAN_RESOURCE_ID}"
        WHERE "resultdttm" >= '{cutoff_date}'
        ORDER BY "resultdttm" DESC
        LIMIT {limit} OFFSET {offset}
    '''

    logger.info(f"Fetching inspections since {cutoff_date} (last {days} days) - offset {offset}")

    try:
        response = requests.get(
            settings.CKAN_SQL_API_URL,
            params={"sql": sql},
            timeout=120
        )
        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            error = result.get("error", {})
            error_msg = error.get("message", "Unknown API error")
            raise Exception(f"CKAN API error: {error_msg}")

        records = result["result"]["records"]
        logger.info(f"Successfully fetched {len(records)} inspection records from API")
        return records

    except requests.exceptions.Timeout:
        logger.error("Request to CKAN API timed out")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching from CKAN API: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching inspections: {e}")
        raise


def fetch_all_inspections_paginated(days: int = 90, batch_size: int = 10000) -> list:
    """
    Fetch all inspections for a date range using pagination.
    Continues fetching until no more records are returned.

    Args:
        days: Number of days back to fetch
        batch_size: Records per API call (max 32000 for CKAN)

    Returns:
        List of all inspection records
    """
    all_records = []
    offset = 0

    while True:
        batch = fetch_inspections_from_ckan(days=days, limit=batch_size, offset=offset)

        if not batch:
            logger.info(f"No more records found. Total fetched: {len(all_records)}")
            break

        all_records.extend(batch)
        offset += len(batch)

        logger.info(f"Fetched batch of {len(batch)} records. Total so far: {len(all_records)}")

        # If we got fewer records than requested, we've reached the end
        if len(batch) < batch_size:
            logger.info(f"Received fewer than {batch_size} records. Pagination complete.")
            break

        # Add a small delay between requests to be respectful to the API
        import time
        time.sleep(1)

    return all_records


def sync_inspections(days: int = None) -> dict:
    """
    Main sync function - fetch inspections from CKAN and upsert to database.
    Returns dict with sync statistics.
    """
    if days is None:
        days = settings.SYNC_DAYS_BACK

    logger.info(f"Starting sync job at {datetime.now().isoformat()}")
    logger.info(f"Syncing inspections from last {days} days")

    # Initialize database if needed
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    with get_db_connection() as conn:
        # Create sync log entry
        sync_id = create_sync_log(conn)
        logger.info(f"Created sync log entry with ID: {sync_id}")

        inserted_count = 0
        updated_count = 0
        records = []

        try:
            # Fetch from CKAN API
            records = fetch_inspections_from_ckan(days=days)

            # Process each record
            for i, record in enumerate(records, 1):
                try:
                    was_inserted, inspection_key = upsert_inspection(conn, record)

                    if was_inserted:
                        inserted_count += 1
                    else:
                        updated_count += 1

                    # Log progress every 100 records
                    if i % 100 == 0:
                        logger.info(f"Processed {i}/{len(records)} records")

                except Exception as e:
                    logger.warning(f"Failed to upsert inspection {record.get('businessname')}: {e}")
                    continue

            # Commit all changes
            conn.commit()

            # Update sync log with success
            update_sync_log(
                conn,
                sync_id,
                records_fetched=len(records),
                records_inserted=inserted_count,
                records_updated=updated_count,
                status="success"
            )

            logger.info(
                f"Sync completed successfully: "
                f"{inserted_count} inserted, {updated_count} updated, "
                f"{len(records)} total fetched"
            )

            return {
                "status": "success",
                "fetched": len(records),
                "inserted": inserted_count,
                "updated": updated_count
            }

        except Exception as e:
            # Rollback on error
            conn.rollback()

            # Update sync log with error
            update_sync_log(
                conn,
                sync_id,
                records_fetched=len(records),
                records_inserted=inserted_count,
                records_updated=updated_count,
                status="error",
                error_message=str(e)
            )

            logger.error(f"Sync failed: {e}")
            raise


if __name__ == "__main__":
    # Allow overriding days via command line argument
    # Usage: python -m backend.sync_job [days]
    days = None
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
            logger.info(f"Using command-line override: syncing {days} days")
        except ValueError:
            logger.error(f"Invalid days argument: {sys.argv[1]}")
            sys.exit(1)

    try:
        result = sync_inspections(days=days)
        logger.info(f"Sync result: {result}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Sync job failed: {e}")
        sys.exit(1)

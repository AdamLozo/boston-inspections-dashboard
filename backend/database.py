"""
Boston Food Inspections Dashboard - Database Operations
PostgreSQL connection and schema management with raw SQL (no ORM)
"""

import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, List
import logging
import re

from .config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Returns connection with dict row factory for dict-like row access.
    """
    conn = None
    try:
        conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """Initialize database schema - creates tables and indexes if they don't exist"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Create inspections table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inspections (
                    id SERIAL PRIMARY KEY,

                    -- Unique identifier (we'll use combination of business + inspection date)
                    inspection_key VARCHAR(255) UNIQUE NOT NULL,

                    -- Business information
                    businessname VARCHAR(255),
                    dbaname VARCHAR(255),
                    legalowner VARCHAR(255),
                    licenseno VARCHAR(50),
                    licstatus VARCHAR(50),
                    licensecat VARCHAR(100),

                    -- License dates
                    license_issued_date TIMESTAMP,
                    license_expiration_date TIMESTAMP,

                    -- Inspection details
                    result VARCHAR(50),
                    resultdttm TIMESTAMP,

                    -- Violation information
                    violation_code VARCHAR(50),
                    viol_level VARCHAR(10),
                    violdesc TEXT,
                    violdttm TIMESTAMP,
                    viol_status VARCHAR(50),
                    comments TEXT,

                    -- Location
                    address VARCHAR(255),
                    city VARCHAR(100),
                    state VARCHAR(10),
                    zip VARCHAR(10),
                    property_id VARCHAR(50),
                    latitude DECIMAL(10,7),
                    longitude DECIMAL(10,7),

                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for common queries
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_resultdttm ON inspections(resultdttm DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_businessname ON inspections(businessname)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_zip ON inspections(zip)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_result ON inspections(result)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_licstatus ON inspections(licstatus)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_coords ON inspections(latitude, longitude)")

            # Create sync_log table (shared across all Boston dashboards)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(50) NOT NULL DEFAULT 'inspections',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status VARCHAR(20),
                    records_fetched INTEGER,
                    records_inserted INTEGER,
                    records_updated INTEGER,
                    error_message TEXT
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_log_source ON sync_log(source)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_log_started ON sync_log(started_at DESC)")

            conn.commit()
            logger.info("Database schema initialized successfully")


def parse_coordinates(location: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    Parse coordinates from location field in format: (latitude, longitude)
    Example: "(42.35108502118551, -71.0607889159121)"

    Returns: (latitude, longitude) or (None, None) if parsing fails
    """
    if not location:
        return None, None

    try:
        # Extract coordinates from "(lat, lng)" format
        match = re.match(r'\(([0-9.-]+),\s*([0-9.-]+)\)', location.strip())
        if not match:
            return None, None

        lat = float(match.group(1))
        lng = float(match.group(2))

        # Validate Boston coordinates (rough bounding box)
        if 42.2 <= lat <= 42.4 and -71.2 <= lng <= -70.9:
            return lat, lng
        else:
            logger.debug(f"Coordinates outside Boston bounds: {lat}, {lng}")
            return None, None

    except (ValueError, AttributeError, TypeError) as e:
        logger.debug(f"Failed to parse coordinates from '{location}': {e}")
        return None, None


def upsert_inspection(conn, record: Dict) -> tuple[bool, str]:
    """
    Insert or update an inspection record.
    Returns (was_inserted, inspection_key)
    """
    with conn.cursor() as cur:
        # Create unique key from business name + result date + violation code
        # This allows multiple violations per inspection
        businessname = record.get('businessname', 'UNKNOWN')
        resultdttm = record.get('resultdttm', '')
        violation = record.get('violation', '')
        inspection_key = f"{businessname}_{resultdttm}_{violation}"

        # Parse dates
        license_issued = record.get('issdttm')
        license_expiration = record.get('expdttm')
        result_datetime = record.get('resultdttm')
        viol_datetime = record.get('violdttm')

        # Parse coordinates
        latitude, longitude = parse_coordinates(record.get('location'))

        cur.execute("""
            INSERT INTO inspections (
                inspection_key, businessname, dbaname, legalowner,
                licenseno, licstatus, licensecat,
                license_issued_date, license_expiration_date,
                result, resultdttm,
                violation_code, viol_level, violdesc, violdttm, viol_status,
                comments, address, city, state, zip,
                property_id, latitude, longitude, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (inspection_key) DO UPDATE SET
                businessname = EXCLUDED.businessname,
                dbaname = EXCLUDED.dbaname,
                legalowner = EXCLUDED.legalowner,
                licenseno = EXCLUDED.licenseno,
                licstatus = EXCLUDED.licstatus,
                licensecat = EXCLUDED.licensecat,
                license_issued_date = EXCLUDED.license_issued_date,
                license_expiration_date = EXCLUDED.license_expiration_date,
                result = EXCLUDED.result,
                resultdttm = EXCLUDED.resultdttm,
                violation_code = EXCLUDED.violation_code,
                viol_level = EXCLUDED.viol_level,
                violdesc = EXCLUDED.violdesc,
                violdttm = EXCLUDED.violdttm,
                viol_status = EXCLUDED.viol_status,
                comments = EXCLUDED.comments,
                address = EXCLUDED.address,
                city = EXCLUDED.city,
                state = EXCLUDED.state,
                zip = EXCLUDED.zip,
                property_id = EXCLUDED.property_id,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                updated_at = CURRENT_TIMESTAMP
            RETURNING (xmax = 0) AS inserted
        """, (
            inspection_key,
            record.get('businessname'),
            record.get('dbaname'),
            record.get('legalowner'),
            record.get('licenseno'),
            record.get('licstatus'),
            record.get('licensecat'),
            license_issued,
            license_expiration,
            record.get('result'),
            result_datetime,
            record.get('violation'),
            record.get('viol_level'),
            record.get('violdesc'),
            viol_datetime,
            record.get('viol_status'),
            record.get('comments'),
            record.get('address'),
            record.get('city'),
            record.get('state'),
            record.get('zip'),
            record.get('property_id'),
            latitude,
            longitude,
            datetime.now()
        ))

        result = cur.fetchone()
        if result:
            was_inserted = result['inserted'] if isinstance(result, dict) else result[0]
        else:
            was_inserted = False
        return was_inserted, inspection_key


def create_sync_log(conn) -> int:
    """Create a new sync log entry and return its ID"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sync_log (source, started_at, status)
            VALUES ('inspections', CURRENT_TIMESTAMP, 'running')
            RETURNING id
        """)
        result = cur.fetchone()
        sync_id = result['id'] if isinstance(result, dict) else result[0]
        conn.commit()
        return sync_id


def update_sync_log(
    conn,
    sync_id: int,
    records_fetched: int,
    records_inserted: int,
    records_updated: int,
    status: str,
    error_message: Optional[str] = None
):
    """Update sync log with completion details"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE sync_log
            SET completed_at = CURRENT_TIMESTAMP,
                status = %s,
                records_fetched = %s,
                records_inserted = %s,
                records_updated = %s,
                error_message = %s
            WHERE id = %s
        """, (status, records_fetched, records_inserted, records_updated, error_message, sync_id))
        conn.commit()


def get_last_sync(conn) -> Optional[Dict]:
    """Get the most recent sync log entry for inspections"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM sync_log
            WHERE source = 'inspections'
            ORDER BY started_at DESC
            LIMIT 1
        """)
        return cur.fetchone()


if __name__ == "__main__":
    # Initialize database when run directly
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialized successfully")

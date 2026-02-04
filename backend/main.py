"""
Boston Food Inspections Dashboard - FastAPI Backend
API endpoints for restaurant inspection data
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
from pathlib import Path
import logging
import psycopg2.extras

from .config import settings
from .database import get_db_connection, init_db, get_last_sync
from decimal import Decimal
from datetime import date, datetime as dt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def serialize_row(row: dict) -> dict:
    """Convert database row to JSON-serializable dict"""
    result = {}
    for key, value in row.items():
        if isinstance(value, (date, dt)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


app = FastAPI(
    title="Boston Food Inspections Dashboard",
    description="Track restaurant health inspections across Boston",
    version="1.0.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    logger.info("Starting Boston Food Inspections Dashboard API")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@app.get("/api/inspections")
async def get_inspections(
    zip: Optional[str] = Query(None, alias="zip", description="Filter by ZIP code"),
    result: Optional[str] = Query(None, description="Filter by inspection result"),
    days: int = Query(90, ge=1, le=3650, description="Number of days to look back"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get most recent inspection per establishment with optional filters.
    Groups by business name to show only the latest inspection.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Build WHERE clause
                conditions = [f"resultdttm >= CURRENT_DATE - INTERVAL '{days} days'"]
                params = []

                if zip:
                    conditions.append("zip = %s")
                    params.append(zip)

                if result:
                    conditions.append("result = %s")
                    params.append(result)

                where_clause = " AND ".join(conditions)

                # Get latest inspection per business (with coordinates)
                # Uses DISTINCT ON to get most recent inspection per business
                query = f"""
                    WITH latest_inspections AS (
                        SELECT DISTINCT ON (businessname, address)
                            *
                        FROM inspections
                        WHERE {where_clause}
                          AND latitude IS NOT NULL
                          AND longitude IS NOT NULL
                        ORDER BY businessname, address, resultdttm DESC
                    )
                    SELECT * FROM latest_inspections
                    ORDER BY resultdttm DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [limit, offset])
                inspections = cur.fetchall()

                # Get total count of unique establishments
                count_query = f"""
                    SELECT COUNT(DISTINCT businessname || '_' || address) as count
                    FROM inspections
                    WHERE {where_clause}
                      AND latitude IS NOT NULL
                      AND longitude IS NOT NULL
                """
                cur.execute(count_query, params)
                total = cur.fetchone()['count']

                return {
                    "data": [serialize_row(row) for row in inspections],
                    "count": len(inspections),
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }

    except Exception as e:
        logger.error(f"Error fetching inspections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats(days: int = Query(90, ge=1, le=3650, description="Number of days to analyze")):
    """Get inspection statistics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Total unique establishments inspected
                cur.execute(f"""
                    SELECT COUNT(DISTINCT businessname || '_' || address) as count
                    FROM inspections
                    WHERE resultdttm >= CURRENT_DATE - INTERVAL '{days} days'
                """)
                total_establishments = cur.fetchone()['count']

                # Pass rate (inspections with passing results)
                # Passing results include: Pass, HE_Pass, NoViol, PassViol
                cur.execute(f"""
                    WITH latest_by_business AS (
                        SELECT DISTINCT ON (businessname, address)
                            result
                        FROM inspections
                        WHERE resultdttm >= CURRENT_DATE - INTERVAL '{days} days'
                        ORDER BY businessname, address, resultdttm DESC
                    )
                    SELECT
                        COUNT(*) FILTER (WHERE result IN ('Pass', 'HE_Pass', 'NoViol', 'PassViol')) as passed,
                        COUNT(*) as total
                    FROM latest_by_business
                """)
                pass_stats = cur.fetchone()
                pass_rate = (pass_stats['passed'] / pass_stats['total'] * 100) if pass_stats['total'] > 0 else 0

                # Total violations
                cur.execute(f"""
                    SELECT COUNT(*) as count
                    FROM inspections
                    WHERE resultdttm >= CURRENT_DATE - INTERVAL '{days} days'
                      AND violation_code IS NOT NULL
                """)
                total_violations = cur.fetchone()['count']

                # By result type
                cur.execute(f"""
                    WITH latest_by_business AS (
                        SELECT DISTINCT ON (businessname, address)
                            result
                        FROM inspections
                        WHERE resultdttm >= CURRENT_DATE - INTERVAL '{days} days'
                        ORDER BY businessname, address, resultdttm DESC
                    )
                    SELECT result, COUNT(*) as count
                    FROM latest_by_business
                    WHERE result IS NOT NULL
                    GROUP BY result
                    ORDER BY count DESC
                """)
                by_result = [
                    {"result": row['result'], "count": row['count']}
                    for row in cur.fetchall()
                ]

                # By ZIP code
                cur.execute(f"""
                    WITH latest_by_business AS (
                        SELECT DISTINCT ON (businessname, address)
                            zip
                        FROM inspections
                        WHERE resultdttm >= CURRENT_DATE - INTERVAL '{days} days'
                        ORDER BY businessname, address, resultdttm DESC
                    )
                    SELECT zip, COUNT(*) as count
                    FROM latest_by_business
                    WHERE zip IS NOT NULL
                    GROUP BY zip
                    ORDER BY count DESC
                    LIMIT 15
                """)
                by_zip = [{"zip": row['zip'], "count": row['count']} for row in cur.fetchall()]

                return {
                    "period_days": days,
                    "total_establishments": total_establishments,
                    "pass_rate": round(pass_rate, 1),
                    "total_violations": total_violations,
                    "by_result": by_result,
                    "by_zip": by_zip
                }

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/neighborhoods")
async def get_neighborhoods():
    """Get list of all ZIP codes with establishment counts"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT zip, COUNT(DISTINCT businessname || '_' || address) as count
                    FROM inspections
                    WHERE zip IS NOT NULL
                    GROUP BY zip
                    ORDER BY zip
                """)
                zip_codes = cur.fetchall()

                return {"data": [serialize_row(row) for row in zip_codes]}

    except Exception as e:
        logger.error(f"Error fetching neighborhoods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results")
async def get_result_types():
    """Get list of all inspection result types"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT result
                    FROM inspections
                    WHERE result IS NOT NULL
                    ORDER BY result
                """)
                results = cur.fetchall()

                return {
                    "data": [
                        {"code": row['result'], "label": row['result']}
                        for row in results
                    ]
                }

    except Exception as e:
        logger.error(f"Error fetching result types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns healthy/degraded/unhealthy based on database and sync status.
    """
    try:
        # Check database connection
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT 1")

            # Get last sync
            last_sync = get_last_sync(conn)

            if last_sync is None:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "database": "connected",
                        "last_sync": None,
                        "error": "No sync records found"
                    }
                )

            # Calculate hours since last sync
            if last_sync['completed_at']:
                hours_since_sync = (
                    datetime.now() - last_sync['completed_at']
                ).total_seconds() / 3600
            else:
                hours_since_sync = None

            # Determine health status
            if hours_since_sync and hours_since_sync > 36:
                return {
                    "status": "degraded",
                    "database": "connected",
                    "last_sync": last_sync['completed_at'].isoformat() if last_sync['completed_at'] else None,
                    "hours_since_sync": round(hours_since_sync, 1),
                    "warning": "Last sync was more than 36 hours ago"
                }

            if last_sync['status'] == 'error':
                return {
                    "status": "degraded",
                    "database": "connected",
                    "last_sync": last_sync['completed_at'].isoformat() if last_sync['completed_at'] else None,
                    "hours_since_sync": round(hours_since_sync, 1) if hours_since_sync else None,
                    "warning": f"Last sync failed: {last_sync.get('error_message', 'Unknown error')}"
                }

            return {
                "status": "healthy",
                "database": "connected",
                "last_sync": last_sync['completed_at'].isoformat() if last_sync['completed_at'] else None,
                "hours_since_sync": round(hours_since_sync, 1) if hours_since_sync else None,
                "records_synced": last_sync.get('records_inserted', 0) + last_sync.get('records_updated', 0)
            }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "error": str(e)
            }
        )


# Serve static files (frontend) - mount after API routes
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

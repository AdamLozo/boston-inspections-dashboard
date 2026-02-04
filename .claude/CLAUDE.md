# Boston Food Inspections Dashboard - Claude Code Context

## Project Overview
Restaurant health inspections dashboard tracking food establishment compliance across Boston with daily automated data sync from Analyze Boston.

## Quick Reference
- **Repo**: boston-inspections-dashboard
- **Stack**: Python/FastAPI + PostgreSQL + Vanilla JS/Leaflet.js
- **Hosting**: Render (web service + cron job + shared PostgreSQL)
- **Data Source**: Analyze Boston CKAN API

## Directory Structure
```
boston-inspections-dashboard/
├── .claude/                    # YOU ARE HERE - Claude Code context
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── database.py             # DB operations (inspections table)
│   ├── sync_job.py             # Cron script for daily sync
│   └── config.py               # Environment config
├── frontend/
│   └── index.html              # Single-page dashboard
├── requirements.txt
├── render.yaml                 # Render deployment config
└── README.md
```

## Critical Context

### Data Characteristics
- **Resource ID**: `4582bec6-2b4f-4f9e-bc55-cbaa73117f4c`
- **Date Field**: `resultdttm` (inspection result date/time)
- **Unique Key**: Combination of `businessname`, `resultdttm`, `violation_code`
- **Coordinates**: 91% coverage, format `(latitude, longitude)`
- **Volume**: 800,000+ records dating back to 2006

### Key Design Decisions
1. **Most Recent Inspection Per Establishment**: Uses `DISTINCT ON (businessname, address)` to show only latest inspection
2. **Color-Coded Markers**: Green=Pass, Red=Fail, Yellow=Warning
3. **Shared Database**: Uses `boston-data-db` with `inspections` table (separate from permits)
4. **Coordinate Parsing**: Regex extraction from `(lat, lng)` string format

## Code Conventions
- **Python**: Black formatting, type hints, docstrings
- **SQL**: Raw SQL via psycopg (no ORM) - parameterized queries only
- **Frontend**: Vanilla JS (no frameworks), mobile-first CSS
- **Error Handling**: Always return meaningful JSON errors
- **Logging**: Use Python logging module, structured logs for production

## Environment Variables
```
DATABASE_URL=postgresql://user:pass@host:port/boston_data
SYNC_DAYS_BACK=90
```

## Key Patterns

### Database Connection
```python
# Use context manager pattern
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(query, params)
```

### Coordinate Parsing
```python
# Extract from "(42.351, -71.060)" format
import re
match = re.match(r'\(([0-9.-]+),\s*([0-9.-]+)\)', location_string)
latitude = float(match.group(1))
longitude = float(match.group(2))

# Validate Boston bounds
if 42.2 <= lat <= 42.4 and -71.2 <= lng <= -70.9:
    # Valid coordinate
```

### API Response Format
```python
# Success
{"data": [...], "count": n, "total": m}

# Error
{"error": "message", "detail": "..."}
```

### CKAN API Query
```python
# Always use SQL endpoint for complex queries
url = "https://data.boston.gov/api/3/action/datastore_search_sql"
sql = f"SELECT * FROM \"{resource_id}\" WHERE resultdttm >= '{date}'"
```

## When You're Stuck
1. Reference building permits dashboard at `../boston-data-dashboard` for patterns
2. Check README.md for deployment and API documentation
3. Ask Adam for clarification before guessing

## Testing Locally
```bash
# Initialize database
python -m backend.database

# Run sync (30 days for testing)
python -m backend.sync_job 30

# Start server
uvicorn backend.main:app --reload

# Test endpoints
curl http://localhost:8000/api/health
curl "http://localhost:8000/api/inspections?days=30&limit=10"
curl http://localhost:8000/api/stats?days=30
```

## Deployment Notes
- Uses shared `boston-data-db` PostgreSQL instance (not separate database)
- Web service and cron job both need `DATABASE_URL` from shared database
- Custom domain: `inspections.adamlozo.com` (CNAME to Render)
- Initial backfill: Run `python -m backend.sync_job 365` after first deploy

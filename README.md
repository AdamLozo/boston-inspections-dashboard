# Boston Restaurant Inspections Dashboard

Interactive map-based dashboard tracking food establishment health inspections across Boston neighborhoods. Built with Python/FastAPI backend, PostgreSQL database, and vanilla JavaScript frontend.

**Live Dashboard**: [bostonrestaurants.adamlozo.com](https://bostonrestaurants.adamlozo.com) _(coming soon)_

![Dashboard Screenshot](docs/screenshot.png) _(screenshot placeholder)_

---

## Features

- **Interactive Map**: Color-coded markers (green=Pass, red=Fail, yellow=Warning) showing most recent inspection per establishment
- **Real-time Filters**: Filter by ZIP code, inspection result, and time period
- **Inspection Details**: Click any restaurant to see inspection results, violations, and license status
- **Daily Data Sync**: Automated sync with [Analyze Boston](https://data.boston.gov) open data portal
- **Mobile Responsive**: Works seamlessly on desktop, tablet, and mobile devices

---

## Data Source

**Dataset**: [Food Establishment Inspections](https://data.boston.gov/dataset/food-establishment-inspections)
**Provider**: City of Boston Inspectional Services Department
**Update Frequency**: Daily
**Coverage**: 91% of records include GPS coordinates
**Records**: 800,000+ inspections dating back to 2006

---

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **PostgreSQL**: Database (shared across Boston dashboards)
- **psycopg3**: PostgreSQL adapter
- **Requests**: HTTP client for CKAN API

### Frontend
- **Vanilla JavaScript**: No frameworks, fast and lightweight
- **Leaflet.js**: Interactive maps
- **Leaflet.markercluster**: Efficient marker clustering
- **Chart.js**: Data visualizations _(planned)_

### Infrastructure
- **Render**: Web service hosting + cron jobs
- **GitHub**: Version control and CI/CD
- **GoDaddy**: DNS management

---

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Git

### Setup

```bash
# Clone repository
git clone https://github.com/AdamLozo/boston-inspections-dashboard.git
cd boston-inspections-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your DATABASE_URL

# Initialize database
python -m backend.database

# Run initial data sync (last 90 days)
python -m backend.sync_job 90

# Start development server
uvicorn backend.main:app --reload
```

Visit http://localhost:8000 to see the dashboard.

---

## Project Structure

```
boston-inspections-dashboard/
├── backend/
│   ├── __init__.py
│   ├── config.py          # Environment configuration
│   ├── database.py        # PostgreSQL operations
│   ├── main.py            # FastAPI application
│   └── sync_job.py        # CKAN data sync script
├── frontend/
│   └── index.html         # Single-page dashboard
├── .claude/
│   └── CLAUDE.md          # Claude Code context
├── docs/
│   └── screenshot.png     # Dashboard screenshot
├── .env.example           # Environment variables template
├── .gitignore
├── README.md
├── render.yaml            # Render deployment config
└── requirements.txt       # Python dependencies
```

---

## Database Schema

```sql
CREATE TABLE inspections (
    id SERIAL PRIMARY KEY,
    inspection_key VARCHAR(255) UNIQUE NOT NULL,

    -- Business information
    businessname VARCHAR(255),
    dbaname VARCHAR(255),
    licenseno VARCHAR(50),
    licstatus VARCHAR(50),

    -- Inspection details
    result VARCHAR(50),              -- Pass, Fail, Warning
    resultdttm TIMESTAMP,            -- Inspection date

    -- Violation information
    violation_code VARCHAR(50),
    viol_level VARCHAR(10),          -- Severity (* to ***)
    violdesc TEXT,

    -- Location
    address VARCHAR(255),
    zip VARCHAR(10),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API Endpoints

### `GET /api/inspections`
Get inspections with filters (shows most recent per establishment)

**Query Parameters:**
- `zip` (optional): Filter by ZIP code
- `result` (optional): Filter by inspection result (Pass/Fail/Warning)
- `days` (default: 90): Number of days to look back (1-3650)
- `limit` (default: 1000): Maximum results
- `offset` (default: 0): Pagination offset

### `GET /api/stats`
Get statistics for specified time period

**Query Parameters:**
- `days` (default: 90): Number of days to analyze

**Response:**
```json
{
  "total_establishments": 5234,
  "pass_rate": 92.3,
  "total_violations": 1842,
  "by_result": [...],
  "by_zip": [...]
}
```

### `GET /api/neighborhoods`
List all ZIP codes with establishment counts

### `GET /api/results`
List all inspection result types

### `GET /api/health`
Health check and sync status

---

## Deployment

### Render Setup

1. **Create PostgreSQL Database** (if not exists):
   - Name: `boston-data-db`
   - Plan: Starter ($7/month, shared across dashboards)

2. **Create Web Service**:
   - Name: `boston-inspections-web`
   - Runtime: Python
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Environment Variables:
     - `DATABASE_URL`: Link to `boston-data-db`
     - `SYNC_DAYS_BACK`: `90`

3. **Create Cron Job**:
   - Name: `boston-inspections-sync`
   - Schedule: `0 11 * * *` (6 AM EST daily)
   - Command: `python -m backend.sync_job`
   - Environment Variables: Same as web service

4. **Configure Custom Domain**:
   - Add custom domain in Render: `inspections.adamlozo.com`
   - Add CNAME record in GoDaddy:
     - Type: `CNAME`
     - Name: `inspections`
     - Value: `[service-name].onrender.com`

5. **Initial Backfill**:
   - After deployment, run historical backfill via Render Shell:
     ```bash
     python -m backend.sync_job 365
     ```

---

## Coordinate Parsing

The dataset includes coordinates in parenthetical format: `(latitude, longitude)`. The parsing logic:

```python
import re

def parse_coordinates(location: str) -> tuple[float, float]:
    match = re.match(r'\(([0-9.-]+),\s*([0-9.-]+)\)', location.strip())
    if match:
        lat = float(match.group(1))
        lng = float(match.group(2))
        # Validate Boston bounds (42.2-42.4, -71.2 to -70.9)
        if 42.2 <= lat <= 42.4 and -71.2 <= lng <= -70.9:
            return lat, lng
    return None, None
```

---

## Future Enhancements

- [ ] Time-series charts showing inspection trends
- [ ] Search by business name
- [ ] Violation category breakdown
- [ ] Export filtered data to CSV
- [ ] Heatmap visualization of high-violation areas
- [ ] Year-over-year comparison view

---

## Related Projects

Part of the **Adam Lozo Portfolio** ecosystem:
- [Building Permits Dashboard](https://github.com/AdamLozo/boston-data-dashboard)
- [311 Service Requests](https://github.com/AdamLozo/boston-311-dashboard) _(planned)_
- [Portfolio Hub](https://adamlozo.com)

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Contact

**Adam Lozo**
Portfolio: [adamlozo.com](https://adamlozo.com)
GitHub: [@AdamLozo](https://github.com/AdamLozo)
LinkedIn: [/in/adamlozo](https://linkedin.com/in/adamlozo)

---

## Acknowledgments

- **City of Boston**: Open data via [Analyze Boston](https://data.boston.gov)
- **Leaflet.js**: Interactive mapping library
- **Render**: Hosting platform

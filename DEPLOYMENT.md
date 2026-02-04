# Deployment Guide - Boston Restaurant Inspections Dashboard

## Pre-Deployment Checklist

- [x] All code written and tested
- [x] Database schema designed (inspections table)
- [x] Coordinate parsing logic verified
- [x] Frontend UI built with color-coded markers
- [x] API endpoints implemented
- [x] Documentation complete
- [ ] GitHub repository created
- [ ] Render services configured
- [ ] Initial data backfill completed

---

## Step 1: Create GitHub Repository

```bash
cd C:\Users\adam\OneDrive\Claude\Projects\boston-inspections-dashboard

# Initialize git
git init
git add .
git commit -m "Initial commit: Boston Restaurant Inspections Dashboard"

# Create GitHub repo (via gh CLI or web interface)
gh repo create boston-inspections-dashboard --public --source=. --remote=origin

# Push to GitHub
git push -u origin main
```

---

## Step 2: Configure Render Services

### A. Verify Shared Database Exists

Check that `boston-data-db` exists in Render (created for permits dashboard):
- Go to https://dashboard.render.com/databases
- Confirm `boston-data-db` (Starter plan, $7/month)
- If not exists, create new PostgreSQL database:
  - Name: `boston-data-db`
  - Database: `boston_data`
  - Plan: Starter

### B. Create Web Service

1. Go to https://dashboard.render.com → "New+" → "Web Service"
2. Connect to `boston-inspections-dashboard` repository
3. Configure:
   - **Name**: `boston-restaurants-web`
   - **Runtime**: Python 3
   - **Region**: Oregon (US West)
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
4. Environment Variables:
   - `DATABASE_URL`: Select "From Database" → `boston-data-db` → Connection String
   - `SYNC_DAYS_BACK`: `90`
5. Click "Create Web Service"

### C. Create Cron Job

1. Go to https://dashboard.render.com → "New+" → "Cron Job"
2. Connect to `boston-inspections-dashboard` repository
3. Configure:
   - **Name**: `boston-restaurants-sync`
   - **Runtime**: Python 3
   - **Region**: Oregon (US West)
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Command**: `python -m backend.sync_job`
   - **Schedule**: `0 11 * * *` (6 AM EST / 11 AM UTC, daily)
4. Environment Variables:
   - `DATABASE_URL`: Select "From Database" → `boston-data-db` → Connection String
   - `SYNC_DAYS_BACK`: `90`
5. Click "Create Cron Job"

---

## Step 3: Configure Custom Domain

### A. Add Custom Domain in Render

1. Go to Web Service → Settings → Custom Domains
2. Click "Add Custom Domain"
3. Enter: `bostonrestaurants.adamlozo.com`
4. Render will provide a target (e.g., `boston-restaurants-web.onrender.com`)

### B. Add CNAME Record in GoDaddy

1. Go to GoDaddy DNS Management for `adamlozo.com`
2. Add new CNAME record:
   - **Type**: CNAME
   - **Name**: `inspections`
   - **Value**: `boston-restaurants-web.onrender.com` (from Render)
   - **TTL**: 600 seconds
3. Save
4. Wait ~10 minutes for SSL certificate provisioning

---

## Step 4: Initial Deployment & Database Setup

### A. Wait for Deployment

Monitor deployment in Render dashboard. First build takes 2-3 minutes.

### B. Initialize Database via Render Shell

Once web service is deployed:

1. Go to Web Service → Shell tab
2. Run database initialization:
   ```bash
   python -m backend.database
   ```
3. Expected output:
   ```
   Database schema initialized successfully
   ```

### C. Run Historical Backfill

Still in Render Shell, fetch 1 year of data:

```bash
python -m backend.sync_job 365
```

**Expected output:**
```
Fetching inspections since 2025-02-04 (last 365 days)
Successfully fetched 10000 inspections from API
Processed 10000/10000 records
Sync completed successfully: X inserted, Y updated, 10000 total fetched
```

**Note:** This may take 5-10 minutes depending on record volume.

---

## Step 5: Verification

### A. Check Health Endpoint

```bash
curl https://bostonrestaurants.adamlozo.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "last_sync": "2026-02-04T11:00:00",
  "hours_since_sync": 0.5,
  "records_synced": 10000
}
```

### B. Test API Endpoints

```bash
# Get recent inspections
curl "https://bostonrestaurants.adamlozo.com/api/inspections?days=30&limit=5"

# Get statistics
curl "https://bostonrestaurants.adamlozo.com/api/stats?days=90"

# Get neighborhoods
curl "https://bostonrestaurants.adamlozo.com/api/neighborhoods"
```

### C. Verify Frontend

Visit https://bostonrestaurants.adamlozo.com in browser:

- [ ] Map loads and displays markers
- [ ] Markers are color-coded (green/red/yellow)
- [ ] ZIP code filter populates
- [ ] Result filter populates
- [ ] Stats bar shows data
- [ ] Clicking marker shows inspection popup
- [ ] Mobile view works (test on phone)

---

## Step 6: Monitor & Troubleshoot

### Check Logs

- **Web Service Logs**: Render Dashboard → `boston-restaurants-web` → Logs
- **Cron Job Logs**: Render Dashboard → `boston-restaurants-sync` → Logs

### Common Issues

**Issue**: No markers on map
- Check browser console for JavaScript errors
- Verify API returns data with coordinates: `/api/inspections?limit=5`
- Check database: records should have non-null `latitude` and `longitude`

**Issue**: Sync job fails
- Check cron job logs for error message
- Verify `DATABASE_URL` is set correctly
- Test CKAN API manually: `https://data.boston.gov/dataset/food-establishment-inspections`

**Issue**: Custom domain not working
- Verify DNS propagation: `nslookup bostonrestaurants.adamlozo.com`
- Check SSL certificate status in Render
- Wait 10-30 minutes for SSL provisioning

---

## Step 7: Update Portfolio Hub

Once deployed, add to main portfolio site:

1. Update `adamlozo-landing` repository
2. Add inspections dashboard to projects grid:
   ```html
   <div class="project-card">
     <h3>Restaurant Inspections</h3>
     <p>Track food establishment health inspections across Boston</p>
     <a href="https://bostonrestaurants.adamlozo.com">View Dashboard →</a>
   </div>
   ```

---

## Ongoing Maintenance

### Daily Sync

Cron job runs automatically at 6 AM EST (11 AM UTC) daily:
- Fetches last 90 days of inspections
- Updates existing records
- Inserts new records
- Check logs occasionally to ensure success

### Database Growth

Monitor database size:
```sql
SELECT
    COUNT(*) as total_records,
    pg_size_pretty(pg_total_relation_size('inspections')) as table_size
FROM inspections;
```

Expected growth: ~500-1000 records per day (varies by inspection activity)

### Performance

If queries slow down:
1. Check index usage: `EXPLAIN ANALYZE` on slow queries
2. Consider adding indexes on frequently filtered columns
3. Implement result caching for stats endpoints

---

## Rollback Plan

If deployment fails:

1. **Rollback Web Service**:
   - Go to Render → Web Service → Manual Deploy
   - Select previous successful commit
   - Deploy

2. **Rollback Database Changes**:
   - Database changes are non-destructive (CREATE IF NOT EXISTS)
   - No rollback needed unless you manually altered schema

3. **Revert DNS**:
   - Remove CNAME record in GoDaddy
   - Previous service remains unaffected

---

## Success Criteria

- [ ] Dashboard accessible at `bostonrestaurants.adamlozo.com`
- [ ] Map displays 1000+ inspection markers
- [ ] Filters work correctly
- [ ] Color-coding reflects inspection results
- [ ] Daily sync runs successfully
- [ ] Mobile-responsive design works
- [ ] No console errors
- [ ] API response times < 500ms

---

## Next Steps After Deployment

1. **Screenshot**: Capture dashboard for README and portfolio
2. **Analytics**: Consider adding Plausible analytics
3. **Social**: Share on LinkedIn, Twitter, Reddit r/boston
4. **Iteration Log**: Document lessons learned
5. **Next Dashboard**: Plan 311 Service Requests dashboard

---

## Support Resources

- **Render Status**: https://status.render.com
- **Analyze Boston**: https://data.boston.gov
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Leaflet.js Docs**: https://leafletjs.com

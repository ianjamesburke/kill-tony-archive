# Episode Processor Setup

`daily_processor.py` processes one Kill Tony episode per run. It checks YouTube
for new episodes first, then falls back to backfilling the newest unprocessed
episode (or reprocessing done episodes with an outdated pipeline version).

Runs hourly, 8am–midnight Mountain Time (~16 episodes/day). Stays within Gemini
free tier limits (~128/250 RPD on 2.5-flash, ~128/1000 RPD on flash-lite).

## Quick Start

```bash
# Dry run — see what it would process
python3 backend/daily_processor.py --dry-run

# Process one episode (check YouTube + backfill)
python3 backend/daily_processor.py

# Backfill only (skip YouTube check)
python3 backend/daily_processor.py --backfill
```

## Linux Cron

```bash
crontab -e
# Hourly, 8am-midnight Mountain Time (adjust TZ for your server)
0 8-23 * * * cd /path/to/kill-tony-data-project-v1/backend && /usr/bin/python3 daily_processor.py >> /var/log/killtony.log 2>&1
```

## Systemd Timer (recommended for servers)

```bash
sudo cp backend/cron/killtony-daily.service /etc/systemd/system/
sudo cp backend/cron/killtony-daily.timer /etc/systemd/system/

# Edit the service file to set your paths and env vars
sudo systemctl edit killtony-daily.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now killtony-daily.timer

# Check status
systemctl status killtony-daily.timer
journalctl -u killtony-daily.service -f
```

## Environment Variables

Set in `.env` or in the systemd service:

- `GEMINI_API_KEY` — Google AI API key
- `RAILWAY_BACKEND_URL` — (optional) Railway backend URL for DB sync after processing
- `ADMIN_SECRET` — (optional) Railway admin secret for DB sync

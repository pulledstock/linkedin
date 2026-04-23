# LinkedIn Job Monitor

Monitors LinkedIn job listings for new matches and sends Discord notifications.

## Setup

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium   # installs system deps on Ubuntu
```

## Configuration

Edit `config.json`:
- Set `discord_webhook_url` (Server Settings → Integrations → Webhooks in Discord)
- Add/remove entries in `searches` with your desired keywords and location
- Adjust `check_interval_minutes`

## Run

```bash
python monitor.py
```

## Run as systemd service (Ubuntu)

```bash
# Copy repo to server, then:
cp linkedin-monitor.service /etc/systemd/system/
# Edit the service file: replace YOUR_USER with your username
nano /etc/systemd/system/linkedin-monitor.service

systemctl daemon-reload
systemctl enable linkedin-monitor
systemctl start linkedin-monitor
systemctl status linkedin-monitor
```


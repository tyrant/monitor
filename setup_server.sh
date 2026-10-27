#!/usr/bin/env bash
# First-time server setup. Run once from your Mac:
#   bash setup_server.sh
set -euo pipefail

SERVER="noob@168.144.167.177"
REMOTE_DIR="/home/noob/monitor"

echo "==> Syncing files..."
rsync -av --exclude='.env' --exclude='monitor.db' --exclude='__pycache__' --exclude='venv' --exclude='.git' \
  "$(dirname "$0")/" "$SERVER:$REMOTE_DIR/"

echo "==> Installing dependencies..."
ssh "$SERVER" bash <<'EOF'
  set -e
  cd /home/noob/monitor
  python3 -m venv venv
  venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q -r requirements.txt
EOF

echo ""
echo "==> Generating API key..."
API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "    API key: $API_KEY"
echo "    (add MONITOR_API_KEY=$API_KEY to your Mac environment — e.g. ~/.zshrc)"
echo ""

echo "==> Creating .env on server (edit to fill in the Resend API key)..."
ssh "$SERVER" bash <<EOF
  cat > /home/noob/monitor/.env <<ENVFILE
MONITOR_API_KEY=$API_KEY
MONITOR_ALERT_FROM=Monitor <monitor@sexyverse.email>
MONITOR_ALERT_TO=deathtomosttyrants@gmail.com
MONITOR_RESEND_API_KEY=REPLACE_WITH_RESEND_API_KEY
MONITOR_DB_PATH=/home/noob/monitor/monitor.db
ENVFILE
  chmod 600 /home/noob/monitor/.env
EOF

echo "==> Creating .htpasswd for Basic Auth..."
echo "    Enter a password for the dashboard web UI:"
read -rs DASH_PASS
echo ""
HTPASSWD_HASH=$(openssl passwd -apr1 "$DASH_PASS")
echo "noob:$HTPASSWD_HASH" | ssh "$SERVER" "cat > /home/noob/monitor/.htpasswd"

echo "==> Installing systemd service (will prompt for sudo password)..."
ssh -t "$SERVER" "sudo cp /home/noob/monitor/monitor.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable monitor && sudo systemctl start monitor"

echo "==> Installing certbot and obtaining SSL cert (will prompt for sudo password)..."
echo "    Note: nginx will be stopped briefly to obtain the cert."
ssh -t "$SERVER" "sudo apt-get install -y certbot && sudo systemctl stop nginx && sudo certbot certonly --standalone -d monitor.mikeyclarke.co.nz --non-interactive --agree-tos -m deathtomosttyrants@gmail.com; sudo systemctl start nginx"

echo ""
echo "==> Manual steps remaining:"
echo "    1. Add DNS A record: monitor.mikeyclarke.co.nz -> 168.144.167.177"
echo "    2. Edit /home/noob/monitor/.env and fill in MONITOR_RESEND_API_KEY"
echo "       (the blog's Resend key works; FROM must be on a Resend-verified domain)"
echo "    3. Copy nginx_fragment.conf to /etc/nginx/sites-available/monitor and symlink it into sites-enabled/"
echo "    4. Reload nginx: sudo nginx -t && sudo systemctl reload nginx"
echo "    5. Add to crontab on server:"
echo "       0 14 * * * /home/noob/monitor/venv/bin/python /home/noob/monitor/check_missing.py"
echo "    6. Add MONITOR_API_KEY=$API_KEY to ~/.zshrc on your Mac"

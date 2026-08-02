#!/usr/bin/env bash
# Deploy latest changes to the server.
#   bash deploy.sh
set -euo pipefail

SERVER="noob@168.144.167.177"
REMOTE_DIR="/home/noob/monitor"

echo "==> Syncing files..."
rsync -av --exclude='.env' --exclude='monitor.db' --exclude='__pycache__' --exclude='venv' --exclude='.git' \
  "$(dirname "$0")/" "$SERVER:$REMOTE_DIR/"

echo "==> Updating dependencies..."
ssh "$SERVER" "/home/noob/monitor/venv/bin/pip install -q -r $REMOTE_DIR/requirements.txt"

echo "==> Restarting service..."
ssh -t "$SERVER" "sudo systemctl restart monitor"

echo "==> Done."

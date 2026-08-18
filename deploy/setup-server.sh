#!/usr/bin/env bash
#
# One-time setup for a fresh Ubuntu 24.04 server.
#
# Run once, as root, on a brand-new VPS. It installs everything the app needs, creates the
# unprivileged user it runs as, and stops short of anything that needs a secret — the .env
# and the certificate are separate steps, because both need values only you have.
#
#   ssh root@<server-ip>
#   bash setup-server.sh
#
# There is deliberately NO PostgreSQL here. The database is already hosted on Supabase in
# ap-south-1 and the app connects to it over the network; installing a second one on this
# box would create an empty database nothing uses.

set -euo pipefail

APP_USER=reportcraft
APP_DIR=/opt/reportcraft

echo "==> Updating the system"
apt-get update -qq
apt-get upgrade -y -qq

echo "==> Base tools"
apt-get install -y -qq git curl ufw ca-certificates

echo "==> Python"
# Ubuntu 24.04 ships 3.12. The project is developed on 3.14 but pins nothing that needs it;
# python3-dev and build-essential are for the packages that compile (psycopg2 among them).
apt-get install -y -qq python3 python3-venv python3-pip python3-dev build-essential libpq-dev
python3 --version

echo "==> Node (for building the frontend)"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
apt-get install -y -qq nodejs
node --version

echo "==> LibreOffice"
# The single reason this deployment is not in a slim container. Every workbook recalculation
# and every PDF shells out to soffice; without it, formulas ship uncalculated and PDF returns
# a 503. --no-install-recommends keeps out the desktop packages a server has no use for.
apt-get install -y -qq --no-install-recommends libreoffice-calc libreoffice-writer
# Fonts, so a rendered PDF is not full of substituted glyphs.
apt-get install -y -qq fonts-dejavu fonts-liberation
which soffice || ln -s /usr/bin/libreoffice /usr/bin/soffice
soffice --version || true

echo "==> Nginx and certbot"
apt-get install -y -qq nginx certbot python3-certbot-nginx

echo "==> Application user"
# The app runs as a user that owns nothing but its own directory. A compromised web process
# should not be a root shell.
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> Firewall"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status

echo
echo "Done. Next:"
echo "  1. su - $APP_USER"
echo "  2. git clone <backend repo>  $APP_DIR/backend"
echo "  3. git clone <frontend repo> $APP_DIR/frontend"
echo "  4. copy .env.production.example to $APP_DIR/backend/.env and fill it in"
echo "  5. bash $APP_DIR/backend/deploy/deploy.sh"

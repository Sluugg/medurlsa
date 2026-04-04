#!/bin/sh
# install.sh — installs dependencies, builds the frontend, and configures a
# system service for web_share_app. Detects Alpine (OpenRC) and Debian/Ubuntu
# (systemd) automatically. Must be run as root.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR"
SERVICE_NAME="webshare"
UVICORN="$APP_DIR/.venv/bin/uvicorn"
LOG_DIR="/var/log/$SERVICE_NAME"

# ── Colour helpers ────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m OK\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33mWARN\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; exit 1; }

# ── Root check ────────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "This script must be run as root."

# ── Detect OS ─────────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="$ID"
    OS_LIKE="${ID_LIKE:-}"
else
    die "Cannot detect OS: /etc/os-release not found."
fi

case "$OS_ID" in
    alpine)
        PLATFORM="alpine"
        ;;
    debian|ubuntu|raspbian)
        PLATFORM="debian"
        ;;
    *)
        # Catch derivatives (e.g. Linux Mint, Pop!_OS) via ID_LIKE
        case "$OS_LIKE" in
            *debian*|*ubuntu*)
                PLATFORM="debian"
                ;;
            *)
                die "Unsupported OS: $OS_ID. Supported platforms: Alpine, Debian, Ubuntu."
                ;;
        esac
        ;;
esac

info "Detected platform: $PLATFORM ($OS_ID)"

# ── Install system dependencies ───────────────────────────────────────────────
info "Installing system dependencies..."

case "$PLATFORM" in
    alpine)
        apk add --no-cache python3 py3-pip nodejs npm
        ;;
    debian)
        apt-get update -qq
        apt-get install -y python3 python3-venv python3-pip nodejs npm
        ;;
esac

ok "System dependencies installed."

# ── Python venv + dependencies ────────────────────────────────────────────────
info "Setting up Python virtual environment..."
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
ok "Python dependencies installed."

# ── Frontend build ────────────────────────────────────────────────────────────
info "Building frontend..."
cd "$APP_DIR/frontend"
npm install --silent
npm run build --silent
cd "$APP_DIR"
ok "Frontend built."

# ── Runtime directories ───────────────────────────────────────────────────────
info "Creating runtime directories..."
mkdir -p "$APP_DIR/data"
mkdir -p "$APP_DIR/backgrounds"
mkdir -p "$LOG_DIR"
ok "Directories ready."

# ── .env scaffolding ──────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    info "Creating .env from template..."
    cat > "$APP_DIR/.env" <<EOF
JELLYFIN_URL=http://your-jellyfin-server:8096
JELLYFIN_API_KEY=your_api_key_here
ADMIN_TOKEN=change_this_to_a_strong_password
PUBLIC_BASE_URL=http://your-public-domain-or-ip
DB_PATH=$APP_DIR/data/links.db
BACKGROUNDS_DIR=$APP_DIR/backgrounds
EOF
    warn ".env created at $APP_DIR/.env — edit it before starting the service."
else
    ok ".env already exists, leaving it untouched."
fi

# ── Service installation ──────────────────────────────────────────────────────
case "$PLATFORM" in

    alpine)
        info "Installing OpenRC service..."
        cat > "/etc/init.d/$SERVICE_NAME" <<EOF
#!/sbin/openrc-run

name="$SERVICE_NAME"
description="Web Share App"
directory="$APP_DIR"
command="$UVICORN"
command_args="app.main:app --host 0.0.0.0 --port 80 --workers 1"
command_user="root"
pidfile="/run/\${RC_SVCNAME}.pid"
command_background=true

output_log="$LOG_DIR/out.log"
error_log="$LOG_DIR/err.log"

depend() {
    need net
    after firewall
}

start_pre() {
    cd "$APP_DIR"
}
EOF
        chmod +x "/etc/init.d/$SERVICE_NAME"
        rc-update add "$SERVICE_NAME" default
        ok "OpenRC service installed and enabled."
        info "Start now with:  rc-service $SERVICE_NAME start"
        ;;

    debian)
        info "Installing systemd service..."
        cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Web Share App
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$UVICORN app.main:app --host 0.0.0.0 --port 80 --workers 1
Restart=on-failure
StandardOutput=append:$LOG_DIR/out.log
StandardError=append:$LOG_DIR/err.log

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        ok "systemd service installed and enabled."
        info "Start now with:  systemctl start $SERVICE_NAME"
        ;;

esac

echo ""
ok "Installation complete."
printf '    App directory:  %s\n' "$APP_DIR"
printf '    Logs:           %s\n' "$LOG_DIR"
printf '    .env:           %s/.env\n' "$APP_DIR"
echo ""
warn "Edit .env before starting the service if you have not done so already."
